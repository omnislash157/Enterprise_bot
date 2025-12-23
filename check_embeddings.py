#!/usr/bin/env python3
"""
Database Embedding Reconnaissance Script

Check what embeddings exist in the database:
1. Count total chunks, embeddings, and synthetic question embeddings
2. Sample chunks to verify structure
3. Check if synthetic questions are being used
4. Identify missing embeddings
5. Verify RAG retrieval is considering question embeddings

Usage:
    python check_embeddings.py
"""

import os
import sys
from typing import Any, Dict, List

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv(override=True)


def get_db_connection():
    """Get PostgreSQL connection from environment."""
    return psycopg2.connect(
        host=os.getenv("AZURE_PG_HOST"),
        database=os.getenv("AZURE_PG_DATABASE", "postgres"),
        user=os.getenv("AZURE_PG_USER"),
        password=os.getenv("AZURE_PG_PASSWORD"),
        sslmode=os.getenv("AZURE_PG_SSLMODE", "require"),
        port=int(os.getenv("AZURE_PG_PORT", "5432")),
    )


def check_schema(cur):
    """Check if enterprise.documents table exists and has expected columns."""
    print("\n" + "=" * 80)
    print("SCHEMA CHECK")
    print("=" * 80)

    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'enterprise'
            AND table_name = 'documents'
        );
    """)

    exists = cur.fetchone()[0]

    if not exists:
        print("❌ ERROR: enterprise.documents table does not exist!")
        return False

    print("✅ enterprise.documents table exists")

    # Get column list
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'enterprise' AND table_name = 'documents'
        ORDER BY ordinal_position;
    """)

    columns = cur.fetchall()

    print(f"\nColumns ({len(columns)} total):")

    # Check for key columns
    key_columns = {
        'id': False,
        'content': False,
        'embedding': False,
        'synthetic_questions': False,
        'synthetic_questions_embedding': False,
        'department_id': False,
        'section_title': False,
        'source_file': False,
    }

    for col in columns:
        col_name = col[0]
        if col_name in key_columns:
            key_columns[col_name] = True
            print(f"  ✅ {col_name} ({col[1]})")
        else:
            print(f"     {col_name} ({col[1]})")

    # Report missing key columns
    missing = [k for k, v in key_columns.items() if not v]
    if missing:
        print(f"\n⚠️  Missing expected columns: {', '.join(missing)}")

    return True


def check_counts(cur):
    """Get counts of various embedding types."""
    print("\n" + "=" * 80)
    print("EMBEDDING COUNTS")
    print("=" * 80)

    # Total chunks
    cur.execute("SELECT COUNT(*) FROM enterprise.documents WHERE is_active = TRUE;")
    total = cur.fetchone()[0]
    print(f"\n📊 Total active chunks: {total:,}")

    if total == 0:
        print("⚠️  No active documents in database!")
        return

    # With content embeddings
    cur.execute("""
        SELECT COUNT(*) FROM enterprise.documents
        WHERE is_active = TRUE AND embedding IS NOT NULL;
    """)
    with_embeddings = cur.fetchone()[0]
    pct_embeddings = (with_embeddings / total * 100) if total > 0 else 0
    print(f"📌 With content embeddings: {with_embeddings:,} ({pct_embeddings:.1f}%)")

    # With synthetic questions
    cur.execute("""
        SELECT COUNT(*) FROM enterprise.documents
        WHERE is_active = TRUE
        AND synthetic_questions IS NOT NULL
        AND array_length(synthetic_questions, 1) > 0;
    """)
    with_questions = cur.fetchone()[0]
    pct_questions = (with_questions / total * 100) if total > 0 else 0
    print(f"❓ With synthetic questions: {with_questions:,} ({pct_questions:.1f}%)")

    # With question embeddings
    cur.execute("""
        SELECT COUNT(*) FROM enterprise.documents
        WHERE is_active = TRUE
        AND synthetic_questions_embedding IS NOT NULL;
    """)
    with_q_embeddings = cur.fetchone()[0]
    pct_q_embeddings = (with_q_embeddings / total * 100) if total > 0 else 0
    print(f"🎯 With question embeddings: {with_q_embeddings:,} ({pct_q_embeddings:.1f}%)")

    # Average question count
    cur.execute("""
        SELECT AVG(array_length(synthetic_questions, 1))
        FROM enterprise.documents
        WHERE is_active = TRUE
        AND synthetic_questions IS NOT NULL;
    """)
    avg_questions = cur.fetchone()[0] or 0
    print(f"📝 Average questions per chunk: {avg_questions:.1f}")

    # Total questions
    total_questions = int(avg_questions * with_questions)
    print(f"💭 Total synthetic questions: ~{total_questions:,}")

    # Breakdown by department
    print("\n📂 By Department:")
    cur.execute("""
        SELECT
            department_id,
            COUNT(*) as total,
            COUNT(embedding) as with_emb,
            COUNT(synthetic_questions_embedding) as with_q_emb,
            AVG(array_length(synthetic_questions, 1)) as avg_q
        FROM enterprise.documents
        WHERE is_active = TRUE
        GROUP BY department_id
        ORDER BY total DESC;
    """)

    for row in cur.fetchall():
        dept, total, emb, q_emb, avg_q = row
        avg_q = avg_q or 0
        print(f"  {dept:15} {total:5} chunks | {emb:5} embeddings | {q_emb:5} q_embeddings | {avg_q:.1f} avg_q")


def sample_chunks(cur):
    """Show sample chunks with their data."""
    print("\n" + "=" * 80)
    print("SAMPLE CHUNKS")
    print("=" * 80)

    cur.execute("""
        SELECT
            id,
            department_id,
            section_title,
            LEFT(content, 100) as content_preview,
            array_length(synthetic_questions, 1) as question_count,
            synthetic_questions[1:2] as sample_questions,
            CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding,
            CASE WHEN synthetic_questions_embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_q_embedding
        FROM enterprise.documents
        WHERE is_active = TRUE
        ORDER BY RANDOM()
        LIMIT 5;
    """)

    samples = cur.fetchall()

    if not samples:
        print("⚠️  No documents found!")
        return

    for i, row in enumerate(samples, 1):
        print(f"\n[CHUNK {i}]")
        print(f"  ID: {row[0]}")
        print(f"  Department: {row[1]}")
        print(f"  Section: {row[2]}")
        print(f"  Content: {row[3]}...")
        print(f"  Questions: {row[4] or 0} total")
        if row[5]:
            for j, q in enumerate(row[5], 1):
                print(f"    Q{j}: {q}")
        print(f"  Content Embedding: {row[6]}")
        print(f"  Question Embedding: {row[7]}")


def check_missing_embeddings(cur):
    """Find chunks that should have embeddings but don't."""
    print("\n" + "=" * 80)
    print("MISSING EMBEDDINGS ANALYSIS")
    print("=" * 80)

    # Chunks with questions but no question embeddings
    cur.execute("""
        SELECT COUNT(*)
        FROM enterprise.documents
        WHERE is_active = TRUE
        AND synthetic_questions IS NOT NULL
        AND array_length(synthetic_questions, 1) > 0
        AND synthetic_questions_embedding IS NULL;
    """)

    missing_q_embeddings = cur.fetchone()[0]

    if missing_q_embeddings > 0:
        print(f"⚠️  {missing_q_embeddings} chunks have questions but NO question embeddings!")

        # Show samples
        cur.execute("""
            SELECT id, department_id, section_title,
                   array_length(synthetic_questions, 1) as q_count
            FROM enterprise.documents
            WHERE is_active = TRUE
            AND synthetic_questions IS NOT NULL
            AND array_length(synthetic_questions, 1) > 0
            AND synthetic_questions_embedding IS NULL
            LIMIT 5;
        """)

        print("\n  Sample chunks missing question embeddings:")
        for row in cur.fetchall():
            print(f"    - {row[0]} ({row[1]}, {row[2]}) - {row[3]} questions")
    else:
        print("✅ All chunks with questions have question embeddings!")

    # Chunks with content but no content embeddings
    cur.execute("""
        SELECT COUNT(*)
        FROM enterprise.documents
        WHERE is_active = TRUE
        AND content IS NOT NULL
        AND content != ''
        AND embedding IS NULL;
    """)

    missing_embeddings = cur.fetchone()[0]

    if missing_embeddings > 0:
        print(f"\n⚠️  {missing_embeddings} chunks have content but NO content embeddings!")
    else:
        print("\n✅ All chunks with content have content embeddings!")


def check_rag_usage(cur):
    """Check how RAG is configured and if it uses question embeddings."""
    print("\n" + "=" * 80)
    print("RAG CONFIGURATION ANALYSIS")
    print("=" * 80)

    # This is a static analysis - we'd need to inspect the code
    print("\n📖 Checking enterprise_rag.py configuration...")

    # Check if there are any indexes on the embedding columns
    cur.execute("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'enterprise'
        AND tablename = 'documents'
        AND indexdef LIKE '%embedding%';
    """)

    indexes = cur.fetchall()

    if indexes:
        print(f"\n✅ Found {len(indexes)} embedding indexes:")
        for idx_name, idx_def in indexes:
            print(f"  - {idx_name}")
            if 'synthetic_questions_embedding' in idx_def:
                print(f"    🎯 USES question embeddings!")
            elif 'embedding' in idx_def:
                print(f"    📌 USES content embeddings")
    else:
        print("\n⚠️  No embedding indexes found!")
        print("    Vector search may be slow or not working.")

    # Check if pgvector extension is installed
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_extension WHERE extname = 'vector'
        );
    """)

    has_vector = cur.fetchone()[0]

    if has_vector:
        print("\n✅ pgvector extension is installed")
    else:
        print("\n❌ pgvector extension NOT installed!")
        print("    Vector search will not work!")


def check_question_stats(cur):
    """Detailed statistics on synthetic questions."""
    print("\n" + "=" * 80)
    print("SYNTHETIC QUESTIONS STATISTICS")
    print("=" * 80)

    # Distribution of question counts
    cur.execute("""
        SELECT
            array_length(synthetic_questions, 1) as q_count,
            COUNT(*) as chunks
        FROM enterprise.documents
        WHERE is_active = TRUE
        AND synthetic_questions IS NOT NULL
        GROUP BY array_length(synthetic_questions, 1)
        ORDER BY q_count;
    """)

    print("\n📊 Question count distribution:")
    for q_count, chunks in cur.fetchall():
        if q_count is not None:
            print(f"  {q_count} questions: {chunks} chunks")

    # Show some actual questions
    print("\n💭 Sample synthetic questions:")
    cur.execute("""
        SELECT
            department_id,
            section_title,
            synthetic_questions[1:3] as sample_q
        FROM enterprise.documents
        WHERE is_active = TRUE
        AND synthetic_questions IS NOT NULL
        AND array_length(synthetic_questions, 1) > 0
        LIMIT 3;
    """)

    for i, row in enumerate(cur.fetchall(), 1):
        dept, section, questions = row
        print(f"\n  [{i}] {dept} - {section}")
        for j, q in enumerate(questions, 1):
            print(f"      Q{j}: {q}")


def main():
    """Run all checks."""
    print("\n" + "=" * 80)
    print("DATABASE EMBEDDING RECONNAISSANCE")
    print("=" * 80)

    # Check env vars
    required_vars = ['AZURE_PG_HOST', 'AZURE_PG_PASSWORD']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        print(f"\n❌ ERROR: Missing environment variables: {', '.join(missing)}")
        print("   Make sure .env file is loaded with database credentials.")
        return 1

    print(f"\n🔗 Connecting to: {os.getenv('AZURE_PG_HOST')}")
    print(f"   Database: {os.getenv('AZURE_PG_DATABASE')}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Run all checks
        if not check_schema(cur):
            return 1

        check_counts(cur)
        sample_chunks(cur)
        check_missing_embeddings(cur)
        check_rag_usage(cur)
        check_question_stats(cur)

        cur.close()
        conn.close()

        print("\n" + "=" * 80)
        print("RECONNAISSANCE COMPLETE")
        print("=" * 80)

        return 0

    except psycopg2.Error as e:
        print(f"\n❌ Database Error: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
