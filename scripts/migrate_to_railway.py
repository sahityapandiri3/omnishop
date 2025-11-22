"""
Script to migrate data from local PostgreSQL to Railway PostgreSQL
"""
import os
import sys
from pathlib import Path

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


def migrate_data(source_url: str, target_url: str):
    """
    Migrate all data from source database to target database

    Args:
        source_url: Source PostgreSQL connection string (local)
        target_url: Target PostgreSQL connection string (Railway)
    """
    logger.info("Starting data migration...")
    logger.info(f"Source: {source_url.split('@')[1] if '@' in source_url else 'local'}")
    logger.info(f"Target: {target_url.split('@')[1] if '@' in target_url else 'railway'}")

    # Create engines
    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    # Create sessions
    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    source_session = SourceSession()
    target_session = TargetSession()

    try:
        # Get table counts
        tables_to_migrate = [
            'categories',
            'products',
            'product_images',
            'product_attributes'
        ]

        logger.info("\n=== Checking source data ===")
        for table in tables_to_migrate:
            try:
                count = source_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                logger.info(f"{table}: {count} rows")
            except Exception as e:
                logger.warning(f"Could not count {table}: {e}")

        # Migrate categories first (products depend on them)
        logger.info("\n=== Migrating categories ===")
        migrate_table(source_session, target_session, 'categories',
                     pk_column='id', batch_size=100)

        # Migrate products
        logger.info("\n=== Migrating products ===")
        migrate_table(source_session, target_session, 'products',
                     pk_column='id', batch_size=500)

        # Migrate product images
        logger.info("\n=== Migrating product images ===")
        migrate_table(source_session, target_session, 'product_images',
                     pk_column='id', batch_size=1000)

        # Migrate product attributes
        logger.info("\n=== Migrating product attributes ===")
        migrate_table(source_session, target_session, 'product_attributes',
                     pk_column='id', batch_size=1000)

        # Update sequences to prevent ID conflicts
        logger.info("\n=== Updating sequences ===")
        for table in tables_to_migrate:
            try:
                max_id_result = target_session.execute(
                    text(f"SELECT MAX(id) FROM {table}")
                )
                max_id = max_id_result.scalar()
                if max_id:
                    sequence_name = f"{table}_id_seq"
                    target_session.execute(
                        text(f"SELECT setval('{sequence_name}', :max_id)"),
                        {"max_id": max_id}
                    )
                    logger.info(f"Updated {sequence_name} to {max_id}")
            except Exception as e:
                logger.warning(f"Could not update sequence for {table}: {e}")

        target_session.commit()

        logger.info("\n=== Migration completed successfully! ===")

        # Show final counts
        logger.info("\n=== Target database statistics ===")
        for table in tables_to_migrate:
            try:
                count = target_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                logger.info(f"{table}: {count} rows")
            except Exception as e:
                logger.warning(f"Could not count {table}: {e}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        target_session.rollback()
        raise
    finally:
        source_session.close()
        target_session.close()


def migrate_table(source_session, target_session, table_name: str,
                 pk_column: str = 'id', batch_size: int = 500):
    """
    Migrate a single table from source to target

    Args:
        source_session: Source database session
        target_session: Target database session
        table_name: Name of table to migrate
        pk_column: Primary key column name
        batch_size: Number of rows per batch
    """
    try:
        # Get total count
        total_count = source_session.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        ).scalar()

        if total_count == 0:
            logger.info(f"Skipping {table_name} (empty table)")
            return

        logger.info(f"Migrating {total_count} rows from {table_name}...")

        # Get column names
        columns_result = source_session.execute(text(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        columns = [row[0] for row in columns_result]
        columns_str = ', '.join(columns)

        # Migrate in batches
        offset = 0
        with tqdm(total=total_count, desc=f"Migrating {table_name}") as pbar:
            while offset < total_count:
                # Fetch batch from source
                rows = source_session.execute(text(f"""
                    SELECT {columns_str}
                    FROM {table_name}
                    ORDER BY {pk_column}
                    LIMIT {batch_size} OFFSET {offset}
                """)).fetchall()

                if not rows:
                    break

                # Insert batch into target
                for row in rows:
                    placeholders = ', '.join([f':{col}' for col in columns])
                    insert_query = f"""
                        INSERT INTO {table_name} ({columns_str})
                        VALUES ({placeholders})
                        ON CONFLICT ({pk_column}) DO UPDATE SET
                        {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != pk_column])}
                    """

                    row_dict = dict(zip(columns, row))
                    target_session.execute(text(insert_query), row_dict)

                target_session.commit()
                offset += len(rows)
                pbar.update(len(rows))

        logger.info(f"✓ Successfully migrated {table_name}")

    except Exception as e:
        logger.error(f"Error migrating {table_name}: {e}")
        raise


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
        logger.info("  python scripts/migrate_to_railway.py")
        sys.exit(1)

    # Confirm migration
    logger.info("\n" + "="*60)
    logger.info("DATABASE MIGRATION")
    logger.info("="*60)
    logger.info(f"\nSource: {source_url.split('@')[1] if '@' in source_url else source_url}")
    logger.info(f"Target: {target_url.split('@')[1] if '@' in target_url else target_url}")
    logger.info("\nThis will copy all data from source to target database.")
    logger.info("Existing data in target will be updated if conflicts occur.")

    response = input("\nContinue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        logger.info("Migration cancelled")
        sys.exit(0)

    # Run migration
    migrate_data(source_url, target_url)

    logger.info("\n" + "="*60)
    logger.info("MIGRATION COMPLETE!")
    logger.info("="*60)


if __name__ == '__main__':
    main()
