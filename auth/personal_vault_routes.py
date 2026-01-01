"""
Personal Vault Routes - Upload and status endpoints

Endpoints:
- POST /api/personal/vault/upload - Upload chat export
- GET /api/personal/vault/status - Get vault status
- GET /api/personal/vault/upload/{upload_id} - Get upload progress

Version: 1.0.0
"""

import logging
import json
from uuid import UUID
from datetime import datetime
from typing import Optional
from io import BytesIO

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from auth.personal_auth import get_personal_auth_service, SessionData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personal/vault", tags=["personal-vault"])

# Response models
class UploadResponse(BaseModel):
    upload_id: str
    status: str
    message: str

class VaultStatus(BaseModel):
    node_count: int
    total_bytes: int
    status: str
    last_sync_at: Optional[datetime]
    uploads: list[dict]

class UploadProgress(BaseModel):
    upload_id: str
    status: str
    progress_pct: int
    nodes_created: int
    nodes_deduplicated: int
    error_message: Optional[str]


# =============================================================================
# DEPENDENCIES
# =============================================================================

async def get_current_user(request: Request) -> SessionData:
    """Dependency to get current user from session cookie."""
    auth = await get_personal_auth_service(request.app.state.redis, request.app.state.db_pool)

    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(401, "Not authenticated")

    session = await auth.get_session(session_id)
    if not session:
        raise HTTPException(401, "Session expired")

    # Refresh session TTL on activity
    await auth.refresh_session(session_id)

    return session


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def detect_source_type(filename: str, content_sample: bytes) -> str:
    """Detect the source type from filename or content."""
    filename_lower = filename.lower()

    if "anthropic" in filename_lower or "claude" in filename_lower:
        return "anthropic"
    elif "openai" in filename_lower or "chatgpt" in filename_lower:
        return "openai"
    elif "grok" in filename_lower:
        return "grok"
    elif "gemini" in filename_lower:
        return "gemini"

    # Try to detect from content structure
    try:
        data = json.loads(content_sample[:10000].decode('utf-8', errors='ignore'))

        # Anthropic format has specific structure
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if "uuid" in first and "chat_messages" in first:
                return "anthropic"
            elif "mapping" in first:
                return "openai"
    except:
        pass

    return "unknown"


async def process_upload_job(
    upload_id: str,
    user_id: str,
    source_type: str,
    file_path: str,
    db_pool,
    config: dict
):
    """
    Background job to process an upload.

    1. Download from B2 (or use local temp)
    2. Run through ingestion pipeline
    3. Update upload status
    """
    logger.info(f"Starting upload processing: {upload_id}")

    async with db_pool.acquire() as conn:
        # Mark as processing
        await conn.execute("""
            UPDATE personal.vault_uploads
            SET status = 'processing', processing_started_at = NOW()
            WHERE id = $1
        """, UUID(upload_id))

    try:
        # Run the user-scoped pipeline
        from memory.ingest.pipeline import run_pipeline_for_user
        result = await run_pipeline_for_user(
            user_id=user_id,
            source_type=source_type,
            upload_id=upload_id,
            config=config
        )

        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE personal.vault_uploads
                SET status = 'complete',
                    progress_pct = 100,
                    nodes_created = $2,
                    nodes_deduplicated = $3,
                    processing_completed_at = NOW()
                WHERE id = $1
            """, UUID(upload_id), result["nodes_created"], result["nodes_deduplicated"])

            # Update vault stats
            await conn.execute("""
                UPDATE personal.vaults
                SET node_count = node_count + $2,
                    status = 'ready',
                    last_sync_at = NOW()
                WHERE user_id = $1
            """, UUID(user_id), result["nodes_created"])

        logger.info(f"Upload {upload_id} complete: {result['nodes_created']} nodes")

    except Exception as e:
        logger.exception(f"Upload {upload_id} failed: {e}")

        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE personal.vault_uploads
                SET status = 'failed', error_message = $2
                WHERE id = $1
            """, UUID(upload_id), str(e))


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/upload", response_model=UploadResponse)
async def upload_chat_export(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: SessionData = Depends(get_current_user),
):
    """
    Upload a chat export file for processing.

    Accepts:
    - Anthropic conversations.json
    - OpenAI export .zip or conversations.json
    - Grok/Gemini exports

    Returns upload_id for progress tracking.
    """
    user_id = session.user_id

    # Read file content
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    # Detect source type
    source_type = detect_source_type(file.filename, content)

    # Prepare destination filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_filename = f"{timestamp}_{file.filename}"

    # Upload to B2
    from core.vault_service import get_vault_service
    from core.config_loader import load_config

    config = load_config()
    vault_service = get_vault_service(config)
    await vault_service.upload_file(
        user_id=user_id,
        source_type=source_type,
        filename=dest_filename,
        file_data=BytesIO(content),
        content_type=file.content_type or "application/json"
    )

    # Create upload record
    db_pool = request.app.state.db_pool

    async with db_pool.acquire() as conn:
        # Ensure vault exists for user
        vault = await conn.fetchrow(
            "SELECT id FROM personal.vaults WHERE user_id = $1",
            UUID(user_id)
        )

        if not vault:
            # Create vault if it doesn't exist (B2 structure already created on signup)
            vault = await conn.fetchrow("""
                INSERT INTO personal.vaults (user_id, prefix, status)
                VALUES ($1, $2, 'empty')
                RETURNING id
            """, UUID(user_id), f"users/{user_id}")

        # Create upload record
        upload = await conn.fetchrow("""
            INSERT INTO personal.vault_uploads (
                vault_id, source_type, original_filename,
                uploaded_bytes, status, progress_pct
            )
            VALUES ($1, $2, $3, $4, 'pending', 0)
            RETURNING id
        """, vault["id"], source_type, file.filename, len(content))

        upload_id = str(upload["id"])

    # Queue background job for pipeline processing
    background_tasks.add_task(
        process_upload_job,
        upload_id=upload_id,
        user_id=user_id,
        source_type=source_type,
        file_path=f"users/{user_id}/uploads/{source_type}/{dest_filename}",
        db_pool=db_pool,
        config=config
    )

    logger.info(f"Queued upload {upload_id} for user {user_id}: {source_type}")

    return UploadResponse(
        upload_id=upload_id,
        status="pending",
        message=f"Upload received. Processing {source_type} export..."
    )


@router.get("/status", response_model=VaultStatus)
async def get_vault_status(
    request: Request,
    session: SessionData = Depends(get_current_user),
):
    """Get current vault status and recent uploads."""
    user_id = session.user_id
    db_pool = request.app.state.db_pool

    async with db_pool.acquire() as conn:
        # Get vault info
        vault = await conn.fetchrow("""
            SELECT node_count, total_bytes, status, last_sync_at
            FROM personal.vaults
            WHERE user_id = $1
        """, UUID(user_id))

        if not vault:
            # No vault yet - return empty state
            return VaultStatus(
                node_count=0,
                total_bytes=0,
                status="empty",
                last_sync_at=None,
                uploads=[]
            )

        # Get recent uploads
        uploads = await conn.fetch("""
            SELECT id, source_type, original_filename, status,
                   progress_pct, nodes_created, uploaded_at
            FROM personal.vault_uploads
            WHERE vault_id = (SELECT id FROM personal.vaults WHERE user_id = $1)
            ORDER BY uploaded_at DESC
            LIMIT 10
        """, UUID(user_id))

        upload_list = [
            {
                "id": str(u["id"]),
                "source_type": u["source_type"],
                "filename": u["original_filename"],
                "status": u["status"],
                "progress_pct": u["progress_pct"],
                "nodes_created": u["nodes_created"],
                "uploaded_at": u["uploaded_at"].isoformat() if u["uploaded_at"] else None
            }
            for u in uploads
        ]

        return VaultStatus(
            node_count=vault["node_count"],
            total_bytes=vault["total_bytes"],
            status=vault["status"],
            last_sync_at=vault["last_sync_at"],
            uploads=upload_list
        )


@router.get("/upload/{upload_id}", response_model=UploadProgress)
async def get_upload_progress(
    upload_id: str,
    request: Request,
    session: SessionData = Depends(get_current_user),
):
    """Get progress of a specific upload."""
    user_id = session.user_id
    db_pool = request.app.state.db_pool

    async with db_pool.acquire() as conn:
        # Verify upload belongs to user and get details
        upload = await conn.fetchrow("""
            SELECT u.id, u.status, u.progress_pct, u.nodes_created,
                   u.nodes_deduplicated, u.error_message
            FROM personal.vault_uploads u
            JOIN personal.vaults v ON u.vault_id = v.id
            WHERE u.id = $1 AND v.user_id = $2
        """, UUID(upload_id), UUID(user_id))

        if not upload:
            raise HTTPException(404, "Upload not found")

        return UploadProgress(
            upload_id=upload_id,
            status=upload["status"],
            progress_pct=upload["progress_pct"],
            nodes_created=upload["nodes_created"] or 0,
            nodes_deduplicated=upload["nodes_deduplicated"] or 0,
            error_message=upload["error_message"]
        )
