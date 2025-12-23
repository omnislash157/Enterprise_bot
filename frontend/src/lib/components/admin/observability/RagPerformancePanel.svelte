<!--
  RagPerformancePanel - RAG pipeline metrics

  Displays: Latency breakdown, cache rates, chunk stats
-->

<script lang="ts">
    import { metricsSnapshot } from '$lib/stores/metrics';

    $: rag = $metricsSnapshot?.rag;
    $: cache = $metricsSnapshot?.cache;
</script>

<div class="rag-panel">
    <div class="panel-header">
        <h3>🧠 RAG Pipeline</h3>
    </div>

    {#if rag && cache}
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{rag.latency_avg_ms.toFixed(0)}<span class="unit">ms</span></div>
                <div class="metric-label">Avg Latency</div>
            </div>

            <div class="metric-card">
                <div class="metric-value">{rag.latency_p95_ms.toFixed(0)}<span class="unit">ms</span></div>
                <div class="metric-label">P95 Latency</div>
            </div>

            <div class="metric-card highlight">
                <div class="metric-value">{cache.rag_hit_rate.toFixed(0)}<span class="unit">%</span></div>
                <div class="metric-label">Cache Hit Rate</div>
            </div>

            <div class="metric-card">
                <div class="metric-value">{rag.avg_chunks.toFixed(1)}</div>
                <div class="metric-label">Avg Chunks</div>
            </div>
        </div>

        <div class="breakdown">
            <div class="breakdown-title">Latency Breakdown</div>
            <div class="breakdown-bar">
                <div
                    class="segment embedding"
                    style="width: {(rag.embedding_avg_ms / rag.latency_avg_ms) * 100}%"
                    title="Embedding: {rag.embedding_avg_ms.toFixed(0)}ms"
                ></div>
                <div
                    class="segment search"
                    style="width: {(rag.search_avg_ms / rag.latency_avg_ms) * 100}%"
                    title="Search: {rag.search_avg_ms.toFixed(0)}ms"
                ></div>
            </div>
            <div class="breakdown-legend">
                <span class="legend-item"><span class="dot embedding"></span> Embedding</span>
                <span class="legend-item"><span class="dot search"></span> Vector Search</span>
            </div>
        </div>

        <div class="stats-footer">
            <span>Total Queries: <strong>{rag.total_queries.toLocaleString()}</strong></span>
            <span>Zero-Chunk: <strong>{rag.zero_chunk_rate.toFixed(1)}%</strong></span>
        </div>
    {:else}
        <div class="loading">Loading RAG metrics...</div>
    {/if}
</div>

<style>
    .rag-panel {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 8px;
        padding: 16px;
    }

    .panel-header h3 {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: #00ffff;
    }

    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }

    .metric-card {
        background: rgba(0, 255, 255, 0.05);
        border-radius: 6px;
        padding: 12px;
        text-align: center;
    }

    .metric-card.highlight {
        background: rgba(0, 255, 65, 0.1);
        border: 1px solid rgba(0, 255, 65, 0.3);
    }

    .metric-value {
        font-size: 24px;
        font-weight: 600;
        color: #e0e0e0;
        font-family: 'JetBrains Mono', monospace;
    }

    .unit {
        font-size: 12px;
        color: #888;
        margin-left: 2px;
    }

    .metric-label {
        font-size: 11px;
        color: #888;
        margin-top: 4px;
    }

    .breakdown {
        margin-bottom: 16px;
    }

    .breakdown-title {
        font-size: 11px;
        color: #888;
        margin-bottom: 8px;
    }

    .breakdown-bar {
        height: 12px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        overflow: hidden;
        display: flex;
    }

    .segment {
        height: 100%;
        transition: width 0.3s ease;
    }

    .segment.embedding {
        background: #ff00ff;
    }

    .segment.search {
        background: #00ffff;
    }

    .breakdown-legend {
        display: flex;
        gap: 16px;
        margin-top: 8px;
        font-size: 10px;
        color: #888;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }

    .dot.embedding {
        background: #ff00ff;
    }

    .dot.search {
        background: #00ffff;
    }

    .stats-footer {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: #666;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .stats-footer strong {
        color: #e0e0e0;
    }

    .loading {
        color: #666;
        text-align: center;
        padding: 20px;
    }
</style>
