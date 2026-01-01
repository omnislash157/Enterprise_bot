<!--
  RealtimeSessions - Live active sessions display
-->

<script lang="ts">
    import type { RealtimeSession } from '$lib/stores/analytics';

    export let sessions: RealtimeSession[] = [];
    export let loading: boolean = false;

    function timeAgo(isoString: string): string {
        const seconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
        if (seconds < 60) return `${seconds}s ago`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        return `${Math.floor(seconds / 3600)}h ago`;
    }
</script>

<div class="realtime-widget panel p-4">
    <div class="header flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-[#00ff41]">
            <span class="live-dot"></span>
            Active Now
        </h3>
        <span class="text-2xl font-bold text-[#00ff41]">{sessions.length}</span>
    </div>

    {#if loading}
        <div class="animate-pulse space-y-2">
            {#each [1, 2, 3] as _}
                <div class="h-8 bg-[#222] rounded"></div>
            {/each}
        </div>
    {:else if sessions.length === 0}
        <div class="text-center text-[#808080] py-4">
            No active sessions
        </div>
    {:else}
        <div class="sessions-list space-y-2 max-h-[200px] overflow-y-auto">
            {#each sessions as session}
                <div class="session-row flex items-center justify-between text-sm p-2 rounded bg-[#1a1a1a]">
                    <div class="user-info">
                        <div class="email text-[#e0e0e0] truncate max-w-[150px]">
                            {session.user_email}
                        </div>
                        <div class="dept text-xs text-[#808080]">
                            {session.department}
                        </div>
                    </div>
                    <div class="activity text-right">
                        <div class="queries text-[#00ffff]">
                            {session.query_count} queries
                        </div>
                        <div class="time text-xs text-[#808080]">
                            {timeAgo(session.last_activity)}
                        </div>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .realtime-widget {
        background: var(--bg-secondary);
        border: 1px solid var(--border-dim);
        border-radius: 8px;
    }

    .live-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #00ff41;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.7); }
        50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(0, 255, 65, 0); }
    }
</style>
