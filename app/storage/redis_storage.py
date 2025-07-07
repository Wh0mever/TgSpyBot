"""
Redis хранилище для TgSpyBot
Сохраняет настройки, чаты, ключевые слова
"""
import json
import redis.asyncio as redis
from typing import Dict, List, Optional
from loguru import logger

from app.config.settings import settings


class RedisStorage:
    """Хранилище данных в Redis"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        
        # Ключи для хранения данных
        self.KEYWORDS_KEY = "tgspybot:keywords"
        self.CHATS_KEY = "tgspybot:monitored_chats"
        self.SETTINGS_KEY = "tgspybot:settings"
        self.STATS_KEY = "tgspybot:stats"
    
    async def initialize(self):
        """Инициализация подключения к Redis"""
        try:
            self.redis = redis.Redis(
                host=settings.database.redis_host,
                port=settings.database.redis_port,
                password=settings.database.redis_password,
                decode_responses=True,
                encoding='utf-8'
            )
            
            # Проверяем подключение
            await self.redis.ping()
            logger.info("✅ Подключение к Redis установлено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Redis: {e}")
            raise
    
    async def close(self):
        """Закрытие подключения"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis подключение закрыто")
    
    async def save_keywords(self, keywords: List[str]):
        """Сохранение ключевых слов"""
        try:
            keywords_json = json.dumps(keywords, ensure_ascii=False)
            await self.redis.set(self.KEYWORDS_KEY, keywords_json)
            logger.debug(f"Ключевые слова сохранены в Redis: {keywords}")
        except Exception as e:
            logger.error(f"Ошибка сохранения ключевых слов: {e}")
    
    async def load_keywords(self) -> List[str]:
        """Загрузка ключевых слов"""
        try:
            keywords_json = await self.redis.get(self.KEYWORDS_KEY)
            if keywords_json:
                keywords = json.loads(keywords_json)
                logger.debug(f"Ключевые слова загружены из Redis: {keywords}")
                return keywords
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки ключевых слов: {e}")
            return []
    
    async def save_monitored_chats(self, chats: Dict[str, Dict]):
        """Сохранение отслеживаемых чатов"""
        try:
            # Конвертируем datetime в строки для JSON
            chats_for_json = {}
            for username, chat_info in chats.items():
                chat_copy = chat_info.copy()
                if 'added_at' in chat_copy:
                    chat_copy['added_at'] = chat_copy['added_at'].isoformat()
                chats_for_json[username] = chat_copy
            
            chats_json = json.dumps(chats_for_json, ensure_ascii=False)
            await self.redis.set(self.CHATS_KEY, chats_json)
            logger.debug(f"Чаты сохранены в Redis: {list(chats.keys())}")
        except Exception as e:
            logger.error(f"Ошибка сохранения чатов: {e}")
    
    async def load_monitored_chats(self) -> Dict[str, Dict]:
        """Загрузка отслеживаемых чатов"""
        try:
            chats_json = await self.redis.get(self.CHATS_KEY)
            if chats_json:
                from datetime import datetime
                chats = json.loads(chats_json)
                
                # Конвертируем строки обратно в datetime
                for username, chat_info in chats.items():
                    if 'added_at' in chat_info and isinstance(chat_info['added_at'], str):
                        chat_info['added_at'] = datetime.fromisoformat(chat_info['added_at'])
                
                logger.debug(f"Чаты загружены из Redis: {list(chats.keys())}")
                return chats
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки чатов: {e}")
            return {}
    
    async def save_settings(self, settings_dict: Dict):
        """Сохранение настроек"""
        try:
            settings_json = json.dumps(settings_dict, ensure_ascii=False)
            await self.redis.set(self.SETTINGS_KEY, settings_json)
            logger.debug("Настройки сохранены в Redis")
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")
    
    async def load_settings(self) -> Dict:
        """Загрузка настроек"""
        try:
            settings_json = await self.redis.get(self.SETTINGS_KEY)
            if settings_json:
                settings_dict = json.loads(settings_json)
                logger.debug("Настройки загружены из Redis")
                return settings_dict
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
            return {}
    
    async def increment_stat(self, stat_name: str, value: int = 1):
        """Увеличение счетчика статистики"""
        try:
            await self.redis.hincrby(self.STATS_KEY, stat_name, value)
        except Exception as e:
            logger.error(f"Ошибка обновления статистики {stat_name}: {e}")
    
    async def get_stats(self) -> Dict[str, int]:
        """Получение статистики"""
        try:
            stats = await self.redis.hgetall(self.STATS_KEY)
            # Конвертируем значения в int
            return {k: int(v) for k, v in stats.items()}
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    async def save_found_message(self, message_data: Dict):
        """Сохранение найденного сообщения"""
        try:
            # Используем timestamp как ключ
            timestamp = message_data['date'].timestamp()
            key = f"tgspybot:found_messages:{timestamp}"
            
            # Подготавливаем данные для JSON
            message_copy = message_data.copy()
            message_copy['date'] = message_data['date'].isoformat()
            
            message_json = json.dumps(message_copy, ensure_ascii=False)
            
            # Сохраняем с TTL 30 дней
            await self.redis.setex(key, 30 * 24 * 3600, message_json)
            
            # Обновляем статистику
            await self.increment_stat("messages_found")
            await self.increment_stat(f"messages_from_{message_data['chat_username']}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения найденного сообщения: {e}")
    
    async def get_recent_found_messages(self, limit: int = 10) -> List[Dict]:
        """Получение последних найденных сообщений"""
        try:
            pattern = "tgspybot:found_messages:*"
            keys = await self.redis.keys(pattern)
            
            # Сортируем по timestamp (который в ключе)
            keys.sort(key=lambda x: float(x.split(':')[-1]), reverse=True)
            
            messages = []
            for key in keys[:limit]:
                message_json = await self.redis.get(key)
                if message_json:
                    message_data = json.loads(message_json)
                    # Конвертируем дату обратно
                    from datetime import datetime
                    message_data['date'] = datetime.fromisoformat(message_data['date'])
                    messages.append(message_data)
            
            return messages
        except Exception as e:
            logger.error(f"Ошибка получения найденных сообщений: {e}")
            return []
    
    async def clear_all_data(self):
        """Очистка всех данных бота (для тестирования)"""
        try:
            keys_to_delete = await self.redis.keys("tgspybot:*")
            if keys_to_delete:
                await self.redis.delete(*keys_to_delete)
                logger.info(f"Удалено {len(keys_to_delete)} ключей из Redis")
        except Exception as e:
            logger.error(f"Ошибка очистки данных: {e}")


class SQLiteStorage:
    """Альтернативное хранилище в SQLite (для случаев без Redis)"""
    
    def __init__(self):
        self.db_path = settings.database.url.replace("sqlite:///", "")
        
    async def initialize(self):
        """Инициализация SQLite базы"""
        import aiosqlite
        import os
        
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Создаем таблицы
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_data (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS found_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_username TEXT,
                    chat_title TEXT,
                    message_text TEXT,
                    keywords TEXT,
                    found_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
        
        logger.info("✅ SQLite база инициализирована")
    
    async def save_keywords(self, keywords: List[str]):
        """Сохранение ключевых слов в SQLite"""
        import aiosqlite
        keywords_json = json.dumps(keywords, ensure_ascii=False)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO bot_data (key, value) VALUES (?, ?)",
                ("keywords", keywords_json)
            )
            await db.commit()
    
    async def load_keywords(self) -> List[str]:
        """Загрузка ключевых слов из SQLite"""
        import aiosqlite
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM bot_data WHERE key = ?", ("keywords",)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return []
    
    # Аналогичные методы для SQLite можно добавить по необходимости
    async def close(self):
        """SQLite не требует явного закрытия"""
        pass 