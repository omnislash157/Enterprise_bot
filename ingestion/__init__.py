"""
Ingestion Pipeline
===================

Document processing and embedding generation for enterprise bot.

Modules:
- docx_to_json_chunks: Core DOCX parser and chunker
- batch_convert_warehouse_docx: Batch conversion utility for Warehouse manuals
- json_chunk_loader: JSON chunk file loader (Phase 3)
- embed_chunks: Embedding generation via DeepInfra (Phase 3)
- ingest_to_postgres: PostgreSQL insertion pipeline (Phase 3)
"""

__version__ = "1.0.0"
