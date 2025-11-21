#!/usr/bin/env python3
"""Check product sources in both databases"""
import os
import sys
sys.path.insert(0, 'api')

from sqlalchemy import create_engine, text

# Local database
local_db = "postgresql://omnishop_user:omnishop_secure_2024@localhost:5432/omnishop"

# Railway database (get from environment)
railway_db = os.environ.get('TARGET_DATABASE_URL')

if not railway_db:
    print("❌ Please set TARGET_DATABASE_URL environment variable")
    print("   export TARGET_DATABASE_URL='your-railway-url'")
    sys.exit(1)

print("🔍 Checking product sources and counts...\n")
print("=" * 70)

# Check local
print("\n📍 LOCAL DATABASE:")
print("-" * 70)
local_engine = create_engine(local_db)
with local_engine.connect() as conn:
    # Total products
    total = conn.execute(text("SELECT COUNT(*) FROM products WHERE is_available = true")).scalar()
    print(f"Total products: {total}")

    # Sofas by source
    print("\n🛋️  Sofas by source:")
    result = conn.execute(text("""
        SELECT source_website, COUNT(*) as count
        FROM products
        WHERE is_available = true
        AND (name ~* '\\ysofa\\y' OR name ~* '\\ycouch\\y'
             OR name ~* '\\ysectional\\y' OR name ~* '\\yloveseat\\y')
        GROUP BY source_website
        ORDER BY count DESC
    """))
    local_sofas = {}
    for row in result:
        print(f"   {row[0]}: {row[1]}")
        local_sofas[row[0]] = row[1]

# Check Railway
print("\n\n📍 RAILWAY DATABASE:")
print("-" * 70)
railway_engine = create_engine(railway_db)
with railway_engine.connect() as conn:
    # Total products
    total = conn.execute(text("SELECT COUNT(*) FROM products WHERE is_available = true")).scalar()
    print(f"Total products: {total}")

    # Sofas by source
    print("\n🛋️  Sofas by source:")
    result = conn.execute(text("""
        SELECT source_website, COUNT(*) as count
        FROM products
        WHERE is_available = true
        AND (name ~* '\\ysofa\\y' OR name ~* '\\ycouch\\y'
             OR name ~* '\\ysectional\\y' OR name ~* '\\yloveseat\\y')
        GROUP BY source_website
        ORDER BY count DESC
    """))
    railway_sofas = {}
    for row in result:
        print(f"   {row[0]}: {row[1]}")
        railway_sofas[row[0]] = row[1]

# Compare
print("\n\n📊 COMPARISON:")
print("=" * 70)
all_sources = set(local_sofas.keys()) | set(railway_sofas.keys())

missing_sources = []
for source in sorted(all_sources):
    local_count = local_sofas.get(source, 0)
    railway_count = railway_sofas.get(source, 0)
    diff = local_count - railway_count

    if diff == 0:
        status = "✅"
    elif railway_count == 0:
        status = "❌ MISSING"
        missing_sources.append((source, local_count))
    else:
        status = f"⚠️  Missing {diff}"

    print(f"{status:15} {source:30} Local: {local_count:3} | Railway: {railway_count:3}")

if missing_sources:
    print("\n\n⚠️  MISSING SOURCES ON RAILWAY:")
    print("-" * 70)
    for source, count in missing_sources:
        print(f"   {source}: {count} sofas not migrated")
    print("\nYou need to re-run the migration to include these sources.")
else:
    print("\n\n✅ All sources migrated successfully!")

print("\n" + "=" * 70)
