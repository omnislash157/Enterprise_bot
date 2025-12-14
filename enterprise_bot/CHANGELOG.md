# Changelog

## 2024-12-10 - Enterprise Fork v1 (elegant-borg)

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
