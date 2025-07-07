"""
Telegram бот для управления парсером TgSpyBot
Использует aiogram 3.x для обработки команд
"""
import asyncio
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from app.config.settings import settings
from app.parser.telegram_parser import TelegramParser
from app.storage.redis_storage import RedisStorage


class BotStates(StatesGroup):
    """Состояния бота для FSM"""
    waiting_for_password = State()
    authenticated = State()


class TelegramBot:
    """Telegram бот для управления парсером"""
    
    def __init__(self, parser: TelegramParser):
        self.bot = Bot(token=settings.bot.token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.parser = parser
        self.storage = RedisStorage()
        self.authorized_users: Dict[int, bool] = {}
        
        # Регистрируем обработчики
        self._register_handlers()
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        
        # Middleware для проверки авторизации
        self.dp.message.middleware.register(self._auth_middleware)
        
        # Команды
        self.dp.message.register(self._cmd_start, Command("start"))
        self.dp.message.register(self._cmd_help, Command("help"))
        self.dp.message.register(self._handle_password, StateFilter(BotStates.waiting_for_password))
        
        # Команды управления (только для авторизованных)
        self.dp.message.register(self._cmd_addchat, Command("addchat"))
        self.dp.message.register(self._cmd_removechat, Command("removechat"))
        self.dp.message.register(self._cmd_listchats, Command("listchats"))
        self.dp.message.register(self._cmd_keywords, Command("keywords"))
        self.dp.message.register(self._cmd_setkeywords, Command("setkeywords"))
        self.dp.message.register(self._cmd_status, Command("status"))
        
        # Неизвестные команды
        self.dp.message.register(self._handle_unknown)
    
    async def _auth_middleware(self, handler, event: types.Message, data: dict):
        """Middleware для проверки авторизации"""
        user_id = event.from_user.id
        
        # Проверяем, является ли пользователь администратором
        if user_id != settings.bot.admin_user_id:
            await event.answer("❌ У вас нет доступа к этому боту.")
            return
        
        # Проверяем авторизацию
        if not self.authorized_users.get(user_id, False):
            # Исключения для команд, доступных без авторизации
            if event.text and (event.text.startswith('/start') or event.text.startswith('/help')):
                return await handler(event, data)
            
            # Если ожидаем пароль
            state = data.get('state')
            if state and await state.get_state() == BotStates.waiting_for_password:
                return await handler(event, data)
            
            await event.answer("🔐 Для использования бота введите пароль.\nИспользуйте /start для начала.")
            return
        
        return await handler(event, data)
    
    async def _cmd_start(self, message: types.Message, state: FSMContext):
        """Команда /start"""
        user_id = message.from_user.id
        
        if self.authorized_users.get(user_id, False):
            await message.answer(
                "✅ Вы уже авторизованы!\n\n"
                "Используйте /help для просмотра доступных команд."
            )
            return
        
        await message.answer(
            "🤖 Добро пожаловать в TgSpyBot!\n\n"
            "🔐 Для доступа к функциям бота введите пароль:"
        )
        await state.set_state(BotStates.waiting_for_password)
    
    async def _handle_password(self, message: types.Message, state: FSMContext):
        """Обработка ввода пароля"""
        user_id = message.from_user.id
        password = message.text.strip()
        
        if password == settings.bot.password:
            self.authorized_users[user_id] = True
            await state.set_state(BotStates.authenticated)
            
            await message.answer(
                "✅ Авторизация успешна!\n\n"
                "🎯 TgSpyBot готов к работе.\n"
                "Используйте /help для просмотра команд."
            )
            
            # Удаляем сообщение с паролем для безопасности
            try:
                await message.delete()
            except:
                pass
                
            logger.info(f"Пользователь {user_id} успешно авторизован")
        else:
            await message.answer("❌ Неверный пароль. Попробуйте ещё раз:")
            logger.warning(f"Неудачная попытка авторизации от пользователя {user_id}")
    
    async def _cmd_help(self, message: types.Message):
        """Команда /help"""
        help_text = """
🤖 **TgSpyBot - Команды управления**

📋 **Управление чатами:**
• `/addchat <ссылка>` - добавить чат для мониторинга
• `/removechat <ссылка>` - удалить чат из мониторинга  
• `/listchats` - список отслеживаемых чатов

🔍 **Ключевые слова:**
• `/keywords` - показать текущие ключевые слова
• `/setkeywords слово1, слово2, слово3` - установить ключевые слова

📊 **Мониторинг:**
• `/status` - состояние парсера

ℹ️ **Справка:**
• `/help` - показать эту справку

---
**Примеры использования:**

`/addchat @durov`
`/addchat https://t.me/cryptonews`  
`/setkeywords биткоин, эфир, продам, куплю`
        """
        
        await message.answer(help_text, parse_mode="Markdown")
    
    async def _cmd_addchat(self, message: types.Message):
        """Команда /addchat"""
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer(
                "❌ Укажите ссылку на чат.\n\n"
                "**Примеры:**\n"
                "`/addchat @channel_name`\n"
                "`/addchat https://t.me/channel_name`",
                parse_mode="Markdown"
            )
            return
        
        chat_link = args[1].strip()
        
        # Проверяем лимит чатов
        current_chats = self.parser.get_monitored_chats()
        if len(current_chats) >= settings.parser.max_chats:
            await message.answer(
                f"❌ Достигнут лимит чатов ({settings.parser.max_chats}).\n"
                "Удалите лишние чаты командой /removechat"
            )
            return
        
        await message.answer("⏳ Добавляю чат...")
        
        success = await self.parser.add_chat(chat_link)
        
        if success:
            # Сохраняем в базу данных
            await self.storage.save_monitored_chats(self.parser.get_monitored_chats())
            
            await message.answer(
                f"✅ Чат успешно добавлен для мониторинга!\n\n"
                f"🔗 Ссылка: `{chat_link}`\n"
                f"📊 Всего чатов: {len(self.parser.get_monitored_chats())}",
                parse_mode="Markdown"
            )
            
            logger.info(f"Чат {chat_link} добавлен пользователем {message.from_user.id}")
        else:
            await message.answer(
                f"❌ Не удалось добавить чат.\n\n"
                "**Возможные причины:**\n"
                "• Чат не найден или недоступен\n"
                "• Неверная ссылка\n"
                "• Чат уже добавлен\n\n"
                "Проверьте ссылку и попробуйте ещё раз.",
                parse_mode="Markdown"
            )
    
    async def _cmd_removechat(self, message: types.Message):
        """Команда /removechat"""
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer(
                "❌ Укажите ссылку на чат для удаления.\n\n"
                "**Пример:**\n"
                "`/removechat @channel_name`",
                parse_mode="Markdown"
            )
            return
        
        chat_link = args[1].strip()
        
        success = await self.parser.remove_chat(chat_link)
        
        if success:
            # Сохраняем в базу данных
            await self.storage.save_monitored_chats(self.parser.get_monitored_chats())
            
            await message.answer(
                f"✅ Чат удален из мониторинга!\n\n"
                f"🔗 Ссылка: `{chat_link}`\n"
                f"📊 Осталось чатов: {len(self.parser.get_monitored_chats())}",
                parse_mode="Markdown"
            )
            
            logger.info(f"Чат {chat_link} удален пользователем {message.from_user.id}")
        else:
            await message.answer(
                f"❌ Чат не найден в списке мониторинга.\n\n"
                "Используйте /listchats для просмотра активных чатов."
            )
    
    async def _cmd_listchats(self, message: types.Message):
        """Команда /listchats"""
        chats = self.parser.get_monitored_chats()
        
        if not chats:
            await message.answer(
                "📋 Список мониторинга пуст.\n\n"
                "Используйте /addchat для добавления чатов."
            )
            return
        
        chat_list = "📋 **Отслеживаемые чаты:**\n\n"
        
        for i, (username, info) in enumerate(chats.items(), 1):
            chat_list += f"{i}. **{info['title']}**\n"
            chat_list += f"   🔗 @{username}\n"
            chat_list += f"   📅 Добавлен: {info['added_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        
        chat_list += f"📊 **Всего чатов:** {len(chats)}/{settings.parser.max_chats}"
        
        await message.answer(chat_list, parse_mode="Markdown")
    
    async def _cmd_keywords(self, message: types.Message):
        """Команда /keywords"""
        keywords = self.parser.keywords
        
        if not keywords:
            await message.answer(
                "🔍 Ключевые слова не установлены.\n\n"
                "Используйте /setkeywords для их настройки."
            )
            return
        
        keywords_text = "🔍 **Текущие ключевые слова:**\n\n"
        for i, keyword in enumerate(keywords, 1):
            keywords_text += f"{i}. `{keyword}`\n"
        
        keywords_text += f"\n📊 **Всего:** {len(keywords)} слов"
        
        await message.answer(keywords_text, parse_mode="Markdown")
    
    async def _cmd_setkeywords(self, message: types.Message):
        """Команда /setkeywords"""
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer(
                "❌ Укажите ключевые слова через запятую.\n\n"
                "**Пример:**\n"
                "`/setkeywords биткоин, эфир, продам, куплю`",
                parse_mode="Markdown"
            )
            return
        
        keywords_str = args[1].strip()
        keywords = [kw.strip().lower() for kw in keywords_str.split(",") if kw.strip()]
        
        if not keywords:
            await message.answer("❌ Не удалось извлечь ключевые слова.")
            return
        
        self.parser.set_keywords(keywords)
        
        # Сохраняем в базу данных
        await self.storage.save_keywords(keywords)
        
        keywords_text = "✅ Ключевые слова обновлены!\n\n🔍 **Новые ключевые слова:**\n"
        for i, keyword in enumerate(keywords, 1):
            keywords_text += f"{i}. `{keyword}`\n"
        
        await message.answer(keywords_text, parse_mode="Markdown")
        
        logger.info(f"Ключевые слова обновлены пользователем {message.from_user.id}: {keywords}")
    
    async def _cmd_status(self, message: types.Message):
        """Команда /status"""
        is_running = self.parser.is_running
        chats = self.parser.get_monitored_chats()
        keywords = self.parser.keywords
        
        status_text = "📊 **Статус TgSpyBot**\n\n"
        
        # Статус парсера
        if is_running:
            status_text += "🟢 **Парсер:** Работает\n"
        else:
            status_text += "🔴 **Парсер:** Остановлен\n"
        
        # Статистика
        status_text += f"📋 **Чатов:** {len(chats)}/{settings.parser.max_chats}\n"
        status_text += f"🔍 **Ключевых слов:** {len(keywords)}\n"
        status_text += f"⏰ **Интервал проверки:** {settings.parser.check_interval} сек\n\n"
        
        # Детали по чатам
        if chats:
            status_text += "📈 **Активные чаты:**\n"
            for username, info in list(chats.items())[:3]:  # Показываем первые 3
                status_text += f"• {info['title']} (@{username})\n"
            
            if len(chats) > 3:
                status_text += f"• ... ещё {len(chats) - 3} чатов\n"
        else:
            status_text += "📭 **Чаты не добавлены**\n"
        
        # Ключевые слова
        if keywords:
            status_text += f"\n🔍 **Поиск по словам:** {', '.join(keywords[:5])}"
            if len(keywords) > 5:
                status_text += f" (+{len(keywords) - 5})"
        else:
            status_text += "\n❌ **Ключевые слова не установлены**"
        
        await message.answer(status_text, parse_mode="Markdown")
    
    async def _handle_unknown(self, message: types.Message):
        """Обработка неизвестных команд"""
        await message.answer(
            "❓ Неизвестная команда.\n\n"
            "Используйте /help для просмотра доступных команд."
        )
    
    async def send_notification(self, message_data: Dict):
        """Отправка уведомления о найденном сообщении"""
        try:
            # Форматируем уведомление
            notification = self._format_bot_notification(message_data)
            
            # Отправляем администратору
            await self.bot.send_message(
                chat_id=settings.bot.admin_user_id,
                text=notification,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
            # Отправляем в группу уведомлений (если настроена)
            if settings.notification.chat_id:
                await self.bot.send_message(
                    chat_id=settings.notification.chat_id,
                    text=notification,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                
            logger.info(f"Уведомление отправлено: {message_data['chat_title']}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
    
    def _format_bot_notification(self, message_data: Dict) -> str:
        """Форматирование уведомления для Telegram"""
        # Обрезаем длинное сообщение
        message_text = message_data['message_text']
        if len(message_text) > 300:
            message_text = message_text[:300] + "..."
        
        # Экранируем специальные символы для Markdown
        message_text = message_text.replace('`', '\\`').replace('*', '\\*').replace('_', '\\_')
        
        # Форматируем дату
        date_str = message_data['date'].strftime("%d.%m.%Y %H:%M:%S")
        
        notification = f"""🔔 **Найдено сообщение по ключевому слову!**

📢 **Чат:** {message_data['chat_title']}
🆔 **Ссылка:** https://t.me/{message_data['chat_username']}
✉️ **Сообщение:** 
```
{message_text}
```
🔍 **Найденные ключевые слова:** {', '.join(message_data['found_keywords'])}
⏰ **Время:** {date_str}"""
        
        return notification
    
    async def start(self):
        """Запуск бота"""
        logger.info("🤖 Запуск Telegram бота...")
        
        # Инициализируем хранилище
        await self.storage.initialize()
        
        # Загружаем сохраненные данные
        await self._load_saved_data()
        
        # Добавляем обработчик уведомлений в парсер
        self.parser.add_message_handler(self.send_notification)
        
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            raise
    
    async def stop(self):
        """Остановка бота"""
        logger.info("🛑 Остановка Telegram бота...")
        await self.bot.session.close()
        await self.storage.close()
    
    async def _load_saved_data(self):
        """Загрузка сохраненных данных из базы"""
        try:
            # Загружаем ключевые слова
            keywords = await self.storage.load_keywords()
            if keywords:
                self.parser.set_keywords(keywords)
                logger.info(f"Загружены ключевые слова: {keywords}")
            
            # Загружаем чаты
            chats = await self.storage.load_monitored_chats()
            if chats:
                self.parser.monitored_chats = chats
                logger.info(f"Загружены чаты: {list(chats.keys())}")
                
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}") 