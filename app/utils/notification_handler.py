"""
Обработчик уведомлений о найденных сообщениях
MVP версия - вывод в консоль
"""
from typing import Dict
from datetime import datetime
from loguru import logger


class ConsoleNotificationHandler:
    """Простой обработчик уведомлений в консоль"""
    
    async def handle_found_message(self, message_data: Dict):
        """Обработка найденного сообщения"""
        try:
            # Форматируем уведомление согласно ТЗ
            notification = self._format_notification(message_data)
            
            # Выводим в консоль
            print("\n" + "="*50)
            print(notification)
            print("="*50 + "\n")
            
            # Логируем
            logger.info(f"Найдено сообщение в {message_data['chat_title']} по ключевым словам: {message_data['found_keywords']}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки уведомления: {e}")
    
    def _format_notification(self, message_data: Dict) -> str:
        """Форматирование уведомления согласно ТЗ"""
        
        # Обрезаем длинные сообщения
        message_text = message_data['message_text']
        if len(message_text) > 200:
            message_text = message_text[:200] + "..."
        
        # Форматируем дату
        date_str = message_data['date'].strftime("%d.%m.%Y %H:%M:%S")
        
        # Создаём уведомление
        notification = f"""🔔 [Найдено сообщение по ключевому слову!]

📢 Чат: {message_data['chat_title']}
🆔 Ссылка: https://t.me/{message_data['chat_username']}
✉️ Сообщение: {message_text}
🔍 Найденные ключевые слова: {', '.join(message_data['found_keywords'])}
⏰ Время: {date_str}"""
        
        return notification


class FileNotificationHandler:
    """Обработчик уведомлений в файл"""
    
    def __init__(self, filename: str = "data/found_messages.log"):
        self.filename = filename
    
    async def handle_found_message(self, message_data: Dict):
        """Сохранение найденного сообщения в файл"""
        try:
            log_entry = self._format_log_entry(message_data)
            
            # Записываем в файл
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
                
            logger.debug(f"Сообщение сохранено в {self.filename}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в файл: {e}")
    
    def _format_log_entry(self, message_data: Dict) -> str:
        """Форматирование записи для файла"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return f"[{timestamp}] CHAT: {message_data['chat_title']} (@{message_data['chat_username']}) | " \
               f"KEYWORDS: {','.join(message_data['found_keywords'])} | " \
               f"MESSAGE: {message_data['message_text'].replace('\n', ' ')}"


class DatabaseNotificationHandler:
    """Обработчик уведомлений с сохранением в базу данных"""
    
    def __init__(self):
        from app.storage.redis_storage import RedisStorage
        self.storage = RedisStorage()
        self._initialized = False
    
    async def handle_found_message(self, message_data: Dict):
        """Сохранение найденного сообщения в базу данных"""
        try:
            # Инициализируем хранилище при первом использовании
            if not self._initialized:
                await self.storage.initialize()
                self._initialized = True
            
            # Сохраняем в базу
            await self.storage.save_found_message(message_data)
            
            logger.debug(f"Сообщение сохранено в базу данных: {message_data['chat_title']}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в базу данных: {e}")


# Глобальные экземпляры обработчиков
console_handler = ConsoleNotificationHandler()
file_handler = FileNotificationHandler()
database_handler = DatabaseNotificationHandler() 