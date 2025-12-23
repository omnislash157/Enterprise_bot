<!--
  Alert Dashboard - Rules and fired alerts
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import { observabilityStore, alertRules, alertInstances, firingAlerts } from '$lib/stores/observability';

    let activeTab = 'instances';

    onMount(() => {
        observabilityStore.loadAlertRules();
        observabilityStore.loadAlertInstances();
    });

    function getSeverityColor(severity: string): string {
        switch (severity) {
            case 'info': return '#36a64f';
            case 'warning': return '#ffc800';
            case 'critical': return '#ff0055';
            default: return '#888';
        }
    }

    function getStatusColor(status: string): string {
        switch (status) {
            case 'firing': return '#ff0055';
            case 'acknowledged': return '#ffc800';
            case 'resolved': return '#00ff41';
            default: return '#888';
        }
    }
</script>

<svelte:head>
    <title>Alerts | CogTwin Admin</title>
</svelte:head>

<div class="alerts-page">
    <header class="page-header">
        <h1>Alert Management</h1>

        {#if $firingAlerts.length > 0}
            <div class="firing-badge">
                {$firingAlerts.length} Firing
            </div>
        {/if}
    </header>

    <div class="tabs">
        <button
            class="tab"
            class:active={activeTab === 'instances'}
            on:click={() => activeTab = 'instances'}
        >
            Alerts ({$alertInstances.length})
        </button>
        <button
            class="tab"
            class:active={activeTab === 'rules'}
            on:click={() => activeTab = 'rules'}
        >
            Rules ({$alertRules.length})
        </button>
    </div>

    {#if activeTab === 'instances'}
        <div class="alert-list">
            {#each $alertInstances as alert}
                <div class="alert-card" class:firing={alert.status === 'firing'}>
                    <div class="alert-header">
                        <span class="severity" style="background: {getSeverityColor(alert.severity)}">
                            {alert.severity.toUpperCase()}
                        </span>
                        <span class="rule-name">{alert.rule_name}</span>
                        <span class="status" style="color: {getStatusColor(alert.status)}">
                            {alert.status}
                        </span>
                    </div>

                    <div class="alert-body">
                        <p class="message">{alert.message}</p>
                        <div class="meta">
                            <span>Value: <strong>{alert.metric_value.toFixed(2)}</strong></span>
                            <span>Threshold: <strong>{alert.threshold_value}</strong></span>
                            <span>Triggered: <strong>{new Date(alert.triggered_at).toLocaleString()}</strong></span>
                        </div>
                    </div>

                    {#if alert.status === 'firing'}
                        <div class="alert-actions">
                            <button
                                class="ack-btn"
                                on:click={() => observabilityStore.acknowledgeAlert(alert.id)}
                            >
                                Acknowledge
                            </button>
                        </div>
                    {/if}
                </div>
            {/each}

            {#if $alertInstances.length === 0}
                <div class="empty">
                    No alerts - everything is running smoothly
                </div>
            {/if}
        </div>
    {:else}
        <div class="rules-list">
            {#each $alertRules as rule}
                <div class="rule-card" class:disabled={!rule.enabled}>
                    <div class="rule-header">
                        <span class="rule-name">{rule.name}</span>
                        <label class="toggle">
                            <input
                                type="checkbox"
                                checked={rule.enabled}
                                on:change={() => observabilityStore.toggleAlertRule(rule.id, !rule.enabled)}
                            />
                            <span class="slider"></span>
                        </label>
                    </div>

                    <p class="rule-desc">{rule.description || 'No description'}</p>

                    <div class="rule-meta">
                        <span>Metric: <strong>{rule.metric_type}</strong></span>
                        <span>Condition: <strong>{rule.condition} {rule.threshold}</strong></span>
                        <span>Severity:
                            <strong style="color: {getSeverityColor(rule.severity)}">
                                {rule.severity}
                            </strong>
                        </span>
                    </div>

                    {#if rule.last_triggered_at}
                        <div class="last-triggered">
                            Last triggered: {new Date(rule.last_triggered_at).toLocaleString()}
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .alerts-page {
        padding: 24px;
    }

    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
    }

    .page-header h1 {
        margin: 0;
        font-size: 24px;
        color: #e0e0e0;
    }

    .firing-badge {
        padding: 8px 16px;
        background: rgba(255, 0, 85, 0.2);
        border: 1px solid rgba(255, 0, 85, 0.5);
        border-radius: 20px;
        color: #ff0055;
        font-weight: 600;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    .tabs {
        display: flex;
        gap: 4px;
        margin-bottom: 24px;
    }

    .tab {
        padding: 10px 20px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px 6px 0 0;
        color: #888;
        cursor: pointer;
        transition: all 0.2s;
    }

    .tab.active {
        background: rgba(255, 255, 255, 0.1);
        color: #e0e0e0;
        border-bottom-color: transparent;
    }

    .alert-list, .rules-list {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .alert-card, .rule-card {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 16px;
    }

    .alert-card.firing {
        border-color: rgba(255, 0, 85, 0.5);
        background: rgba(255, 0, 85, 0.05);
    }

    .alert-header, .rule-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }

    .severity {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 700;
        color: white;
    }

    .rule-name {
        font-size: 16px;
        font-weight: 600;
        color: #e0e0e0;
        flex: 1;
    }

    .status {
        font-size: 12px;
        font-weight: 600;
    }

    .message {
        margin: 0 0 12px 0;
        color: #e0e0e0;
    }

    .meta, .rule-meta {
        display: flex;
        gap: 24px;
        font-size: 13px;
        color: #888;
    }

    .meta strong, .rule-meta strong {
        color: #e0e0e0;
    }

    .alert-actions {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .ack-btn {
        padding: 8px 16px;
        background: rgba(255, 200, 0, 0.2);
        border: 1px solid rgba(255, 200, 0, 0.5);
        border-radius: 6px;
        color: #ffc800;
        cursor: pointer;
    }

    .rule-card.disabled {
        opacity: 0.5;
    }

    .rule-desc {
        margin: 0 0 12px 0;
        color: #888;
        font-size: 14px;
    }

    .last-triggered {
        margin-top: 12px;
        font-size: 12px;
        color: #666;
    }

    .toggle {
        position: relative;
        width: 44px;
        height: 24px;
    }

    .toggle input {
        opacity: 0;
        width: 0;
        height: 0;
    }

    .slider {
        position: absolute;
        cursor: pointer;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(255, 255, 255, 0.2);
        transition: 0.3s;
        border-radius: 24px;
    }

    .slider:before {
        position: absolute;
        content: "";
        height: 18px;
        width: 18px;
        left: 3px;
        bottom: 3px;
        background-color: white;
        transition: 0.3s;
        border-radius: 50%;
    }

    .toggle input:checked + .slider {
        background-color: #00ff41;
    }

    .toggle input:checked + .slider:before {
        transform: translateX(20px);
    }

    .empty {
        padding: 60px;
        text-align: center;
        color: #00ff41;
        font-size: 18px;
    }
</style>
