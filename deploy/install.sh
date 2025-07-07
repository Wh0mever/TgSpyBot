#!/bin/bash

# ==============================================
# TgSpyBot - Автоматическая установка на VPS
# ==============================================

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Константы
TGSPYBOT_USER="tgspybot"
TGSPYBOT_HOME="/opt/tgspybot"
SYSTEMD_SERVICE="tgspybot"
NGINX_CONF_NAME="tgspybot"

echo -e "${BLUE}
╔══════════════════════════════════════════════╗
║           TgSpyBot Auto Install              ║
║         Установка на VPS сервер              ║
╚══════════════════════════════════════════════╝
${NC}"

# Функция для вывода с префиксом
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Проверка прав root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Скрипт должен запускаться с правами root (sudo)"
    fi
}

# Обновление системы
update_system() {
    log "Обновление системы..."
    
    if command -v apt &> /dev/null; then
        apt update && apt upgrade -y
        apt install -y curl wget git unzip software-properties-common
    elif command -v yum &> /dev/null; then
        yum update -y
        yum install -y curl wget git unzip epel-release
    elif command -v dnf &> /dev/null; then
        dnf update -y
        dnf install -y curl wget git unzip
    else
        error "Неподдерживаемая система пакетов"
    fi
}

# Установка Docker
install_docker() {
    log "Проверка Docker..."
    
    if ! command -v docker &> /dev/null; then
        log "Установка Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        
        # Добавляем пользователя в группу docker
        usermod -aG docker $TGSPYBOT_USER 2>/dev/null || true
        
        # Запуск Docker
        systemctl enable docker
        systemctl start docker
        
        log "Docker установлен успешно"
    else
        log "Docker уже установлен"
    fi
}

# Установка Docker Compose
install_docker_compose() {
    log "Проверка Docker Compose..."
    
    if ! command -v docker-compose &> /dev/null; then
        log "Установка Docker Compose..."
        
        # Определяем архитектуру
        ARCH=$(uname -m)
        case $ARCH in
            x86_64) DOCKER_COMPOSE_ARCH="x86_64" ;;
            aarch64) DOCKER_COMPOSE_ARCH="aarch64" ;;
            *) error "Неподдерживаемая архитектура: $ARCH" ;;
        esac
        
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${DOCKER_COMPOSE_ARCH}" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        
        log "Docker Compose установлен успешно"
    else
        log "Docker Compose уже установлен"
    fi
}

# Создание пользователя
create_user() {
    log "Создание пользователя $TGSPYBOT_USER..."
    
    if ! id "$TGSPYBOT_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash $TGSPYBOT_USER
        log "Пользователь $TGSPYBOT_USER создан"
    else
        log "Пользователь $TGSPYBOT_USER уже существует"
    fi
}

# Создание директорий
create_directories() {
    log "Создание директорий..."
    
    mkdir -p $TGSPYBOT_HOME/{data,logs,backups}
    chown -R $TGSPYBOT_USER:$TGSPYBOT_USER $TGSPYBOT_HOME
    chmod 755 $TGSPYBOT_HOME
    chmod 700 $TGSPYBOT_HOME/data  # Защищенная директория для данных
    
    log "Директории созданы"
}

# Загрузка кода
download_code() {
    log "Загрузка кода TgSpyBot..."
    
    # Если есть git репозиторий
    if [[ -n "${GITHUB_REPO:-}" ]]; then
        if [[ -d "$TGSPYBOT_HOME/.git" ]]; then
            cd $TGSPYBOT_HOME
            sudo -u $TGSPYBOT_USER git pull
        else
            sudo -u $TGSPYBOT_USER git clone $GITHUB_REPO $TGSPYBOT_HOME
        fi
    else
        # Копируем локальные файлы
        if [[ -f "$(dirname "$0")/../main.py" ]]; then
            cp -r $(dirname "$0")/../* $TGSPYBOT_HOME/
            chown -R $TGSPYBOT_USER:$TGSPYBOT_USER $TGSPYBOT_HOME
        else
            warning "Код не найден. Скопируйте файлы в $TGSPYBOT_HOME вручную"
        fi
    fi
    
    log "Код загружен"
}

# Настройка окружения
setup_environment() {
    log "Настройка окружения..."
    
    cd $TGSPYBOT_HOME
    
    # Создаем .env файл если его нет
    if [[ ! -f ".env" ]]; then
        if [[ -f "env.example" ]]; then
            cp env.example .env
            warning "Создан .env файл из примера. ОБЯЗАТЕЛЬНО отредактируйте его!"
        else
            error ".env файл не найден и env.example не существует"
        fi
    fi
    
    # Устанавливаем права доступа
    chmod 600 .env
    chown $TGSPYBOT_USER:$TGSPYBOT_USER .env
    
    log "Окружение настроено"
}

# Настройка файрвола
setup_firewall() {
    log "Настройка файрвола..."
    
    if command -v ufw &> /dev/null; then
        # UFW (Ubuntu/Debian)
        ufw --force enable
        ufw default deny incoming
        ufw default allow outgoing
        ufw allow 22/tcp    # SSH
        ufw allow 80/tcp    # HTTP (если нужен)
        ufw allow 443/tcp   # HTTPS (если нужен)
        # Redis порт НЕ открываем наружу для безопасности
        log "UFW настроен"
    elif command -v firewall-cmd &> /dev/null; then
        # firewalld (CentOS/RHEL)
        systemctl enable firewalld
        systemctl start firewalld
        firewall-cmd --permanent --zone=public --add-service=ssh
        firewall-cmd --reload
        log "Firewalld настроен"
    else
        warning "Файрвол не настроен - установите ufw или firewalld"
    fi
}

# Создание systemd service
create_systemd_service() {
    log "Создание systemd service..."
    
    cat > /etc/systemd/system/${SYSTEMD_SERVICE}.service << EOF
[Unit]
Description=TgSpyBot - Telegram Chat Parser
After=network.target docker.service
Requires=docker.service

[Service]
Type=forking
User=$TGSPYBOT_USER
Group=$TGSPYBOT_USER
WorkingDirectory=$TGSPYBOT_HOME
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart
Restart=always
RestartSec=10

# Безопасность
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=$TGSPYBOT_HOME

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SYSTEMD_SERVICE
    
    log "Systemd service создан"
}

# Настройка логротации
setup_logrotate() {
    log "Настройка ротации логов..."
    
    cat > /etc/logrotate.d/tgspybot << EOF
$TGSPYBOT_HOME/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $TGSPYBOT_USER $TGSPYBOT_USER
    postrotate
        systemctl reload $SYSTEMD_SERVICE >/dev/null 2>&1 || true
    endscript
}
EOF
    
    log "Ротация логов настроена"
}

# Создание backup скрипта
create_backup_script() {
    log "Создание backup скрипта..."
    
    cat > $TGSPYBOT_HOME/backup.sh << 'EOF'
#!/bin/bash

# Backup скрипт для TgSpyBot
BACKUP_DIR="/opt/tgspybot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="tgspybot_backup_${DATE}.tar.gz"

# Создаем backup
tar -czf "${BACKUP_DIR}/${BACKUP_FILE}" \
    --exclude='logs' \
    --exclude='backups' \
    --exclude='.git' \
    -C /opt/tgspybot .

# Удаляем старые backup'ы (старше 7 дней)
find $BACKUP_DIR -name "tgspybot_backup_*.tar.gz" -mtime +7 -delete

echo "Backup создан: ${BACKUP_FILE}"
EOF

    chmod +x $TGSPYBOT_HOME/backup.sh
    chown $TGSPYBOT_USER:$TGSPYBOT_USER $TGSPYBOT_HOME/backup.sh
    
    # Добавляем в crontab
    (crontab -u $TGSPYBOT_USER -l 2>/dev/null; echo "0 2 * * * $TGSPYBOT_HOME/backup.sh") | crontab -u $TGSPYBOT_USER -
    
    log "Backup скрипт создан и добавлен в crontab"
}

# Установка мониторинга
install_monitoring() {
    log "Настройка мониторинга..."
    
    # Создаем health check скрипт
    cat > $TGSPYBOT_HOME/health_check.sh << 'EOF'
#!/bin/bash

# Health check для TgSpyBot
CONTAINER_NAME="tgspybot-app"

if docker ps | grep -q $CONTAINER_NAME; then
    echo "OK: TgSpyBot container is running"
    exit 0
else
    echo "ERROR: TgSpyBot container is not running"
    exit 1
fi
EOF

    chmod +x $TGSPYBOT_HOME/health_check.sh
    chown $TGSPYBOT_USER:$TGSPYBOT_USER $TGSPYBOT_HOME/health_check.sh
    
    log "Мониторинг настроен"
}

# Финальная настройка
final_setup() {
    log "Финальная настройка..."
    
    cd $TGSPYBOT_HOME
    
    # Собираем Docker образ
    sudo -u $TGSPYBOT_USER docker-compose build
    
    log "Docker образ собран"
}

# Вывод инструкций
show_instructions() {
    echo -e "${GREEN}
╔══════════════════════════════════════════════╗
║           Установка завершена!               ║
╚══════════════════════════════════════════════╝
${NC}"

    echo -e "${YELLOW}Следующие шаги:${NC}"
    echo -e "1. Отредактируйте файл конфигурации:"
    echo -e "   ${BLUE}sudo -u $TGSPYBOT_USER nano $TGSPYBOT_HOME/.env${NC}"
    echo
    echo -e "2. Запустите TgSpyBot:"
    echo -e "   ${BLUE}sudo systemctl start $SYSTEMD_SERVICE${NC}"
    echo
    echo -e "3. Проверьте статус:"
    echo -e "   ${BLUE}sudo systemctl status $SYSTEMD_SERVICE${NC}"
    echo
    echo -e "4. Просмотр логов:"
    echo -e "   ${BLUE}sudo -u $TGSPYBOT_USER docker-compose logs -f${NC}"
    echo
    echo -e "${YELLOW}Полезные команды:${NC}"
    echo -e "• Остановка: ${BLUE}sudo systemctl stop $SYSTEMD_SERVICE${NC}"
    echo -e "• Перезапуск: ${BLUE}sudo systemctl restart $SYSTEMD_SERVICE${NC}"
    echo -e "• Обновление: ${BLUE}cd $TGSPYBOT_HOME && sudo -u $TGSPYBOT_USER docker-compose pull && sudo systemctl restart $SYSTEMD_SERVICE${NC}"
    echo -e "• Backup: ${BLUE}sudo -u $TGSPYBOT_USER $TGSPYBOT_HOME/backup.sh${NC}"
    echo
    echo -e "${RED}ВАЖНО: Обязательно настройте .env файл перед запуском!${NC}"
}

# Основная функция
main() {
    check_root
    log "Начало установки TgSpyBot на VPS..."
    
    update_system
    install_docker
    install_docker_compose
    create_user
    create_directories
    download_code
    setup_environment
    setup_firewall
    create_systemd_service
    setup_logrotate
    create_backup_script
    install_monitoring
    final_setup
    
    show_instructions
    
    log "Установка TgSpyBot завершена успешно!"
}

# Обработка аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --github-repo)
            GITHUB_REPO="$2"
            shift 2
            ;;
        --help)
            echo "Использование: $0 [--github-repo URL]"
            echo "  --github-repo URL  Ссылка на Git репозиторий"
            exit 0
            ;;
        *)
            error "Неизвестный аргумент: $1"
            ;;
    esac
done

# Запуск установки
main "$@" 