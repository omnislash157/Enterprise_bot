#!/usr/bin/env python3
"""
Claude Agent SDK - One-Shot Runner
Execute a single prompt and watch Claude work.

Usage:
    python claude_run.py "Fix the bug in auth.py and run tests"
    python claude_run.py --file prompts/phase3.txt
    echo "Scan codebase" | python claude_run.py -
"""

import asyncio
import sys
import os
import argparse

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        ToolUseBlock,
        TextBlock,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    DIM = '\033[2m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


async def run_prompt(
    prompt: str,
    cwd: str = None,
    mode: str = "acceptEdits",
    tools: list = None,
    system_prompt: str = None,
    verbose: bool = True
):
    """Execute a single prompt and stream results."""
    
    if not SDK_AVAILABLE:
        print(f"{Colors.RED}Error: claude_agent_sdk not installed{Colors.RESET}")
        print("Install with: pip install claude-agent-sdk")
        return False
    
    cwd = cwd or os.getcwd()
    tools = tools or ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
    
    # Format prompt - compress to single line
    prompt = ' '.join(line.strip() for line in prompt.strip().split('\n') if line.strip())
    
    if verbose:
        print(f"{Colors.DIM}Working directory: {cwd}{Colors.RESET}")
        print(f"{Colors.DIM}Prompt: {prompt[:80]}...{Colors.RESET}" if len(prompt) > 80 else f"{Colors.DIM}Prompt: {prompt}{Colors.RESET}")
        print()
    
    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=tools,
        permission_mode=mode,
        system_prompt=system_prompt
    )
    
    success = True
    current_text = ""
    
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        new_text = block.text
                        if new_text.startswith(current_text):
                            print(new_text[len(current_text):], end='', flush=True)
                        else:
                            print(new_text, end='', flush=True)
                        current_text = new_text
                        
                    elif isinstance(block, ToolUseBlock):
                        if verbose:
                            print(f"\n{Colors.YELLOW}[{block.name}]{Colors.RESET} ", end='')
                            if hasattr(block, 'input') and block.input:
                                input_str = str(block.input)
                                if len(input_str) > 80:
                                    input_str = input_str[:80] + "..."
                                print(f"{Colors.DIM}{input_str}{Colors.RESET}")
                        
            elif isinstance(message, ResultMessage):
                if message.subtype == "error":
                    success = False
                    print(f"\n{Colors.RED}[Error]{Colors.RESET}")
                elif verbose:
                    print(f"\n{Colors.GREEN}[Done]{Colors.RESET}")
                    
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        success = False
    
    print()
    return success


# Pre-defined prompts for CogTwin merge phases
MERGE_PROMPTS = {
    "phase3": """Phase 3 Auth Scoping: 1) In schemas.py add user_id and tenant_id Optional[str] fields to MemoryNode class. 2) In main.py websocket_endpoint, extract user_id and tenant_id from auth context and pass to engine.think(). 3) In cog_twin.py modify think() to accept user_id and tenant_id params and pass to retriever. 4) In retrieval.py modify retrieve() to filter nodes by user_id or tenant_id before similarity search - if neither provided return empty results. 5) In memory_pipeline.py stamp new memories with user_id/tenant_id. Test by running python main.py. Report all changes.""",

    "phase4": """Phase 4 Extraction Toggle: 1) Verify config.yaml has features.extraction_enabled flag. 2) In main.py find the upload endpoint and add a guard that raises HTTPException 403 if extraction_enabled is false. 3) Test by setting extraction_enabled: false and confirming upload is blocked. Report changes.""",

    "phase5a": """Phase 5 Part 1 - Database Schema: Create database migration script in db/migrations/001_memory_tables.sql with tables: users (id UUID, auth_provider, external_id, email, tenant_id, created_at), tenants (id UUID, name, azure_tenant_id, config JSONB, voice_engine), memory_nodes (id UUID, user_id, tenant_id, conversation_id, human_content, assistant_content, source, embedding VECTOR(1024), intent_type, complexity, cluster_id, created_at), episodic_memories (same pattern), documents (tenant_id, department, title, content, chunk_index, embedding). Add pgvector extension and ivfflat indexes. Save file and confirm path.""",

    "phase5b": """Phase 5 Part 2 - PostgreSQL Backend: Create postgres_backend.py with PostgresBackend class using asyncpg and pgvector. Methods: connect(), get_nodes(user_id, tenant_id), vector_search(embedding, user_id, tenant_id, top_k), insert_node(node). Use connection pooling. Handle the VECTOR type properly with register_vector. Report implementation.""",

    "phase5c": """Phase 5 Part 3 - Backend Abstraction: Create memory_backend.py with abstract MemoryBackend base class defining interface: get_nodes, vector_search, insert_node. Create FileBackend class wrapping existing file-based retrieval.py logic. Create factory function get_backend(config) that returns FileBackend or PostgresBackend based on cfg('memory.backend'). Update cog_twin.py to use the factory. Test with backend: file config. Report changes.""",

    "scan": """Scan this codebase and create WIRING_MAP.md documenting: 1) Architecture overview with ASCII diagram 2) Data flow patterns 3) Entry points and API routes 4) Key module responsibilities 5) Integration points. Save the file and confirm path when done.""",

    "test": """Run python main.py to test server startup. If it fails, diagnose and fix the issue. Report what you found.""",

    # Nerve Center observability presets
    "nerve0": """Create src/lib/components/nervecenter/StateMonitor.svelte - a real-time debug panel. First read src/lib/stores/session.ts to understand store structure. Component must: 1) Track isStreaming, currentStream.length, cognitiveState.phase, websocket.connected. 2) Log state changes with timestamps to scrollable list. 3) Show computed CheekyLoader indicator. 4) Use cyberpunk styling: rgba(0,0,0,0.6) background, #00ff41 accents, JetBrains Mono font. Then add StateMonitor to src/routes/nervecenter/+page.svelte in a debug panel section.""",

    "nerve1": """Create src/lib/components/nervecenter/LaneHeatmap.svelte showing the 5 retrieval lanes: FAISS (brain), BM25 (search), SQUIRREL (temporal), EPISODIC (arcs), TRACES (reasoning). Each lane shows: heat bar 0-100%, call count, avg latency ms. Color gradient from rgba(0,255,65,0.1) cold to rgba(255,100,0,0.8) hot. Read from session.observability.metrics.retrieval_lanes. Match existing nervecenter component patterns.""",

    "nerve2": """In main.py add observability: 1) Create MetricsCollector class with lane_stats dict, tokens tracking. 2) Add emit_state_transition(ws, from_state, to_state, trigger) function sending {type:'state_transition', timestamp, from_state, to_state, trigger}. 3) In websocket handler emit transitions on phase changes. 4) Create async metrics_loop pushing system_metrics every 5s.""",

    "phase5wire": """Wire postgres backend: 1) In memory_backend.py add 'try: from postgres_backend import PostgresBackend as AsyncPostgresBackend; POSTGRES_AVAILABLE=True except: POSTGRES_AVAILABLE=False'. 2) Replace get_backend postgres branch to check POSTGRES_AVAILABLE, build connection string from config or AZURE_PG_CONNECTION_STRING env var. 3) Delete stub PostgresBackend class (the one with NotImplementedError).""",

    "phase6": """Cleanup deprecated code: 1) mkdir -p archive/deprecated && mv enterprise_twin.py archive/deprecated/. 2) In config_loader.py change context_stuffing_enabled() to return False with DEPRECATED docstring. 3) In test_setup.py remove 'from enterprise_twin import EnterpriseTwin' and its test. 4) In config.yaml update context_stuffing comment to DEPRECATED. 5) Run python -c 'from main import app' to verify no broken imports.""",
}


async def main():
    parser = argparse.ArgumentParser(
        description="Execute a single Claude Agent SDK prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Pre-defined prompts (use --preset):
  {', '.join(MERGE_PROMPTS.keys())}

Examples:
  python claude_run.py "Fix bugs in auth.py"
  python claude_run.py --preset phase3
  python claude_run.py --file prompts/task.txt
  echo "Analyze codebase" | python claude_run.py -
        """
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to execute (use - for stdin)"
    )
    parser.add_argument(
        "--preset", "-p",
        choices=list(MERGE_PROMPTS.keys()),
        help="Use a pre-defined prompt"
    )
    parser.add_argument(
        "--file", "-f",
        help="Read prompt from file"
    )
    parser.add_argument(
        "--cwd", "-c",
        default=os.getcwd(),
        help="Working directory"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["acceptEdits", "bypassPermissions", "default"],
        default="acceptEdits",
        help="Permission mode"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )
    
    args = parser.parse_args()
    
    # Determine prompt source
    if args.preset:
        prompt = MERGE_PROMPTS[args.preset]
    elif args.file:
        with open(args.file) as f:
            prompt = f.read()
    elif args.prompt == "-":
        prompt = sys.stdin.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.print_help()
        sys.exit(1)
    
    success = await run_prompt(
        prompt=prompt,
        cwd=args.cwd,
        mode=args.mode,
        verbose=not args.quiet
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
