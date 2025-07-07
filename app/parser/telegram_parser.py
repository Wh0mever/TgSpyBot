"""
Основной парсер Telegram сообщений
Использует Telethon для мониторинга открытых чатов
"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from telethon import TelegramClient, events
from telethon.tl.types import Message, User, Chat, Channel
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from loguru import logger

from app.config.settings import settings


class TelegramParser:
    """Парсер сообщений из Telegram чатов"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.monitored_chats: Dict[str, Dict] = {}
        self.keywords: List[str] = settings.parser.keywords
        self.is_running = False
        self.message_handlers: List[Callable] = []
        self.last_check_time = {}
        
    async def initialize(self) -> bool:
        """Инициализация клиента Telegram"""
        try:
            self.client = TelegramClient(
                settings.telegram.session_file,
                settings.telegram.api_id,
                settings.telegram.api_hash
            )
            
            logger.info("Подключение к Telegram...")
            await self.client.start(phone=settings.telegram.phone)
            
            if not await self.client.is_user_authorized():
                logger.error("Пользователь не авторизован")
                return False
                
            me = await self.client.get_me()
            logger.info(f"Успешно подключен как: {me.first_name} ({me.username})")
            
            return True
            
        except SessionPasswordNeededError:
            logger.error("Требуется двухфакторная аутентификация")
            return False
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")
            return False
    
    async def add_chat(self, chat_link: str) -> bool:
        """Добавление чата для мониторинга"""
        try:
            # Извлекаем username из ссылки
            username = self._extract_username_from_link(chat_link)
            if not username:
                logger.error(f"Не удалось извлечь username из ссылки: {chat_link}")
                return False
            
            # Получаем информацию о чате
            try:
                entity = await self.client.get_entity(username)
            except Exception as e:
                logger.error(f"Не удалось найти чат {username}: {e}")
                return False
            
            chat_info = {
                "id": entity.id,
                "title": getattr(entity, 'title', getattr(entity, 'first_name', username)),
                "username": username,
                "link": chat_link,
                "type": self._get_chat_type(entity),
                "added_at": datetime.now(),
                "last_message_id": 0
            }
            
            self.monitored_chats[username] = chat_info
            self.last_check_time[username] = datetime.now() - timedelta(minutes=5)
            
            logger.info(f"Добавлен чат для мониторинга: {chat_info['title']} (@{username})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка добавления чата {chat_link}: {e}")
            return False
    
    async def remove_chat(self, chat_link: str) -> bool:
        """Удаление чата из мониторинга"""
        username = self._extract_username_from_link(chat_link)
        if username in self.monitored_chats:
            chat_title = self.monitored_chats[username]['title']
            del self.monitored_chats[username]
            del self.last_check_time[username]
            logger.info(f"Чат удален из мониторинга: {chat_title} (@{username})")
            return True
        return False
    
    def set_keywords(self, keywords: List[str]):
        """Установка ключевых слов для поиска"""
        self.keywords = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
        logger.info(f"Установлены ключевые слова: {self.keywords}")
    
    def add_message_handler(self, handler: Callable):
        """Добавление обработчика найденных сообщений"""
        self.message_handlers.append(handler)
    
    async def start_monitoring(self):
        """Запуск мониторинга чатов"""
        if not self.client:
            logger.error("Клиент не инициализирован")
            return
        
        self.is_running = True
        logger.info("Запуск мониторинга чатов...")
        
        while self.is_running:
            try:
                await self._check_all_chats()
                await asyncio.sleep(settings.parser.check_interval)
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(30)  # Пауза при ошибке
    
    async def stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_running = False
        logger.info("Мониторинг остановлен")
    
    async def _check_all_chats(self):
        """Проверка всех чатов на новые сообщения"""
        for username, chat_info in self.monitored_chats.items():
            try:
                await self._check_chat_messages(username, chat_info)
                # Пауза между проверками чатов для соблюдения rate limits
                await asyncio.sleep(2)
            except FloodWaitError as e:
                logger.warning(f"FloodWait {e.seconds} секунд для чата {username}")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Ошибка проверки чата {username}: {e}")
    
    async def _check_chat_messages(self, username: str, chat_info: Dict):
        """Проверка сообщений в конкретном чате"""
        try:
            entity = await self.client.get_entity(username)
            last_check = self.last_check_time.get(username, datetime.now() - timedelta(minutes=5))
            
            # Получаем последние сообщения
            messages = await self.client.get_messages(
                entity,
                limit=50,  # Проверяем последние 50 сообщений
                offset_date=last_check
            )
            
            new_messages_count = 0
            for message in reversed(messages):  # Обрабатываем в хронологическом порядке
                if message.date > last_check and message.text:
                    if self._check_message_keywords(message.text):
                        await self._handle_found_message(message, chat_info)
                        new_messages_count += 1
            
            self.last_check_time[username] = datetime.now()
            
            if new_messages_count > 0:
                logger.info(f"Найдено {new_messages_count} сообщений по ключевым словам в {chat_info['title']}")
                
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из {username}: {e}")
    
    def _check_message_keywords(self, text: str) -> bool:
        """Проверка сообщения на наличие ключевых слов"""
        if not self.keywords or not text:
            return False
        
        text_lower = text.lower()
        for keyword in self.keywords:
            if keyword in text_lower:
                return True
        return False
    
    async def _handle_found_message(self, message: Message, chat_info: Dict):
        """Обработка найденного сообщения"""
        message_data = {
            "chat_title": chat_info["title"],
            "chat_username": chat_info["username"],
            "chat_link": chat_info["link"],
            "message_text": message.text,
            "message_id": message.id,
            "date": message.date,
            "sender_id": message.sender_id if message.sender_id else None,
            "found_keywords": self._find_matching_keywords(message.text)
        }
        
        # Вызываем все зарегистрированные обработчики
        for handler in self.message_handlers:
            try:
                await handler(message_data)
            except Exception as e:
                logger.error(f"Ошибка в обработчике сообщения: {e}")
    
    def _find_matching_keywords(self, text: str) -> List[str]:
        """Находит все ключевые слова в тексте"""
        text_lower = text.lower()
        found = []
        for keyword in self.keywords:
            if keyword in text_lower:
                found.append(keyword)
        return found
    
    def _extract_username_from_link(self, link: str) -> Optional[str]:
        """Извлечение username из ссылки на чат"""
        patterns = [
            r't\.me/([a-zA-Z0-9_]+)',
            r'telegram\.me/([a-zA-Z0-9_]+)',
            r'@([a-zA-Z0-9_]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return match.group(1)
        
        # Если это просто username без ссылки
        if link.startswith('@'):
            return link[1:]
        elif '/' not in link and '@' not in link:
            return link
            
        return None
    
    def _get_chat_type(self, entity) -> str:
        """Определение типа чата"""
        if isinstance(entity, User):
            return "user"
        elif isinstance(entity, Chat):
            return "group"
        elif isinstance(entity, Channel):
            return "channel"
        else:
            return "unknown"
    
    async def get_chat_info(self, username: str) -> Optional[Dict]:
        """Получение информации о чате"""
        if username in self.monitored_chats:
            return self.monitored_chats[username]
        return None
    
    def get_monitored_chats(self) -> Dict[str, Dict]:
        """Получение списка отслеживаемых чатов"""
        return self.monitored_chats.copy()
    
    async def disconnect(self):
        """Отключение от Telegram"""
        if self.client:
            await self.client.disconnect()
            logger.info("Отключение от Telegram") 