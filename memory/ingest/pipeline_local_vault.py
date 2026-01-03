# Updated version of run_pipeline_for_user to use LocalVaultService

async def run_pipeline_for_user(
    user_id: str,
    source_type: str,
    upload_id: str,
    config: dict,
) -> dict:
    """
    Run ingestion pipeline for a specific user's upload.
    
    **NEW VERSION 3.0: LOCAL-FIRST WITH B2 SYNC**
    
    - Reads existing data from LocalVaultService (local ~/.cogzy/)
    - Downloads new uploads from B2
    - Processes and writes to LocalVaultService first
    - Then syncs to B2 in background

    Args:
        user_id: User UUID
        source_type: anthropic, openai, grok, gemini
        upload_id: UUID of the vault_uploads record
        config: Full config dict

    Returns:
        dict with nodes_created, nodes_deduplicated counts
    """
    from core.vault_service import get_vault_service
    from core.local_vault import LocalVaultService
    from io import BytesIO
    import json
    import hashlib
    import numpy as np
    from datetime import datetime

    # Initialize services
    vault = get_vault_service(config)
    local_vault = LocalVaultService(user_id=user_id, b2_config=config)
    
    logger.info(f"Running LOCAL-FIRST pipeline for user {user_id}, upload {upload_id}")

    # 1. List files in uploads/{source_type}/ (still from B2)
    paths = vault.get_paths(user_id)
    upload_prefix = f"{paths.uploads}/{source_type}/"
    upload_files = await vault.list_files(upload_prefix)

    if not upload_files:
        raise ValueError(f"No files found in {upload_prefix}")

    # 2. Download and parse each file
    all_exchanges = []
    for file_path in upload_files:
        if file_path.endswith("/.keep"):
            continue

        content = await vault.download_file(file_path)

        # Use existing chat parser
        from memory.ingest.chat_parser import parse_chat_export
        exchanges = parse_chat_export(content, source_type)
        all_exchanges.extend(exchanges)

    logger.info(f"Parsed {len(all_exchanges)} exchanges from {len(upload_files)} files")

    # 3. Load existing nodes for dedup FROM LOCAL VAULT
    existing_nodes = []
    try:
        existing_data = local_vault.read_nodes()
        existing_nodes = [MemoryNode.from_dict(d) for d in existing_data]
        logger.info(f"Loaded {len(existing_nodes)} existing nodes from local vault")
    except Exception as e:
        logger.info(f"No existing nodes found in local vault: {e}")

    # 4. Deduplicate (inline content-hash based)
    existing_hashes = set()
    for node in existing_nodes:
        h = hashlib.sha256(f"{node.human_content[:100]}{node.assistant_content[:100]}".encode()).hexdigest()[:16]
        existing_hashes.add(h)

    new_exchanges = []
    dedup_count = 0
    for ex in all_exchanges:
        h = hashlib.sha256(f"{ex['human'][:100]}{ex['assistant'][:100]}".encode()).hexdigest()[:16]
        if h not in existing_hashes:
            new_exchanges.append(ex)
            existing_hashes.add(h)
        else:
            dedup_count += 1

    logger.info(f"After dedup: {len(new_exchanges)} new, {dedup_count} duplicates skipped")

    if not new_exchanges:
        return {"nodes_created": 0, "nodes_deduplicated": dedup_count}

    # 5. Convert to nodes
    nodes = [exchange_to_node(ex, user_id=user_id) for ex in new_exchanges]

    # 6. Embed (GPU parallel)
    from memory.embedder import create_embedder
    import os

    # Use Modal (serverless GPU) if available, else fall back to DeepInfra
    provider = os.getenv("EMBEDDING_PROVIDER", "deepinfra")
    embedder = create_embedder(provider=provider)

    texts = [f"{n.human_content} {n.assistant_content}" for n in nodes]

    if provider == "modal":
        # Modal handles batching internally on GPU - send larger chunks
        embeddings = await embedder.embed_batch(
            texts,
            batch_size=256,  # GPU can handle big batches
            max_concurrent=2,  # Modal handles parallelism
            show_progress=True
        )
    else:
        # DeepInfra rate limited to 180 RPM
        embeddings = await embedder.embed_batch(
            texts,
            batch_size=64,
            max_concurrent=4,
            show_progress=True
        )

    # 7. Cluster (optional, can skip for now)
    # from streaming_cluster import StreamingClusterEngine
    # ...

    # ================================================================
    # 8. SAVE TO LOCAL VAULT FIRST (NEW!)
    # ================================================================
    
    # Merge with existing
    all_nodes = existing_nodes + nodes
    
    # Convert to dict format for storage
    all_nodes_dict = [n.to_dict() for n in all_nodes]
    
    # Write to local vault (this will also queue for B2 sync)
    local_vault.write_nodes(all_nodes_dict, sync=False)  # Don't auto-sync yet
    
    # Handle embeddings
    existing_embeddings = local_vault.read_node_embeddings()
    if existing_embeddings is not None:
        all_embeddings = np.vstack([existing_embeddings, np.array(embeddings)])
    else:
        all_embeddings = np.array(embeddings)
        
    # Write embeddings to local vault
    local_vault.write_node_embeddings(all_embeddings, sync=False)  # Don't auto-sync yet
    
    # Update dedup index in local vault
    existing_dedup = local_vault.read_dedup_index()
    updated_dedup = existing_dedup.copy() if existing_dedup else {}
    if "ingested_ids" not in updated_dedup:
        updated_dedup["ingested_ids"] = []
    
    # Add new node IDs and content hashes to dedup index
    for node in nodes:
        updated_dedup["ingested_ids"].append(node.id)
        content_hash = hashlib.sha256(node.combined_content.encode()).hexdigest()[:16]
        updated_dedup["ingested_ids"].append(content_hash)
    
    local_vault.write_dedup_index(updated_dedup, sync=False)
    
    # ================================================================
    # 9. SYNC TO B2 IN BACKGROUND (NEW!)
    # ================================================================
    
    try:
        await local_vault.sync_to_b2()
        logger.info("Successfully synced to B2 backup")
    except Exception as e:
        logger.warning(f"B2 sync failed (data still saved locally): {e}")

    logger.info(f"Saved {len(nodes)} new nodes to LOCAL VAULT ({len(all_nodes)} total)")
    logger.info(f"Local vault status: {local_vault.get_status()}")

    return {
        "nodes_created": len(nodes),
        "nodes_deduplicated": dedup_count,
        "total_nodes": len(all_nodes),
        "local_vault_path": str(local_vault.root),
        "sync_status": "completed"
    }


def exchange_to_node(exchange: dict, user_id: str) -> MemoryNode:
    """Convert a parsed exchange to a MemoryNode with user scoping."""
    from core.schemas import MemoryNode, Source

    return MemoryNode(
        id=exchange.get("id") or hashlib.sha256(
            f"{exchange['human'][:100]}{exchange['assistant'][:100]}".encode()
        ).hexdigest()[:16],
        source=Source(exchange.get("source", "unknown")),
        conversation_id=exchange.get("conversation_id", "import"),
        sequence_index=exchange.get("sequence_index", 0),
        created_at=exchange.get("timestamp") or datetime.now(),
        human_content=exchange["human"],
        assistant_content=exchange["assistant"],
        user_id=user_id,  # CRITICAL: Scope to user
        tenant_id=None,   # Personal tier, no tenant
    )