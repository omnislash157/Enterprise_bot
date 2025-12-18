"""
PostgreSQL Migration Script - Phase 5
======================================

Migrates existing file-based memory data to PostgreSQL with pgvector.

This is a one-time migration tool to move from file storage to PostgreSQL
while preserving all memory nodes, embeddings, and metadata.

Usage:
    # Personal mode (user_id scoping)
    python migrate_to_postgres.py --user-id <user_id> [--data-dir ./data]

    # Enterprise mode (tenant_id scoping)
    python migrate_to_postgres.py --tenant-id <tenant_id> [--data-dir ./data]

Requirements:
    - PostgreSQL with pgvector extension
    - DATABASE_URL environment variable set
    - Existing data/corpus/nodes.json and data/vectors/nodes.npy

Environment:
    DATABASE_URL: PostgreSQL connection string
                  (e.g., postgresql://user:pass@host:port/dbname)
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import numpy as np
import asyncpg
from asyncpg import Connection

# Import schemas for type safety
try:
    from schemas import MemoryNode, Source, IntentType, Complexity, EmotionalValence, Urgency, ConversationMode
except ImportError:
    print("ERROR: Cannot import schemas. Ensure schemas.py exists in project root.")
    sys.exit(1)


class MigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.total_nodes = 0
        self.migrated = 0
        self.skipped = 0
        self.errors = 0
        self.start_time = None
        self.end_time = None
        self.error_messages = []

    def record_success(self):
        self.migrated += 1

    def record_skip(self):
        self.skipped += 1

    def record_error(self, node_id: str, error: str):
        self.errors += 1
        self.error_messages.append(f"[{node_id}] {error}")

    def start(self):
        self.start_time = time.time()

    def finish(self):
        self.end_time = time.time()

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def print_summary(self):
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Total nodes found:       {self.total_nodes}")
        print(f"Successfully migrated:   {self.migrated}")
        print(f"Skipped:                 {self.skipped}")
        print(f"Errors:                  {self.errors}")
        print(f"Time taken:              {self.duration_seconds:.2f}s")

        if self.migrated > 0:
            print(f"Average per node:        {self.duration_seconds / self.migrated * 1000:.1f}ms")

        if self.error_messages:
            print("\nERROR DETAILS:")
            for msg in self.error_messages[:10]:  # Show first 10 errors
                print(f"  - {msg}")
            if len(self.error_messages) > 10:
                print(f"  ... and {len(self.error_messages) - 10} more errors")

        print("=" * 60)


class PostgresMigrator:
    """Handles migration from file-based storage to PostgreSQL."""

    def __init__(self, connection_string: str, data_dir: Path):
        self.connection_string = connection_string
        self.data_dir = data_dir
        self.conn: Optional[Connection] = None
        self.stats = MigrationStats()

    async def connect(self):
        """Establish database connection and register pgvector."""
        try:
            self.conn = await asyncpg.connect(self.connection_string)

            # Register pgvector extension
            await self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            print(f"Connected to PostgreSQL")
            return True
        except Exception as e:
            print(f"ERROR: Failed to connect to database: {e}")
            return False

    async def close(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            print("Database connection closed")

    async def verify_schema(self) -> bool:
        """Verify that memory_nodes table exists."""
        try:
            result = await self.conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'memory_nodes'
                )
            """)

            if not result:
                print("ERROR: memory_nodes table does not exist.")
                print("Please run the database migration SQL first:")
                print("  CREATE TABLE memory_nodes (...)")
                return False

            print("Schema verified: memory_nodes table exists")
            return True
        except Exception as e:
            print(f"ERROR: Schema verification failed: {e}")
            return False

    def load_nodes_from_file(self) -> List[MemoryNode]:
        """Load memory nodes from nodes.json."""
        nodes_file = self.data_dir / "corpus" / "nodes.json"

        if not nodes_file.exists():
            print(f"ERROR: Nodes file not found: {nodes_file}")
            return []

        try:
            with open(nodes_file, 'r', encoding='utf-8') as f:
                nodes_data = json.load(f)

            nodes = [MemoryNode.from_dict(d) for d in nodes_data]
            print(f"Loaded {len(nodes)} nodes from {nodes_file}")
            return nodes
        except Exception as e:
            print(f"ERROR: Failed to load nodes: {e}")
            return []

    def load_embeddings_from_file(self) -> Optional[np.ndarray]:
        """Load embeddings from nodes.npy."""
        emb_file = self.data_dir / "vectors" / "nodes.npy"

        if not emb_file.exists():
            print(f"ERROR: Embeddings file not found: {emb_file}")
            return None

        try:
            embeddings = np.load(emb_file)
            print(f"Loaded embeddings with shape: {embeddings.shape}")
            return embeddings
        except Exception as e:
            print(f"ERROR: Failed to load embeddings: {e}")
            return None

    async def insert_node(
        self,
        node: MemoryNode,
        embedding: np.ndarray,
        user_id: Optional[str],
        tenant_id: Optional[str]
    ) -> bool:
        """Insert a single node into PostgreSQL."""
        try:
            # Convert embedding to list for pgvector
            embedding_list = embedding.tolist()

            # Note: user_id and tenant_id should be UUIDs in the database
            # If they're not valid UUIDs, the INSERT will fail
            # The caller should ensure these are valid UUID strings

            await self.conn.execute("""
                INSERT INTO memory_nodes (
                    id, user_id, tenant_id, conversation_id, sequence_index,
                    human_content, assistant_content, source, embedding,
                    intent_type, complexity, technical_depth,
                    emotional_valence, urgency, conversation_mode,
                    action_required, has_code, has_error,
                    cluster_id, cluster_label, cluster_confidence,
                    access_count, created_at
                ) VALUES (
                    $1, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                )
                ON CONFLICT (id) DO NOTHING
            """,
                node.id,
                user_id,
                tenant_id,
                node.conversation_id,
                node.sequence_index,
                node.human_content,
                node.assistant_content,
                node.source.value,
                embedding_list,
                node.intent_type.value,
                node.complexity.value,
                node.technical_depth,
                node.emotional_valence.value,
                node.urgency.value,
                node.conversation_mode.value,
                node.action_required,
                node.has_code,
                node.has_error,
                node.cluster_id,
                node.cluster_label,
                node.cluster_confidence,
                node.access_count,
                node.created_at
            )

            return True
        except Exception as e:
            print(f"ERROR inserting node {node.id}: {e}")
            return False

    async def migrate_all(
        self,
        user_id: Optional[str],
        tenant_id: Optional[str]
    ) -> MigrationStats:
        """Migrate all nodes from file storage to PostgreSQL."""

        # Validate auth scoping
        if not user_id and not tenant_id:
            print("ERROR: Must provide either --user-id or --tenant-id")
            return self.stats

        if user_id and tenant_id:
            print("ERROR: Cannot provide both --user-id and --tenant-id")
            return self.stats

        # Determine mode
        mode = "personal" if user_id else "enterprise"
        scope_id = user_id or tenant_id
        print(f"\nMigration mode: {mode}")
        print(f"Scope ID: {scope_id}")

        # Load data
        print("\n" + "-" * 60)
        print("LOADING DATA FROM FILES")
        print("-" * 60)

        nodes = self.load_nodes_from_file()
        if not nodes:
            print("No nodes to migrate")
            return self.stats

        embeddings = self.load_embeddings_from_file()
        if embeddings is None:
            print("Cannot proceed without embeddings")
            return self.stats

        # Verify shapes match
        if len(nodes) != embeddings.shape[0]:
            print(f"ERROR: Node count ({len(nodes)}) does not match embedding count ({embeddings.shape[0]})")
            return self.stats

        self.stats.total_nodes = len(nodes)

        # Begin migration
        print("\n" + "-" * 60)
        print("MIGRATING TO POSTGRESQL")
        print("-" * 60)

        self.stats.start()

        for i, node in enumerate(nodes):
            # Progress indicator
            if (i + 1) % 10 == 0 or (i + 1) == len(nodes):
                progress = (i + 1) / len(nodes) * 100
                print(f"Progress: {i + 1}/{len(nodes)} ({progress:.1f}%) - {self.stats.migrated} migrated, {self.stats.errors} errors", end='\r')

            # Insert node
            success = await self.insert_node(
                node=node,
                embedding=embeddings[i],
                user_id=user_id,
                tenant_id=tenant_id
            )

            if success:
                self.stats.record_success()
            else:
                self.stats.record_error(node.id, "Insert failed")

        print()  # New line after progress
        self.stats.finish()

        return self.stats


async def main():
    """Main migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate file-based memory data to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate for personal user
  python migrate_to_postgres.py --user-id user_123

  # Migrate for enterprise tenant
  python migrate_to_postgres.py --tenant-id tenant_driscoll

  # Custom data directory
  python migrate_to_postgres.py --user-id user_123 --data-dir /path/to/data
"""
    )

    parser.add_argument(
        '--user-id',
        type=str,
        help='User ID to stamp nodes with (for personal mode)'
    )

    parser.add_argument(
        '--tenant-id',
        type=str,
        help='Tenant ID to stamp nodes with (for enterprise mode)'
    )

    parser.add_argument(
        '--data-dir',
        type=str,
        default='./data',
        help='Path to data directory (default: ./data)'
    )

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("PostgreSQL Migration Tool - Phase 5")
    print("=" * 60)
    print()

    # Validate arguments
    if not args.user_id and not args.tenant_id:
        parser.error("Must provide either --user-id or --tenant-id")

    if args.user_id and args.tenant_id:
        parser.error("Cannot provide both --user-id and --tenant-id")

    # Validate UUID format
    scope_id = args.user_id or args.tenant_id
    try:
        UUID(scope_id)
    except ValueError:
        print(f"ERROR: Invalid UUID format: {scope_id}")
        print("Please provide a valid UUID (e.g., '11111111-1111-1111-1111-111111111111')")
        print()
        print("To create a test user or tenant, run the following SQL:")
        if args.user_id:
            print(f"  INSERT INTO users (id, auth_provider, external_id, email)")
            print(f"  VALUES ('{scope_id}', 'test', 'test_user', 'test@example.com');")
        else:
            print(f"  INSERT INTO tenants (id, name)")
            print(f"  VALUES ('{scope_id}', 'test_tenant');")
        sys.exit(1)

    # Get database connection string
    connection_string = os.environ.get('DATABASE_URL')
    if not connection_string:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Please set DATABASE_URL to your PostgreSQL connection string:")
        print("  export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        sys.exit(1)

    # Verify data directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: Data directory does not exist: {data_dir}")
        sys.exit(1)

    print(f"Data directory: {data_dir.absolute()}")
    print(f"Database: {connection_string.split('@')[1] if '@' in connection_string else 'localhost'}")
    print()

    # Confirmation prompt
    mode = "personal" if args.user_id else "enterprise"
    scope_id = args.user_id or args.tenant_id
    print(f"Ready to migrate in {mode} mode")
    print(f"All nodes will be stamped with: {mode}_id = {scope_id}")
    print()

    response = input("Continue? [y/N]: ")
    if response.lower() not in ['y', 'yes']:
        print("Migration cancelled")
        sys.exit(0)

    # Run migration
    migrator = PostgresMigrator(connection_string, data_dir)

    try:
        # Connect to database
        if not await migrator.connect():
            sys.exit(1)

        # Verify schema
        if not await migrator.verify_schema():
            sys.exit(1)

        # Run migration
        stats = await migrator.migrate_all(
            user_id=args.user_id,
            tenant_id=args.tenant_id
        )

        # Print summary
        stats.print_summary()

        # Exit code
        if stats.errors > 0:
            print("\nWARNING: Migration completed with errors")
            sys.exit(1)
        else:
            print("\nMigration completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await migrator.close()


if __name__ == "__main__":
    asyncio.run(main())
