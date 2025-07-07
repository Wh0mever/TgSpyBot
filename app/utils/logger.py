"""
Настройка логирования для TgSpyBot
"""
import sys
from loguru import logger
from app.config.settings import settings


def setup_logger():
    """Настройка логгера"""
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Добавляем консольный вывод
    logger.add(
        sys.stderr,
        level=settings.logging.level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # Добавляем файловый вывод
    logger.add(
        settings.logging.file,
        level=settings.logging.level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    logger.info("Логирование настроено")


# Настраиваем логгер при импорте модуля
setup_logger() 