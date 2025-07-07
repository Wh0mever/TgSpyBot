#!/usr/bin/env python3
"""
TgSpyBot - Полная версия с Telegram ботом
Основной файл для запуска парсера и бота управления
"""
import asyncio
import signal
import sys
from loguru import logger

# Импортируем компоненты приложения
from app.parser.telegram_parser import TelegramParser
from app.bot.telegram_bot import TelegramBot
from app.utils.logger import setup_logger
from app.utils.notification_handler import console_handler, file_handler, database_handler
from app.config.settings import settings


class TgSpyBotApp:
    """Главное приложение TgSpyBot"""
    
    def __init__(self):
        self.parser = TelegramParser()
        self.bot = TelegramBot(self.parser)
        self.is_running = False
        
    async def start(self):
        """Запуск всего приложения"""
        logger.info("🚀 Запуск TgSpyBot - полная версия")
        
        try:
            # Инициализируем парсер
            logger.info("📡 Инициализация Telegram парсера...")
            if not await self.parser.initialize():
                logger.error("❌ Не удалось инициализировать парсер")
                return False
            
            # Добавляем базовые обработчики уведомлений
            self.parser.add_message_handler(console_handler.handle_found_message)
            self.parser.add_message_handler(file_handler.handle_found_message)
            self.parser.add_message_handler(database_handler.handle_found_message)
            
            # Показываем статус приложения
            self._show_startup_info()
            
            self.is_running = True
            
            # Запускаем парсер и бота параллельно
            parser_task = asyncio.create_task(self.parser.start_monitoring())
            bot_task = asyncio.create_task(self.bot.start())
            
            logger.info("✅ TgSpyBot успешно запущен!")
            logger.info("💡 Используйте команды в Telegram боте для управления")
            
            # Ждем завершения любой из задач
            done, pending = await asyncio.wait(
                [parser_task, bot_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            return False
        finally:
            await self.stop()
            
        return True
    
    async def stop(self):
        """Остановка приложения"""
        if not self.is_running:
            return
            
        logger.info("🛑 Остановка TgSpyBot...")
        self.is_running = False
        
        try:
            # Останавливаем компоненты
            await self.parser.stop_monitoring()
            await self.bot.stop()
            await self.parser.disconnect()
            
            logger.info("✅ TgSpyBot успешно остановлен")
        except Exception as e:
            logger.error(f"Ошибка при остановке: {e}")
    
    def _show_startup_info(self):
        """Отображение информации о запуске"""
        logger.info("⚙️ Конфигурация приложения:")
        logger.info(f"   📱 Telegram Phone: {settings.telegram.phone}")
        logger.info(f"   🤖 Bot ID: {settings.bot.token.split(':')[0]}")
        logger.info(f"   👤 Admin ID: {settings.bot.admin_user_id}")
        logger.info(f"   💬 Notification Chat: {settings.notification.chat_id}")
        logger.info(f"   🔍 Keywords: {settings.parser.keywords}")
        logger.info(f"   ⏰ Check Interval: {settings.parser.check_interval}s")
        logger.info(f"   📊 Max Chats: {settings.parser.max_chats}")
        logger.info(f"   🗄️ Database: {settings.database.type}")
        
        if settings.database.type == "redis":
            logger.info(f"   📍 Redis: {settings.database.redis_host}:{settings.database.redis_port}")
    
    async def health_check(self):
        """Проверка состояния системы"""
        status = {
            "parser_running": self.parser.is_running,
            "parser_connected": self.parser.client is not None,
            "monitored_chats": len(self.parser.get_monitored_chats()),
            "keywords_count": len(self.parser.keywords),
        }
        return status


async def setup_signal_handlers(app: TgSpyBotApp):
    """Настройка обработчиков сигналов для корректного завершения"""
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        asyncio.create_task(app.stop())
    
    # Обработчики для различных сигналов
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination
    
    # Для Windows
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, signal_handler)


async def validate_configuration():
    """Проверка конфигурации перед запуском"""
    errors = []
    
    # Проверяем обязательные настройки Telegram
    if not settings.telegram.api_id:
        errors.append("TELEGRAM_API_ID не настроен")
    
    if not settings.telegram.api_hash:
        errors.append("TELEGRAM_API_HASH не настроен")
    
    if not settings.telegram.phone:
        errors.append("TELEGRAM_PHONE не настроен")
    
    # Проверяем настройки бота
    if not settings.bot.token:
        errors.append("BOT_TOKEN не настроен")
    
    if not settings.bot.password:
        errors.append("BOT_PASSWORD не настроен")
    
    if not settings.bot.admin_user_id:
        errors.append("ADMIN_USER_ID не настроен")
    
    # Проверяем базу данных
    if settings.database.type == "redis":
        try:
            import redis.asyncio as redis
            r = redis.Redis(
                host=settings.database.redis_host,
                port=settings.database.redis_port,
                password=settings.database.redis_password
            )
            await r.ping()
            await r.close()
            logger.info("✅ Redis подключение проверено")
        except Exception as e:
            errors.append(f"Ошибка подключения к Redis: {e}")
    
    if errors:
        logger.error("❌ Ошибки конфигурации:")
        for error in errors:
            logger.error(f"   • {error}")
        logger.info("💡 Проверьте файл .env или переменные окружения")
        return False
    
    logger.info("✅ Конфигурация валидна")
    return True


async def main():
    """Главная функция приложения"""
    
    print("""
╔══════════════════════════════════════════════╗
║              TgSpyBot v1.0                   ║
║     Парсер сообщений Telegram с ботом       ║
║           управления                         ║
╚══════════════════════════════════════════════╝
    """)
    
    logger.info("Инициализация TgSpyBot...")
    
    # Проверяем конфигурацию
    if not await validate_configuration():
        logger.error("❌ Запуск невозможен из-за ошибок конфигурации")
        return
    
    # Создаем и настраиваем приложение
    app = TgSpyBotApp()
    await setup_signal_handlers(app)
    
    try:
        # Запускаем приложение
        success = await app.start()
        
        if success:
            logger.info("TgSpyBot завершен штатно")
        else:
            logger.error("TgSpyBot завершен с ошибками")
            
    except KeyboardInterrupt:
        logger.info("Прерывание пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
    finally:
        logger.info("Завершение работы TgSpyBot")


if __name__ == "__main__":
    # Запускаем приложение
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        sys.exit(1) 