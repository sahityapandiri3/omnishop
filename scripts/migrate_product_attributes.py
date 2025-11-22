"""
Script to migrate product_attributes from local PostgreSQL to Railway PostgreSQL
with timeout handling and resume capability
"""
import os
import sys
from pathlib import Path
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_product_attributes(source_url: str, target_url: str, batch_size: int = 100):
    """
    Migrate product_attributes from source to target database

    Args:
        source_url: Source PostgreSQL connection string (local)
        target_url: Target PostgreSQL connection string (Railway)
        batch_size: Number of rows per batch (default 100 for better timeout handling)
    """
    logger.info("Starting product_attributes migration...")
    logger.info(f"Source: {source_url.split('@')[1] if '@' in source_url else 'local'}")
    logger.info(f"Target: {target_url.split('@')[1] if '@' in target_url else 'railway'}")
    logger.info(f"Batch size: {batch_size}")

    # Create engines with timeout settings
    source_engine = create_engine(
        source_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 60}
    )

    target_engine = create_engine(
        target_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 60, "keepalives": 1, "keepalives_idle": 30}
    )

    # Create sessions
    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    source_session = SourceSession()
    target_session = TargetSession()

    try:
        # Get counts
        source_count = source_session.execute(
            text("SELECT COUNT(*) FROM product_attributes")
        ).scalar()

        target_count = target_session.execute(
            text("SELECT COUNT(*) FROM product_attributes")
        ).scalar()

        remaining = source_count - target_count

        logger.info(f"\n=== Product Attributes Status ===")
        logger.info(f"Source total: {source_count}")
        logger.info(f"Target existing: {target_count}")
        logger.info(f"Remaining to migrate: {remaining}")

        if remaining == 0:
            logger.info("\n✅ All product_attributes already migrated!")
            return

        # Get column names
        columns_result = source_session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'product_attributes'
            ORDER BY ordinal_position
        """))
        columns = [row[0] for row in columns_result]
        columns_str = ', '.join(columns)

        # Find missing IDs (much more efficient than scanning all rows)
        logger.info("Getting all attribute IDs from source...")
        source_ids_result = source_session.execute(
            text("SELECT id FROM product_attributes ORDER BY id")
        )
        source_ids = set(row[0] for row in source_ids_result)

        logger.info("Getting all attribute IDs from target...")
        target_ids_result = target_session.execute(
            text("SELECT id FROM product_attributes ORDER BY id")
        )
        target_ids = set(row[0] for row in target_ids_result)

        # Find missing IDs
        missing_ids = sorted(source_ids - target_ids)

        logger.info(f"Found {len(missing_ids)} missing attributes to migrate")

        if not missing_ids:
            logger.info("✅ All attributes already migrated!")
            return

        logger.info(f"\nMigrating {len(missing_ids)} product_attributes in batches of {batch_size}...")
        logger.info("Progress will be saved automatically.\n")

        # Migrate only missing IDs in batches
        total_migrated = 0
        errors = 0

        with tqdm(total=len(missing_ids), desc="Migrating missing attributes") as pbar:
            # Process missing IDs in batches
            for i in range(0, len(missing_ids), batch_size):
                batch_ids = missing_ids[i:i + batch_size]

                try:
                    # Fetch batch from source using specific IDs
                    ids_placeholder = ','.join(str(id) for id in batch_ids)
                    rows = source_session.execute(text(f"""
                        SELECT {columns_str}
                        FROM product_attributes
                        WHERE id IN ({ids_placeholder})
                        ORDER BY id
                    """)).fetchall()

                    if not rows:
                        logger.warning(f"No rows found for IDs: {batch_ids[:5]}...")
                        continue

                    # Insert batch into target
                    batch_migrated = 0

                    for row in rows:
                        row_dict = dict(zip(columns, row))

                        # Insert new attribute
                        placeholders = ', '.join([f':{col}' for col in columns])
                        insert_query = f"""
                            INSERT INTO product_attributes ({columns_str})
                            VALUES ({placeholders})
                            ON CONFLICT (id) DO NOTHING
                        """

                        try:
                            target_session.execute(text(insert_query), row_dict)
                            batch_migrated += 1
                        except Exception as e:
                            logger.error(f"Error inserting attribute {row_dict.get('id')}: {e}")
                            errors += 1

                    # Commit batch
                    target_session.commit()
                    total_migrated += batch_migrated
                    pbar.update(len(rows))

                    # Log progress every 10 batches
                    if (i // batch_size) % 10 == 0 and total_migrated > 0:
                        logger.info(f"Migrated {total_migrated}/{len(missing_ids)} attributes")

                    # Small delay to prevent overwhelming the connection
                    time.sleep(0.1)

                except Exception as e:
                    logger.error(f"Error processing batch: {e}")
                    logger.info("Committing successful rows and continuing...")
                    try:
                        target_session.commit()
                    except:
                        target_session.rollback()
                    errors += 1

                    # If too many errors, pause
                    if errors > 5:
                        logger.warning("Multiple errors detected, pausing for 5 seconds...")
                        time.sleep(5)
                        errors = 0

        # Update sequence
        logger.info("\nUpdating sequence...")
        try:
            max_id_result = target_session.execute(
                text("SELECT MAX(id) FROM product_attributes")
            )
            max_id = max_id_result.scalar()
            if max_id:
                target_session.execute(
                    text("SELECT setval('product_attributes_id_seq', :max_id)"),
                    {"max_id": max_id}
                )
                target_session.commit()
                logger.info(f"Updated product_attributes_id_seq to {max_id}")
        except Exception as e:
            logger.warning(f"Could not update sequence: {e}")

        # Final count
        final_count = target_session.execute(
            text("SELECT COUNT(*) FROM product_attributes")
        ).scalar()

        logger.info("\n" + "="*60)
        logger.info("MIGRATION COMPLETE!")
        logger.info("="*60)
        logger.info(f"Total in source: {source_count}")
        logger.info(f"Total in target: {final_count}")
        logger.info(f"Newly migrated: {total_migrated}")
        logger.info(f"Skipped (already existed): {total_skipped}")
        logger.info(f"Errors encountered: {errors}")

        if final_count == source_count:
            logger.info("\n✅ All product_attributes successfully migrated!")
        else:
            missing = source_count - final_count
            logger.warning(f"\n⚠️  {missing} attributes still missing. Run the script again to retry.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        target_session.rollback()
        raise
    finally:
        source_session.close()
        target_session.close()


def main():
    """Main migration function"""
    # Get database URLs from environment or arguments
    source_url = os.environ.get(
        'SOURCE_DATABASE_URL',
        'postgresql://omnishop_user:omnishop_secure_2024@localhost:5432/omnishop'
    )

    target_url = os.environ.get('TARGET_DATABASE_URL') or os.environ.get('DATABASE_URL')

    if not target_url:
        logger.error("TARGET_DATABASE_URL or DATABASE_URL environment variable not set!")
        logger.info("\nUsage:")
        logger.info("  export TARGET_DATABASE_URL='your-railway-postgres-url'")
        logger.info("  python scripts/migrate_product_attributes.py")
        sys.exit(1)

    # Confirm migration
    logger.info("\n" + "="*60)
    logger.info("PRODUCT ATTRIBUTES MIGRATION")
    logger.info("="*60)
    logger.info(f"\nSource: {source_url.split('@')[1] if '@' in source_url else source_url}")
    logger.info(f"Target: {target_url.split('@')[1] if '@' in target_url else target_url}")
    logger.info("\nThis will migrate product_attributes with timeout handling.")
    logger.info("You can safely re-run this script if it times out.")

    response = input("\nContinue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        logger.info("Migration cancelled")
        sys.exit(0)

    # Run migration
    batch_size = int(os.environ.get('BATCH_SIZE', '100'))
    migrate_product_attributes(source_url, target_url, batch_size=batch_size)


if __name__ == '__main__':
    main()
