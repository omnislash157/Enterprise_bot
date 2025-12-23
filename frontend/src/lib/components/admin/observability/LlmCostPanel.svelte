<!--
  LlmCostPanel - LLM usage and cost tracking
-->

<script lang="ts">
    import { metricsSnapshot } from '$lib/stores/metrics';

    $: llm = $metricsSnapshot?.llm;

    function formatCost(usd: number): string {
        if (usd < 0.01) return `$${(usd * 100).toFixed(2)}¢`;
        return `$${usd.toFixed(2)}`;
    }

    function formatTokens(n: number): string {
        if (n > 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
        if (n > 1_000) return `${(n / 1_000).toFixed(1)}K`;
        return n.toString();
    }
</script>

<div class="llm-panel">
    <div class="panel-header">
        <h3>⚡ LLM Performance</h3>
        {#if llm}
            <span class="cost-badge">{formatCost(llm.cost_total_usd)}</span>
        {/if}
    </div>

    {#if llm}
        <div class="metrics-row">
            <div class="metric">
                <div class="metric-value">{llm.first_token_avg_ms.toFixed(0)}</div>
                <div class="metric-label">First Token (ms)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{llm.latency_avg_ms.toFixed(0)}</div>
                <div class="metric-label">Avg Latency (ms)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{llm.latency_p95_ms.toFixed(0)}</div>
                <div class="metric-label">P95 Latency (ms)</div>
            </div>
        </div>

        <div class="token-stats">
            <div class="token-row">
                <span class="token-label">Input Tokens</span>
                <span class="token-value">{formatTokens(llm.tokens_in_total)}</span>
            </div>
            <div class="token-row">
                <span class="token-label">Output Tokens</span>
                <span class="token-value">{formatTokens(llm.tokens_out_total)}</span>
            </div>
            <div class="token-row">
                <span class="token-label">Requests</span>
                <span class="token-value">{llm.total_requests.toLocaleString()}</span>
            </div>
            <div class="token-row error">
                <span class="token-label">Errors</span>
                <span class="token-value">{llm.error_count}</span>
            </div>
        </div>
    {:else}
        <div class="loading">Loading LLM metrics...</div>
    {/if}
</div>

<style>
    .llm-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 200, 0, 0.3);
        border-radius: 8px;
        padding: 16px;
    }

    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }

    .panel-header h3 {
        margin: 0;
        font-size: 14px;
        color: #ffc800;
    }

    .cost-badge {
        background: rgba(0, 255, 65, 0.2);
        color: #00ff41;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    .metrics-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 16px;
    }

    .metric {
        text-align: center;
        flex: 1;
    }

    .metric-value {
        font-size: 20px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }

    .metric-label {
        font-size: 10px;
        color: #888;
        margin-top: 4px;
    }

    .token-stats {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .token-row {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
    }

    .token-label {
        color: #888;
    }

    .token-value {
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }

    .token-row.error .token-value {
        color: #ff4444;
    }

    .loading {
        color: #666;
        text-align: center;
        padding: 20px;
    }
</style>
