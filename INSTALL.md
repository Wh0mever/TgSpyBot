# 🚀 Установка и настройка TgSpyBot

## 📋 Системные требования

- **Python 3.8+**
- **Redis Server** (для хранения данных)
- **Telegram API credentials**
- **Telegram Bot Token**

## 📦 Установка зависимостей

### 1. Python зависимости

```bash
# Установка всех зависимостей
pip install -r requirements.txt

# Или установка вручную основных пакетов:
pip install telethon==1.35.0 aiogram==3.4.1 redis==5.0.1 loguru==0.7.2 pydantic==2.5.2 python-dotenv==1.0.0
```

### 2. Redis Server

#### Для Ubuntu/Debian:
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Проверка работы
redis-cli ping
# Должен ответить: PONG
```

#### Для CentOS/RHEL:
```bash
sudo yum install epel-release
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis
```

#### Для Windows:
```bash
# Используйте Docker или WSL с Ubuntu
docker run -d -p 6379:6379 --name redis redis:latest

# Или установите Redis для Windows
# https://github.com/MicrosoftArchive/redis/releases
```

#### Для macOS:
```bash
brew install redis
brew services start redis
```

## 🔑 Получение необходимых токенов

### 1. Telegram API (обязательно!)

1. Зайдите на https://my.telegram.org
2. Войдите в свой аккаунт
3. Перейдите в "API Development Tools"
4. Создайте новое приложение:
   - **App title:** TgSpyBot
   - **Short name:** tgspybot
   - **Platform:** Desktop
5. Получите:
   - **api_id** (числовой ID)
   - **api_hash** (строка хеша)

### 2. Telegram Bot Token

1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Укажите имя бота: `TgSpyBot`
4. Укажите username: `your_tgspybot` (должен быть уникальным)
5. Получите **Bot Token**

### 3. Ваш Telegram User ID

1. Найдите @userinfobot в Telegram
2. Отправьте `/start`
3. Получите ваш **User ID** (число)

### 4. ID чата для уведомлений (опционально)

Для личных сообщений:
- Используйте ваш User ID

Для группы:
1. Добавьте бота в группу
2. Дайте ему права администратора
3. Найдите @userinfobot
4. Добавьте его в группу и получите **Chat ID**

## ⚙️ Настройка конфигурации

### 1. Создание файла настроек

```bash
# Скопируйте пример настроек
cp env.example .env

# Отредактируйте файл .env
nano .env
```

### 2. Заполнение .env файла

```bash
# =================================
# TELEGRAM PARSER CONFIGURATION
# =================================

# Telegram API credentials (ОБЯЗАТЕЛЬНО!)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+1234567890

# Bot configuration (ОБЯЗАТЕЛЬНО!)
BOT_TOKEN=123456789:ABCDEF1234567890abcdef1234567890
BOT_PASSWORD=your_secure_password_123
ADMIN_USER_ID=123456789

# Parser settings
CHECK_INTERVAL=60  # секунды между проверками
MAX_CHATS=15      # максимум чатов для мониторинга
KEYWORDS="продам, куплю, обмен, биткоин, эфир"

# Database settings
DATABASE_TYPE=redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/tgspybot.log

# Security
ENCRYPTION_KEY=your_32_character_encryption_key
SESSION_ENCRYPTION=true

# Monitoring and notifications
NOTIFICATION_CHAT_ID=123456789  # Ваш User ID или ID группы
ERROR_NOTIFICATION=true

# Rate limiting
API_RATE_LIMIT=30
FLOOD_WAIT_THRESHOLD=300

# Docker settings
TZ=Europe/Moscow
```

## 🏃‍♂️ Запуск приложения

### 1. Первый запуск (авторизация)

```bash
# Запуск полной версии с ботом
python main.py
```

При первом запуске:
1. Введите код подтверждения из SMS
2. Если включена 2FA - введите пароль от аккаунта Telegram

### 2. Проверка работы

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Введите пароль (из BOT_PASSWORD)
4. Попробуйте команды:
   ```
   /help
   /status
   /addchat @durov
   /setkeywords тест, проверка
   ```

## 🔧 Проверка настроек

### Проверка Redis

```bash
# Проверка подключения
redis-cli ping

# Просмотр данных бота
redis-cli
> KEYS tgspybot:*
> GET tgspybot:keywords
> exit
```

### Проверка логов

```bash
# Просмотр логов в реальном времени
tail -f logs/tgspybot.log

# Просмотр найденных сообщений
tail -f data/found_messages.log
```

### Проверка session файла

```bash
# Session файл должен создаться автоматически
ls -la data/telegram_session.session
```

## 🐛 Устранение проблем

### Ошибка "API_ID not found"
```bash
# Проверьте .env файл
cat .env | grep TELEGRAM_API_ID
# Должно показать: TELEGRAM_API_ID=ваш_id
```

### Ошибка подключения к Redis
```bash
# Проверьте статус Redis
sudo systemctl status redis-server

# Перезапустите Redis
sudo systemctl restart redis-server

# Проверьте порт
netstat -tlnp | grep 6379
```

### Ошибка "Phone number invalid"
- Укажите номер в международном формате: `+1234567890`
- Убедитесь что номер зарегистрирован в Telegram

### Ошибка "Bot token invalid"
- Проверьте BOT_TOKEN в .env
- Создайте нового бота через @BotFather

### FloodWaitError
- Увеличьте CHECK_INTERVAL в .env
- Уменьшите количество отслеживаемых чатов
- Подождите указанное время

### Чат не найден
- Убедитесь что чат публичный
- Проверьте правильность username
- Попробуйте сначала открыть чат в своём Telegram

## 📊 Мониторинг работы

### Просмотр статистики в Redis

```bash
redis-cli
> HGETALL tgspybot:stats
> KEYS tgspybot:found_messages:*
```

### Структура данных

```
tgspybot:keywords           - ключевые слова
tgspybot:monitored_chats    - отслеживаемые чаты
tgspybot:settings           - настройки
tgspybot:stats              - статистика
tgspybot:found_messages:*   - найденные сообщения
```

## 🔒 Безопасность

### Важные файлы для защиты:
- `.env` - содержит токены и пароли
- `data/telegram_session.session` - авторизация Telegram
- `logs/` - могут содержать чувствительную информацию

### Рекомендации:
1. Используйте сильные пароли
2. Ограничьте доступ к серверу
3. Регулярно проверяйте логи
4. Используйте отдельный Telegram аккаунт для парсинга
5. Настройте файрвол для Redis (порт 6379)

## 🚀 Следующие шаги

После успешной установки:

1. **Добавьте чаты для мониторинга:** `/addchat @channel_name`
2. **Настройте ключевые слова:** `/setkeywords слово1, слово2`
3. **Проверьте статус:** `/status`
4. **Настройте автозапуск** (см. раздел Docker)
5. **Подготовьте второй VPS** для отказоустойчивости

---

**Поддержка:** При возникновении проблем проверьте логи в `logs/tgspybot.log` 