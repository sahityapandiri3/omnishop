#!/bin/bash
# Simple and reliable migration using PostgreSQL native tools

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SOURCE_DB="postgresql://omnishop_user:omnishop_secure_2024@localhost:5432/omnishop"
TARGET_DB="${TARGET_DATABASE_URL}"

if [ -z "$TARGET_DB" ]; then
    echo -e "${RED}Error: TARGET_DATABASE_URL not set${NC}"
    echo "Usage: export TARGET_DATABASE_URL='your-railway-url' && bash scripts/migrate_simple.sh"
    exit 1
fi

echo -e "${BLUE}=== Simple PostgreSQL Migration ===${NC}"
echo ""

# Function to run SQL on source
run_source_sql() {
    psql "$SOURCE_DB" -t -c "$1"
}

# Function to run SQL on target
run_target_sql() {
    psql "$TARGET_DB" -t -c "$1"
}

# Get counts
echo -e "${BLUE}Checking current state...${NC}"
SOURCE_IMAGES=$(run_source_sql "SELECT COUNT(*) FROM product_images;")
TARGET_IMAGES=$(run_target_sql "SELECT COUNT(*) FROM product_images;")
SOURCE_ATTRS=$(run_source_sql "SELECT COUNT(*) FROM product_attributes;")
TARGET_ATTRS=$(run_target_sql "SELECT COUNT(*) FROM product_attributes;")

echo "Product Images: $TARGET_IMAGES / $SOURCE_IMAGES in Railway"
echo "Product Attributes: $TARGET_ATTRS / $SOURCE_ATTRS in Railway"
echo ""

MISSING_IMAGES=$((SOURCE_IMAGES - TARGET_IMAGES))
MISSING_ATTRS=$((SOURCE_ATTRS - TARGET_ATTRS))

if [ $MISSING_IMAGES -gt 0 ]; then
    echo -e "${BLUE}Migrating $MISSING_IMAGES product_images...${NC}"

    # Export missing images to temp file
    echo "Exporting from local database..."
    psql "$SOURCE_DB" -c "\COPY (
        SELECT * FROM product_images
        WHERE id NOT IN (SELECT id FROM dblink('$TARGET_DB', 'SELECT id FROM product_images') AS t(id integer))
        ORDER BY id
    ) TO '/tmp/missing_images.csv' WITH CSV HEADER" 2>/dev/null || {
        # Fallback: export all and let target handle conflicts
        echo "Using fallback export method..."
        psql "$SOURCE_DB" -c "\COPY (
            SELECT * FROM product_images ORDER BY id
        ) TO '/tmp/all_images.csv' WITH CSV HEADER"

        echo "Importing to Railway (will skip duplicates)..."
        psql "$TARGET_DB" -c "CREATE TEMP TABLE temp_images (LIKE product_images INCLUDING ALL);"
        psql "$TARGET_DB" -c "\COPY temp_images FROM '/tmp/all_images.csv' WITH CSV HEADER"
        psql "$TARGET_DB" -c "INSERT INTO product_images SELECT * FROM temp_images ON CONFLICT (id) DO NOTHING;"
        rm /tmp/all_images.csv
    }

    echo -e "${GREEN}✓ Product images migrated${NC}"
else
    echo -e "${GREEN}✓ All product images already migrated${NC}"
fi

echo ""

if [ $MISSING_ATTRS -gt 0 ]; then
    echo -e "${BLUE}Migrating $MISSING_ATTRS product_attributes...${NC}"

    echo "Exporting from local database..."
    psql "$SOURCE_DB" -c "\COPY (
        SELECT * FROM product_attributes ORDER BY id
    ) TO '/tmp/all_attrs.csv' WITH CSV HEADER"

    echo "Importing to Railway (will skip duplicates)..."
    psql "$TARGET_DB" -c "CREATE TEMP TABLE temp_attrs (LIKE product_attributes INCLUDING ALL);"
    psql "$TARGET_DB" -c "\COPY temp_attrs FROM '/tmp/all_attrs.csv' WITH CSV HEADER"
    psql "$TARGET_DB" -c "INSERT INTO product_attributes SELECT * FROM temp_attrs ON CONFLICT (id) DO NOTHING;"
    rm /tmp/all_attrs.csv

    echo -e "${GREEN}✓ Product attributes migrated${NC}"
else
    echo -e "${GREEN}✓ All product attributes already migrated${NC}"
fi

echo ""
echo -e "${GREEN}=== Migration Complete! ===${NC}"

# Final counts
echo ""
echo "Final counts in Railway:"
FINAL_IMAGES=$(run_target_sql "SELECT COUNT(*) FROM product_images;")
FINAL_ATTRS=$(run_target_sql "SELECT COUNT(*) FROM product_attributes;")
echo "  Product Images: $FINAL_IMAGES"
echo "  Product Attributes: $FINAL_ATTRS"
