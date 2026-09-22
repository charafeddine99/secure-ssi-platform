#!/usr/bin/env python3
"""
CLI Tool: Authoritative SQLite to MongoDB Data Migration.
Usage:
    python scripts/migrate_sqlite_to_mongodb.py [--dry-run] [--export-json <path>] [--mongo-uri <uri>]
"""

import sys
import os
import argparse
from pathlib import Path

# Add identity-service to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "services" / "identity-service"))

from app.infrastructure.persistence.sqlite_migrator import SQLiteToMongoMigrator

def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite entities to MongoDB persistence.")
    parser.add_argument(
        "--sqlite-path",
        default=str(BASE_DIR / "services" / "identity-service" / "secure_ssi_database.db"),
        help="Path to SQLite database file"
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv("IDENTITY_MONGO_URI"),
        help="Target MongoDB connection URI"
    )
    parser.add_argument(
        "--export-json",
        default=str(BASE_DIR / "scratch" / "migrated_mongo_data.json"),
        help="Path to save validated JSON export of transformed documents"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform transformation and validation without live insertion"
    )

    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        print(f"[-] SQLite database not found at: {sqlite_path}")
        sys.exit(1)

    print(f"[+] Initializing SQLite -> MongoDB Migrator for: {sqlite_path}")
    migrator = SQLiteToMongoMigrator(sqlite_path)

    mongo_db = None
    if args.mongo_uri and not args.dry_run:
        try:
            from pymongo import MongoClient
            client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            mongo_db = client.get_default_database() or client["secure_identity"]
            print(f"[+] Successfully connected to live MongoDB: {mongo_db.name}")
        except Exception as e:
            print(f"[!] Warning: Could not connect to live MongoDB: {e}")
            print("[!] Defaulting to dry-run validation mode.")
            mongo_db = None

    export_target = Path(args.export_json) if args.export_json else None
    result = migrator.run_migration_or_export(mongo_db=mongo_db, export_file=export_target)

    print("\n" + "=" * 60)
    print("MIGRATION & VALIDATION REPORT:")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Source SQLite Records:")
    for k, v in result["source_sqlite_records"].items():
        print(f"  • {k}: {v} records")
    print(f"Target MongoDB Documents:")
    for k, v in result["target_mongo_documents"].items():
        print(f"  • {k}: {v} documents")
    print("Security Invariants:")
    for k, v in result["security_validation"].items():
        print(f"  • {k}: {v}")
    if "export_path" in result:
        print(f"Exported artifact: {result['export_path']}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
