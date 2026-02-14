#!/bin/bash
set -e

# Настройки
BACKUP_DIR="/opt/hackathon/backups/postgres"
LOG_FILE="/opt/hackathon/logs/backup.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y-%m-%d)
MAX_BACKUPS=7  # Храним последние 7 дней

# Загружаем переменные окружения
source /opt/hackathon/.env

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Создаём директорию если не существует
mkdir -p "$BACKUP_DIR"

# === БЭКАП БАЗЫ ДАННЫХ ===
log "🗄️ Начинаем бэкап базы данных..."

BACKUP_FILE="$BACKUP_DIR/db_${DATE}_${TIMESTAMP}.sql.gz"

# Делаем дамп базы и сжимаем
if docker exec hackathon-db pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "✅ Бэкап создан: $BACKUP_FILE (размер: $BACKUP_SIZE)"
else
    log "❌ ОШИБКА при создании бэкапа!"
    exit 1
fi

# === БЭКАП КОНФИГОВ ===
CONFIG_BACKUP="$BACKUP_DIR/configs_${DATE}_${TIMESTAMP}.tar.gz"
tar -czf "$CONFIG_BACKUP" \
    -C /opt/hackathon \
    .env docker-compose.yml Caddyfile \
    2>/dev/null || true

log "📦 Конфиги сохранены: $CONFIG_BACKUP"

# === РОТАЦИЯ СТАРЫХ БЭКАПОВ ===
log "🧹 Удаление старых бэкапов (храним последние $MAX_BACKUPS)..."

# Удаляем старые бэкапы БД
OLD_DB_BACKUPS=$(ls -t "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)))
if [ -n "$OLD_DB_BACKUPS" ]; then
    echo "$OLD_DB_BACKUPS" | xargs rm -f
    log "🗑️ Удалено старых бэкапов БД: $(echo "$OLD_DB_BACKUPS" | wc -l)"
fi

# Удаляем старые бэкапы конфигов
OLD_CONFIG_BACKUPS=$(ls -t "$BACKUP_DIR"/configs_*.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)))
if [ -n "$OLD_CONFIG_BACKUPS" ]; then
    echo "$OLD_CONFIG_BACKUPS" | xargs rm -f
    log "🗑️ Удалено старых бэкапов конфигов: $(echo "$OLD_CONFIG_BACKUPS" | wc -l)"
fi

# === СТАТИСТИКА ===
TOTAL_BACKUPS=$(ls -1 "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "📊 Всего бэкапов: $TOTAL_BACKUPS | Занято места: $TOTAL_SIZE"
log "✅ Бэкап завершён успешно"

echo "---" >> "$LOG_FILE"
