#!/bin/bash

# ==============================================
# TgSpyBot - Скрипт управления
# ==============================================

# Константы
TGSPYBOT_USER="tgspybot"
TGSPYBOT_HOME="/opt/tgspybot"
SYSTEMD_SERVICE="tgspybot"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Функции вывода
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

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Проверка прав
check_permissions() {
    if [[ $EUID -ne 0 ]]; then
        error "Скрипт должен запускаться с правами root (sudo)"
    fi
}

# Функция статуса
show_status() {
    echo -e "${BLUE}
╔══════════════════════════════════════════════╗
║                TgSpyBot Status               ║
╚══════════════════════════════════════════════╝
${NC}"

    # Systemd status
    echo -e "${YELLOW}Systemd Service:${NC}"
    systemctl is-active --quiet $SYSTEMD_SERVICE && echo -e "  ${GREEN}✓ Активен${NC}" || echo -e "  ${RED}✗ Неактивен${NC}"
    systemctl is-enabled --quiet $SYSTEMD_SERVICE && echo -e "  ${GREEN}✓ Включен в автозапуск${NC}" || echo -e "  ${RED}✗ Автозапуск отключен${NC}"
    
    # Docker containers
    echo -e "\n${YELLOW}Docker Containers:${NC}"
    cd $TGSPYBOT_HOME
    sudo -u $TGSPYBOT_USER docker-compose ps
    
    # Disk usage
    echo -e "\n${YELLOW}Использование диска:${NC}"
    du -sh $TGSPYBOT_HOME/{data,logs,backups} 2>/dev/null | while read size path; do
        echo "  $(basename $path): $size"
    done
    
    # Redis status
    echo -e "\n${YELLOW}Redis:${NC}"
    if sudo -u $TGSPYBOT_USER docker exec tgspybot-redis redis-cli ping &>/dev/null; then
        echo -e "  ${GREEN}✓ Redis доступен${NC}"
        redis_info=$(sudo -u $TGSPYBOT_USER docker exec tgspybot-redis redis-cli info memory | grep used_memory_human)
        echo "  Память: ${redis_info#*:}"
    else
        echo -e "  ${RED}✗ Redis недоступен${NC}"
    fi
    
    # Recent logs
    echo -e "\n${YELLOW}Последние логи:${NC}"
    sudo -u $TGSPYBOT_USER docker-compose logs --tail=5 tgspybot 2>/dev/null || echo "  Логи недоступны"
}

# Запуск
start_service() {
    log "Запуск TgSpyBot..."
    
    if systemctl is-active --quiet $SYSTEMD_SERVICE; then
        warning "Сервис уже запущен"
        return 0
    fi
    
    systemctl start $SYSTEMD_SERVICE
    
    # Ждем запуска
    sleep 5
    
    if systemctl is-active --quiet $SYSTEMD_SERVICE; then
        log "TgSpyBot успешно запущен"
    else
        error "Не удалось запустить TgSpyBot"
    fi
}

# Остановка
stop_service() {
    log "Остановка TgSpyBot..."
    
    if ! systemctl is-active --quiet $SYSTEMD_SERVICE; then
        warning "Сервис уже остановлен"
        return 0
    fi
    
    systemctl stop $SYSTEMD_SERVICE
    
    # Принудительная остановка контейнеров если нужно
    cd $TGSPYBOT_HOME
    sudo -u $TGSPYBOT_USER docker-compose down --timeout 30
    
    log "TgSpyBot остановлен"
}

# Перезапуск
restart_service() {
    log "Перезапуск TgSpyBot..."
    stop_service
    sleep 2
    start_service
}

# Просмотр логов
show_logs() {
    local lines=${1:-50}
    local follow=${2:-false}
    
    cd $TGSPYBOT_HOME
    
    if [[ "$follow" == "true" ]]; then
        log "Просмотр логов в реальном времени (Ctrl+C для выхода)..."
        sudo -u $TGSPYBOT_USER docker-compose logs -f --tail=$lines
    else
        log "Последние $lines строк логов:"
        sudo -u $TGSPYBOT_USER docker-compose logs --tail=$lines
    fi
}

# Обновление
update_service() {
    log "Обновление TgSpyBot..."
    
    cd $TGSPYBOT_HOME
    
    # Создаем backup перед обновлением
    sudo -u $TGSPYBOT_USER ./backup.sh
    
    # Останавливаем сервис
    stop_service
    
    # Обновляем код (если есть git)
    if [[ -d ".git" ]]; then
        log "Обновление кода из Git..."
        sudo -u $TGSPYBOT_USER git pull
    else
        warning "Git репозиторий не найден, обновите код вручную"
    fi
    
    # Пересобираем образы
    log "Пересборка Docker образов..."
    sudo -u $TGSPYBOT_USER docker-compose build --no-cache
    
    # Запускаем сервис
    start_service
    
    log "Обновление завершено"
}

# Создание backup
create_backup() {
    log "Создание backup..."
    
    cd $TGSPYBOT_HOME
    
    if [[ -f "backup.sh" ]]; then
        sudo -u $TGSPYBOT_USER ./backup.sh
        log "Backup создан"
    else
        error "Backup скрипт не найден"
    fi
}

# Восстановление из backup
restore_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        echo "Доступные backup файлы:"
        ls -la $TGSPYBOT_HOME/backups/tgspybot_backup_*.tar.gz 2>/dev/null || echo "Backup файлы не найдены"
        error "Укажите файл backup для восстановления"
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        error "Backup файл не найден: $backup_file"
    fi
    
    log "Восстановление из backup: $backup_file"
    
    # Останавливаем сервис
    stop_service
    
    # Создаем временную директорию
    temp_dir="/tmp/tgspybot_restore_$$"
    mkdir -p $temp_dir
    
    # Извлекаем backup
    tar -xzf "$backup_file" -C $temp_dir
    
    # Сохраняем текущие данные
    mv $TGSPYBOT_HOME $TGSPYBOT_HOME.backup.$(date +%Y%m%d_%H%M%S)
    
    # Восстанавливаем из backup
    mv $temp_dir $TGSPYBOT_HOME
    chown -R $TGSPYBOT_USER:$TGSPYBOT_USER $TGSPYBOT_HOME
    
    # Запускаем сервис
    start_service
    
    log "Восстановление завершено"
}

# Очистка логов
clean_logs() {
    log "Очистка старых логов..."
    
    # Очищаем Docker логи
    cd $TGSPYBOT_HOME
    sudo -u $TGSPYBOT_USER docker-compose down
    docker system prune -f
    
    # Очищаем файловые логи старше 30 дней
    find $TGSPYBOT_HOME/logs -name "*.log*" -mtime +30 -delete
    
    # Запускаем сервис обратно
    start_service
    
    log "Очистка логов завершена"
}

# Проверка конфигурации
check_config() {
    log "Проверка конфигурации..."
    
    cd $TGSPYBOT_HOME
    
    # Проверяем .env файл
    if [[ ! -f ".env" ]]; then
        error ".env файл не найден"
    fi
    
    # Проверяем основные переменные
    source .env
    
    local errors=0
    
    [[ -z "$TELEGRAM_API_ID" ]] && { error "TELEGRAM_API_ID не настроен"; ((errors++)); }
    [[ -z "$TELEGRAM_API_HASH" ]] && { error "TELEGRAM_API_HASH не настроен"; ((errors++)); }
    [[ -z "$BOT_TOKEN" ]] && { error "BOT_TOKEN не настроен"; ((errors++)); }
    [[ -z "$ADMIN_USER_ID" ]] && { error "ADMIN_USER_ID не настроен"; ((errors++)); }
    
    if [[ $errors -eq 0 ]]; then
        log "Конфигурация корректна"
    else
        error "Найдено $errors ошибок в конфигурации"
    fi
}

# Health check
health_check() {
    cd $TGSPYBOT_HOME
    
    if [[ -f "health_check.sh" ]]; then
        sudo -u $TGSPYBOT_USER ./health_check.sh
    else
        error "Health check скрипт не найден"
    fi
}

# Показать помощь
show_help() {
    echo -e "${BLUE}
╔══════════════════════════════════════════════╗
║            TgSpyBot Management               ║
╚══════════════════════════════════════════════╝
${NC}"

    echo "Использование: $0 <команда> [параметры]"
    echo
    echo "Команды:"
    echo "  status                    - показать статус сервиса"
    echo "  start                     - запустить TgSpyBot"
    echo "  stop                      - остановить TgSpyBot"
    echo "  restart                   - перезапустить TgSpyBot"
    echo "  logs [количество]         - показать логи (по умолчанию 50 строк)"
    echo "  logs-follow [количество]  - показать логи в реальном времени"
    echo "  update                    - обновить TgSpyBot"
    echo "  backup                    - создать backup"
    echo "  restore <файл>            - восстановить из backup"
    echo "  clean-logs               - очистить старые логи"
    echo "  check-config             - проверить конфигурацию"
    echo "  health                   - проверка работоспособности"
    echo "  help                     - показать эту справку"
    echo
    echo "Примеры:"
    echo "  $0 status"
    echo "  $0 logs 100"
    echo "  $0 logs-follow"
    echo "  $0 restore /opt/tgspybot/backups/tgspybot_backup_20240101_120000.tar.gz"
}

# Основная функция
main() {
    local command="$1"
    shift
    
    case "$command" in
        "status")
            show_status
            ;;
        "start")
            check_permissions
            start_service
            ;;
        "stop")
            check_permissions
            stop_service
            ;;
        "restart")
            check_permissions
            restart_service
            ;;
        "logs")
            show_logs "$1" false
            ;;
        "logs-follow")
            show_logs "$1" true
            ;;
        "update")
            check_permissions
            update_service
            ;;
        "backup")
            check_permissions
            create_backup
            ;;
        "restore")
            check_permissions
            restore_backup "$1"
            ;;
        "clean-logs")
            check_permissions
            clean_logs
            ;;
        "check-config")
            check_config
            ;;
        "health")
            health_check
            ;;
        "help"|"--help"|"-h"|"")
            show_help
            ;;
        *)
            error "Неизвестная команда: $command. Используйте '$0 help' для справки."
            ;;
    esac
}

# Запуск
main "$@" 