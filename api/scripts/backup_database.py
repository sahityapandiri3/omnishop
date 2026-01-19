#!/usr/bin/env python3
"""
Database backup script for Omnishop.

Usage:
    # Backup local database
    python scripts/backup_database.py --local

    # Backup production database
    python scripts/backup_database.py --prod --prod-url "postgresql://..."

    # Backup both
    python scripts/backup_database.py --local --prod --prod-url "postgresql://..."

    # Restore from backup
    python scripts/backup_database.py --restore backup_file.sql --target local
    python scripts/backup_database.py --restore backup_file.sql --target prod --prod-url "..."

Backups are saved to: api/backups/
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")


def ensure_backup_dir():
    """Create backup directory if it doesn't exist."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Add .gitignore to prevent committing backups
    gitignore_path = os.path.join(BACKUP_DIR, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write("# Ignore all backup files\n*.sql\n*.sql.gz\n")


def parse_db_url(url: str) -> dict:
    """Parse database URL into components."""
    parsed = urlparse(url.replace("+asyncpg", ""))
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def backup_database(db_url: str, name: str) -> str:
    """Backup a database using pg_dump."""
    ensure_backup_dir()

    db = parse_db_url(db_url)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"{name}_{timestamp}.sql")

    # Set password in environment (if exists)
    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    # Run pg_dump
    cmd = [
        "pg_dump",
        "-h", db["host"],
        "-p", str(db["port"]),
        "-U", db["user"],
        "-d", db["database"],
        "-F", "p",  # Plain SQL format
        "--no-owner",
        "--no-acl",
        "-f", backup_file,
    ]

    print(f"Backing up {name} database...")
    print(f"  Host: {db['host']}:{db['port']}")
    print(f"  Database: {db['database']}")

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return None

        # Get file size
        size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        print(f"  Saved to: {backup_file}")
        print(f"  Size: {size_mb:.2f} MB")

        # Optionally compress
        compress_cmd = ["gzip", "-f", backup_file]
        subprocess.run(compress_cmd, capture_output=True)
        compressed_file = backup_file + ".gz"
        if os.path.exists(compressed_file):
            size_mb = os.path.getsize(compressed_file) / (1024 * 1024)
            print(f"  Compressed: {compressed_file} ({size_mb:.2f} MB)")
            return compressed_file

        return backup_file
    except FileNotFoundError:
        print("  Error: pg_dump not found. Install PostgreSQL client tools.")
        return None


def restore_database(backup_file: str, db_url: str):
    """Restore a database from backup."""
    db = parse_db_url(db_url)

    # Decompress if needed
    if backup_file.endswith(".gz"):
        print(f"Decompressing {backup_file}...")
        subprocess.run(["gunzip", "-k", "-f", backup_file], capture_output=True)
        backup_file = backup_file[:-3]  # Remove .gz

    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    cmd = [
        "psql",
        "-h", db["host"],
        "-p", str(db["port"]),
        "-U", db["user"],
        "-d", db["database"],
        "-f", backup_file,
    ]

    print(f"Restoring to {db['host']}:{db['port']}/{db['database']}...")
    print("WARNING: This will overwrite existing data!")

    confirm = input("Continue? [y/N]: ")
    if confirm.lower() != "y":
        print("Aborted.")
        return

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print("Restore complete!")


def list_backups():
    """List available backups."""
    ensure_backup_dir()
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith((".sql", ".sql.gz"))])

    if not backups:
        print("No backups found.")
        return

    print(f"Available backups in {BACKUP_DIR}:")
    for backup in backups:
        path = os.path.join(BACKUP_DIR, backup)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {backup} ({size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Database backup and restore")
    parser.add_argument("--local", action="store_true", help="Backup local database")
    parser.add_argument("--prod", action="store_true", help="Backup production database")
    parser.add_argument("--prod-url", help="Production database URL")
    parser.add_argument("--restore", help="Restore from backup file")
    parser.add_argument("--target", choices=["local", "prod"], help="Restore target (local or prod)")
    parser.add_argument("--list", action="store_true", help="List available backups")

    args = parser.parse_args()

    if args.list:
        list_backups()
        return

    if args.restore:
        if not args.target:
            print("Error: --target required for restore")
            sys.exit(1)

        if args.target == "local":
            db_url = os.getenv("DATABASE_URL", "")
        else:
            if not args.prod_url:
                print("Error: --prod-url required for production restore")
                sys.exit(1)
            db_url = args.prod_url

        restore_database(args.restore, db_url)
        return

    if args.local:
        local_url = os.getenv("DATABASE_URL", "")
        if not local_url:
            print("Error: DATABASE_URL not set")
        else:
            backup_database(local_url, "local")

    if args.prod:
        if not args.prod_url:
            print("Error: --prod-url required for production backup")
            sys.exit(1)
        backup_database(args.prod_url, "production")

    if not args.local and not args.prod and not args.restore:
        parser.print_help()


if __name__ == "__main__":
    main()
