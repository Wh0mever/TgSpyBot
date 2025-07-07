"""
Конфигурация приложения TgSpyBot
Загружает настройки из переменных окружения с валидацией
"""
import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class TelegramSettings(BaseSettings):
    """Настройки Telegram API"""
    api_id: int = Field(..., env="TELEGRAM_API_ID")
    api_hash: str = Field(..., env="TELEGRAM_API_HASH")
    phone: str = Field(..., env="TELEGRAM_PHONE")
    session_file: str = Field(default="data/telegram_session", env="TELEGRAM_SESSION_FILE")

    class Config:
        env_prefix = "TELEGRAM_"


class BotSettings(BaseSettings):
    """Настройки Telegram бота"""
    token: str = Field(..., env="BOT_TOKEN")
    password: str = Field(..., env="BOT_PASSWORD")
    admin_user_id: int = Field(..., env="ADMIN_USER_ID")

    class Config:
        env_prefix = "BOT_"


class ParserSettings(BaseSettings):
    """Настройки парсера"""
    check_interval: int = Field(default=60, env="CHECK_INTERVAL")
    max_chats: int = Field(default=15, env="MAX_CHATS")
    keywords: str = Field(default="", env="KEYWORDS")
    api_rate_limit: int = Field(default=30, env="API_RATE_LIMIT")
    flood_wait_threshold: int = Field(default=300, env="FLOOD_WAIT_THRESHOLD")

    @validator("keywords")
    def parse_keywords(cls, v):
        """Парсим ключевые слова из строки в список"""
        if not v:
            return []
        return [keyword.strip().lower() for keyword in v.split(",") if keyword.strip()]

    class Config:
        env_prefix = "PARSER_"


class DatabaseSettings(BaseSettings):
    """Настройки базы данных"""
    type: str = Field(default="sqlite", env="DATABASE_TYPE")
    url: str = Field(default="sqlite:///data/tgspybot.db", env="DATABASE_URL")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    class Config:
        env_prefix = "DATABASE_"


class SecuritySettings(BaseSettings):
    """Настройки безопасности"""
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")
    session_encryption: bool = Field(default=True, env="SESSION_ENCRYPTION")

    class Config:
        env_prefix = "SECURITY_"


class LoggingSettings(BaseSettings):
    """Настройки логирования"""
    level: str = Field(default="INFO", env="LOG_LEVEL")
    file: str = Field(default="logs/tgspybot.log", env="LOG_FILE")
    error_notification: bool = Field(default=True, env="ERROR_NOTIFICATION")

    class Config:
        env_prefix = "LOG_"


class NotificationSettings(BaseSettings):
    """Настройки уведомлений"""
    chat_id: Optional[int] = Field(default=None, env="NOTIFICATION_CHAT_ID")

    class Config:
        env_prefix = "NOTIFICATION_"


class AppSettings:
    """Главные настройки приложения"""
    
    def __init__(self):
        self.telegram = TelegramSettings()
        self.bot = BotSettings()
        self.parser = ParserSettings()
        self.database = DatabaseSettings()
        self.security = SecuritySettings()
        self.logging = LoggingSettings()
        self.notification = NotificationSettings()
        
        # Создаём необходимые директории
        self._create_directories()
    
    def _create_directories(self):
        """Создаём необходимые директории"""
        directories = [
            "data",
            "logs",
            os.path.dirname(self.telegram.session_file),
            os.path.dirname(self.logging.file),
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

# Глобальный экземпляр настроек
settings = AppSettings() 