#!/usr/bin/env python3
"""
Install pgvector extension on Azure PostgreSQL
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!"),
    "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}


def install_pgvector():
    """Install pgvector extension."""
    print("Connecting to database...")
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Database: {DB_CONFIG['database']}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print("\nInstalling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✓ pgvector extension installed")

        # Verify installation
        cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
        result = cur.fetchone()
        if result:
            print(f"\n✓ Verification successful:")
            print(f"  Extension: {result[0]}")
            print(f"  Version: {result[1]}")
        else:
            print("\n✗ Extension not found after installation!")

    except Exception as e:
        print(f"\n✗ Failed to install pgvector: {e}")
        print("\nNote: Azure PostgreSQL Flexible Server includes pgvector by default.")
        print("If this fails, ensure you're using Flexible Server (not Single Server).")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    install_pgvector()
