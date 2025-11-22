#!/bin/bash
# Fast migration for product_attributes only using PostgreSQL COPY

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SOURCE_DB="postgresql://omnishop_user:omnishop_secure_2024@localhost:5432/omnishop"
TARGET_DB="${TARGET_DATABASE_URL}"

if [ -z "$TARGET_DB" ]; then
    echo -e "${RED}Error: TARGET_DATABASE_URL not set${NC}"
    echo ""
    echo "Usage:"
    echo "  export TARGET_DATABASE_URL='your-railway-url'"
    echo "  bash scripts/migrate_attributes_fast.sh"
    exit 1
fi

echo -e "${BLUE}=== Fast Product Attributes Migration ===${NC}"
echo ""

# Get counts
echo -e "${BLUE}Checking current state...${NC}"
SOURCE_COUNT=$(psql "$SOURCE_DB" -t -c "SELECT COUNT(*) FROM product_attributes;" | tr -d ' ')
TARGET_COUNT=$(psql "$TARGET_DB" -t -c "SELECT COUNT(*) FROM product_attributes;" | tr -d ' ')

echo "Source (local): $SOURCE_COUNT attributes"
echo "Target (Railway): $TARGET_COUNT attributes"
echo ""

MISSING=$((SOURCE_COUNT - TARGET_COUNT))

if [ $MISSING -le 0 ]; then
    echo -e "${GREEN}✓ All product_attributes already migrated!${NC}"
    exit 0
fi

echo -e "${YELLOW}Need to migrate: $MISSING attributes${NC}"
echo ""

# Confirm
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ] && [ "$confirm" != "y" ]; then
    echo "Migration cancelled"
    exit 0
fi

echo ""
echo -e "${BLUE}Step 1: Exporting from local database...${NC}"

# Export all attributes to CSV
psql "$SOURCE_DB" -c "\COPY (
    SELECT * FROM product_attributes ORDER BY id
) TO '/tmp/product_attributes.csv' WITH (FORMAT CSV, HEADER true)"

FILE_SIZE=$(du -h /tmp/product_attributes.csv | cut -f1)
echo -e "${GREEN}✓ Exported to /tmp/product_attributes.csv ($FILE_SIZE)${NC}"

echo ""
echo -e "${BLUE}Step 2: Importing to Railway...${NC}"
echo "This may take a few minutes..."

# Create temp table, import, then insert with conflict handling
psql "$TARGET_DB" <<EOF
-- Create temporary table
CREATE TEMP TABLE temp_product_attributes (LIKE product_attributes INCLUDING ALL);

-- Import CSV into temp table
\COPY temp_product_attributes FROM '/tmp/product_attributes.csv' WITH (FORMAT CSV, HEADER true)

-- Insert into real table (skip duplicates)
INSERT INTO product_attributes
SELECT * FROM temp_product_attributes
ON CONFLICT (id) DO NOTHING;

-- Update sequence
SELECT setval('product_attributes_id_seq', (SELECT MAX(id) FROM product_attributes));
EOF

echo -e "${GREEN}✓ Import completed${NC}"

# Cleanup
rm /tmp/product_attributes.csv
echo ""
echo -e "${BLUE}Step 3: Verifying...${NC}"

# Final count
FINAL_COUNT=$(psql "$TARGET_DB" -t -c "SELECT COUNT(*) FROM product_attributes;" | tr -d ' ')
NEWLY_ADDED=$((FINAL_COUNT - TARGET_COUNT))

echo ""
echo -e "${GREEN}=== Migration Complete! ===${NC}"
echo ""
echo "Results:"
echo "  Before: $TARGET_COUNT attributes"
echo "  After:  $FINAL_COUNT attributes"
echo "  Added:  $NEWLY_ADDED attributes"
echo ""

if [ $FINAL_COUNT -eq $SOURCE_COUNT ]; then
    echo -e "${GREEN}✓ All $SOURCE_COUNT product_attributes successfully migrated!${NC}"
else
    STILL_MISSING=$((SOURCE_COUNT - FINAL_COUNT))
    echo -e "${YELLOW}⚠ Warning: $STILL_MISSING attributes still missing${NC}"
    echo "You can re-run this script to retry"
fi
