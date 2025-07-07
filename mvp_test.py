#!/usr/bin/env python3
"""
MVP тест парсера TgSpyBot
Простая демонстрация функционала
"""
import asyncio
import signal
import sys
from loguru import logger

# Импортируем наши модули
from app.parser.telegram_parser import TelegramParser
from app.utils.notification_handler import console_handler, file_handler
from app.utils.logger import setup_logger
from app.config.settings import settings


class MVPBot:
    """Простой MVP бот для тестирования парсера"""
    
    def __init__(self):
        self.parser = TelegramParser()
        self.is_running = False
    
    async def start(self):
        """Запуск MVP бота"""
        logger.info("🚀 Запуск TgSpyBot MVP")
        
        # Инициализируем парсер
        if not await self.parser.initialize():
            logger.error("❌ Не удалось инициализировать парсер")
            return False
        
        # Добавляем обработчики уведомлений
        self.parser.add_message_handler(console_handler.handle_found_message)
        self.parser.add_message_handler(file_handler.handle_found_message)
        
        # Показываем текущие настройки
        self._show_settings()
        
        # Добавляем тестовые чаты (если не заданы в настройках)
        await self._setup_test_chats()
        
        # Запускаем мониторинг
        self.is_running = True
        try:
            await self.parser.start_monitoring()
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки")
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка бота"""
        logger.info("🛑 Остановка TgSpyBot MVP")
        self.is_running = False
        await self.parser.stop_monitoring()
        await self.parser.disconnect()
    
    def _show_settings(self):
        """Показ текущих настроек"""
        logger.info("⚙️ Текущие настройки:")
        logger.info(f"   📱 Телефон: {settings.telegram.phone}")
        logger.info(f"   🔍 Ключевые слова: {settings.parser.keywords}")
        logger.info(f"   ⏰ Интервал проверки: {settings.parser.check_interval} сек")
        logger.info(f"   📊 Максимум чатов: {settings.parser.max_chats}")
    
    async def _setup_test_chats(self):
        """Настройка тестовых чатов"""
        if not self.parser.get_monitored_chats():
            logger.info("📋 Чаты для мониторинга не заданы")
            logger.info("💡 Добавьте чаты вручную через метод add_chat() или через будущий бот")
            
            # Пример добавления чата (закомментирован)
            # await self.parser.add_chat("@test_channel")
    
    async def add_test_chat(self, chat_link: str):
        """Добавление тестового чата"""
        logger.info(f"➕ Добавление тестового чата: {chat_link}")
        success = await self.parser.add_chat(chat_link)
        if success:
            logger.info(f"✅ Чат добавлен успешно")
        else:
            logger.error(f"❌ Не удалось добавить чат")
        return success
    
    def set_test_keywords(self, keywords_str: str):
        """Установка тестовых ключевых слов"""
        keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        self.parser.set_keywords(keywords)
        logger.info(f"🔍 Установлены ключевые слова: {keywords}")


async def main():
    """Главная функция MVP теста"""
    
    print("""
╔══════════════════════════════════════════════╗
║           TgSpyBot MVP Test v1.0             ║
║        Парсер сообщений Telegram            ║
╚══════════════════════════════════════════════╝
    """)
    
    # Проверяем наличие настроек
    try:
        # Проверяем ключевые настройки
        if not hasattr(settings.telegram, 'api_id') or not settings.telegram.api_id:
            logger.error("❌ Не найден TELEGRAM_API_ID в настройках")
            logger.info("💡 Скопируйте env.example в .env и заполните настройки")
            return
            
        if not hasattr(settings.telegram, 'api_hash') or not settings.telegram.api_hash:
            logger.error("❌ Не найден TELEGRAM_API_HASH в настройках")
            return
            
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки настроек: {e}")
        logger.info("💡 Проверьте файл .env или переменные окружения")
        return
    
    # Создаем и запускаем MVP бота
    mvp_bot = MVPBot()
    
    # Обработчик сигналов для корректного завершения
    def signal_handler(signum, frame):
        logger.info("Получен сигнал завершения")
        asyncio.create_task(mvp_bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await mvp_bot.start()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        logger.info("MVP тест завершен")


if __name__ == "__main__":
    asyncio.run(main()) 