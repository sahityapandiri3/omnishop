#!/bin/bash
# Backup production database using Docker (handles version mismatch)
#
# Usage: ./scripts/backup_prod_docker.sh "postgresql://user:pass@host:port/db"

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <production-database-url>"
    echo "Example: $0 'postgresql://postgres:pass@host:5432/railway'"
    exit 1
fi

PROD_URL="$1"
BACKUP_DIR="$(dirname "$0")/../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/production_${TIMESTAMP}.sql"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Parse URL
# Format: postgresql://user:password@host:port/database
DB_USER=$(echo "$PROD_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$PROD_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$PROD_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$PROD_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$PROD_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

echo "Backing up production database..."
echo "  Host: $DB_HOST:$DB_PORT"
echo "  Database: $DB_NAME"
echo "  Output: $BACKUP_FILE"

# Use Docker with PostgreSQL 17 to run pg_dump
docker run --rm \
    -e PGPASSWORD="$DB_PASS" \
    postgres:17 \
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-acl > "$BACKUP_FILE"

# Compress
gzip -f "$BACKUP_FILE"
COMPRESSED="${BACKUP_FILE}.gz"
SIZE=$(du -h "$COMPRESSED" | cut -f1)

echo "  Saved: $COMPRESSED ($SIZE)"
echo "Done!"
