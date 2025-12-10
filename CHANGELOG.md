# Changelog

## 2024-12-10 - Enterprise Fork v1 LIVE (elegant-borg)

**Status: PRODUCTION** - Driscoll Assistant operational.

### Deploy Fixes (same day)
- `main.py` moved to repo root for Railway imports
- WebSocket URL uses `window.location.host` for same-origin deploys
- `config_loader.py` uses script directory, not cwd
- Division categories default to division name (fixes "No docs found")
- Model name: `grok-4-fast-reasoning` (not `grok-4-1-fast-reasoning`)
- Added xAI error logging for debugging
- `python-docx` added to requirements.txt

### Removed
- `cog_twin.py` imports (memory/extraction engine)
- `IngestPipeline`, `ChatParserFactory`, `agents` imports
- MemoryCanvas (Threlte 3D visualization)
- SwarmPanel (agent orchestration UI)
- AnalyticsDashboard (cognitive state metrics)
- WorkspaceNav component
- Upload/ingest functionality
- pyodbc, hdbscan, river dependencies

### Added
- `python-docx` dependency for doc loading
- Clean `enterprise_twin.py` (context stuffing only)
- Clean `enterprise_tenant.py` (simple dataclass)
- Division-aware `doc_loader.py`

### Changed
- Frontend: Chat + Artifacts panels only
- Branding: "Driscoll Assistant"
- Status bar: Shows "Enterprise" mode
- Placeholder: "Ask about company procedures..."

### Preserved
- Cyberpunk theme (black + neon green)
- WebSocket streaming
- Artifact rendering
- Theme toggle
- Panel dock/float/fullscreen modes
- Memory infrastructure (stubbed for v2)
