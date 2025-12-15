<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import type { DupeCheckResult, OverrideResolution } from '$lib/stores/credit';
  
    export let items: DupeCheckResult[] = [];
    export let visible: boolean = false;
  
    const dispatch = createEventDispatcher<{
      cancel: void;
      submit: { resolutions: OverrideResolution[] };
    }>();
  
    // Track resolution state per item
    interface ItemResolution {
      action: 'cap' | 'override';
      explanation: string;
    }
  
    let resolutions: Map<string, ItemResolution> = new Map();
  
    // Initialize resolutions when items change
    $: if (items.length > 0) {
      resolutions = new Map(
        items.map(item => [
          item.lineItemId,
          {
            // Default: cap if possible, otherwise must override
            action: item.status === 'capped' ? 'cap' : 'override',
            explanation: '',
          },
        ])
      );
    }
  
    // Check if all required explanations are filled
    $: canSubmit = Array.from(resolutions.entries()).every(([lineItemId, res]) => {
      if (res.action === 'cap') return true;
      return res.explanation.trim().length > 0;
    });
  
    function handleCancel() {
      dispatch('cancel');
    }
  
    function handleSubmit() {
      if (!canSubmit) return;
  
      const resolvedItems: OverrideResolution[] = Array.from(resolutions.entries()).map(
        ([lineItemId, res]) => ({
          lineItemId,
          action: res.action,
          explanation: res.action === 'override' ? res.explanation : undefined,
        })
      );
  
      dispatch('submit', { resolutions: resolvedItems });
    }
  
    function setAction(lineItemId: string, action: 'cap' | 'override') {
      const current = resolutions.get(lineItemId);
      if (current) {
        resolutions.set(lineItemId, { ...current, action });
        resolutions = resolutions; // Trigger reactivity
      }
    }
  
    function setExplanation(lineItemId: string, explanation: string) {
      const current = resolutions.get(lineItemId);
      if (current) {
        resolutions.set(lineItemId, { ...current, explanation });
        resolutions = resolutions;
      }
    }
  
    function getResolution(lineItemId: string): ItemResolution {
      return resolutions.get(lineItemId) || { action: 'cap', explanation: '' };
    }
  </script>
  
  {#if visible}
    <div class="modal-backdrop" on:click={handleCancel} role="presentation">
      <div class="modal-container" on:click|stopPropagation role="dialog" aria-modal="true">
        <!-- Header -->
        <div class="modal-header">
          <div class="header-icon">âš </div>
          <div class="header-text">
            <h2 class="header-title">DUPLICATE RETURN DETECTED</h2>
            <p class="header-subtitle">
              {items.length} item{items.length > 1 ? 's have' : ' has'} previous returns on record
            </p>
          </div>
        </div>
  
        <!-- Items List -->
        <div class="items-list">
          {#each items as item (item.lineItemId)}
            {@const resolution = getResolution(item.lineItemId)}
            <div class="dupe-item" class:blocked={item.status === 'blocked'}>
              <!-- Item Header -->
              <div class="item-header">
                <div class="status-badge" class:blocked={item.status === 'blocked'} class:capped={item.status === 'capped'}>
                  {item.status === 'blocked' ? 'ðŸ›‘' : 'âš '}
                </div>
                <div class="item-info">
                  <span class="item-sku">{item.itemNumber}</span>
                  <span class="item-desc">{item.description}</span>
                </div>
              </div>
  
              <!-- Return History -->
              <div class="history-info">
                <div class="history-row">
                  <span class="history-label">Original Invoice Qty</span>
                  <span class="history-value">{item.originalQty}</span>
                </div>
                <div class="history-row">
                  <span class="history-label">Previously Returned</span>
                  <span class="history-value warning">{item.previouslyReturned}</span>
                </div>
                <div class="history-row">
                  <span class="history-label">Remaining</span>
                  <span class="history-value" class:zero={item.availableDelta === 0}>
                    {item.availableDelta}
                  </span>
                </div>
                <div class="history-row highlight">
                  <span class="history-label">You Requested</span>
                  <span class="history-value requested">{item.requestedQty}</span>
                </div>
              </div>
  
              <!-- Status Message -->
              <div class="status-message" class:blocked={item.status === 'blocked'}>
                {item.message}
              </div>
  
              <!-- Resolution Options -->
              <div class="resolution-section">
                {#if item.status === 'capped'}
                  <!-- Capped: Can choose cap or override -->
                  <div class="resolution-options">
                    <label class="resolution-option" class:selected={resolution.action === 'cap'}>
                      <input
                        type="radio"
                        name="resolution-{item.lineItemId}"
                        checked={resolution.action === 'cap'}
                        on:change={() => setAction(item.lineItemId, 'cap')}
                      />
                      <span class="option-radio"></span>
                      <span class="option-text">
                        Cap quantity to <strong>{item.availableDelta}</strong> (no override needed)
                      </span>
                    </label>
  
                    <label class="resolution-option" class:selected={resolution.action === 'override'}>
                      <input
                        type="radio"
                        name="resolution-{item.lineItemId}"
                        checked={resolution.action === 'override'}
                        on:change={() => setAction(item.lineItemId, 'override')}
                      />
                      <span class="option-radio"></span>
                      <span class="option-text">
                        Override and request full <strong>{item.requestedQty}</strong>
                      </span>
                    </label>
                  </div>
                {:else}
                  <!-- Blocked: Must override -->
                  <div class="blocked-notice">
                    <span class="blocked-icon">ðŸ”’</span>
                    <span class="blocked-text">Override explanation required to proceed</span>
                  </div>
                {/if}
  
                <!-- Explanation Field (shown if override selected or blocked) -->
                {#if resolution.action === 'override' || item.status === 'blocked'}
                  <div class="explanation-field" class:required={resolution.explanation.trim().length === 0}>
                    <label class="explanation-label">
                      Override Explanation
                      <span class="required-indicator">*</span>
                    </label>
                    <textarea
                      class="explanation-input"
                      placeholder="Explain why this additional credit is legitimate..."
                      value={resolution.explanation}
                      on:input={(e) => setExplanation(item.lineItemId, e.currentTarget.value)}
                      rows="2"
                    ></textarea>
                    {#if resolution.explanation.trim().length === 0}
                      <span class="field-error">Required for override</span>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
  
        <!-- Warning Footer -->
        <div class="warning-footer">
          <span class="warning-icon">ðŸ“‹</span>
          <span class="warning-text">
            Overrides will be flagged in red for credit team review
          </span>
        </div>
  
        <!-- Actions -->
        <div class="modal-actions">
          <button class="action-btn cancel" on:click={handleCancel}>
            CANCEL
          </button>
          <button
            class="action-btn submit"
            class:disabled={!canSubmit}
            disabled={!canSubmit}
            on:click={handleSubmit}
          >
            {#if items.some(i => getResolution(i.lineItemId).action === 'override' || i.status === 'blocked')}
              SUBMIT WITH OVERRIDES
            {:else}
              SUBMIT WITH CAPS
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}
  
  <style>
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 1000;
      background: rgba(0, 0, 0, 0.85);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      animation: fadeIn 0.2s ease;
    }
  
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
  
    .modal-container {
      background: #0a0a0f;
      border: 2px solid #ff4444;
      border-radius: 8px;
      max-width: 600px;
      width: 100%;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      box-shadow:
        0 0 60px rgba(255, 68, 68, 0.3),
        inset 0 0 40px rgba(255, 68, 68, 0.05);
      animation: scaleIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
  
    @keyframes scaleIn {
      from {
        transform: scale(0.95);
        opacity: 0;
      }
      to {
        transform: scale(1);
        opacity: 1;
      }
    }
  
    /* ========== Header ========== */
  
    .modal-header {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 1.25rem 1.5rem;
      background: linear-gradient(135deg, rgba(255, 68, 68, 0.15) 0%, rgba(255, 68, 68, 0.05) 100%);
      border-bottom: 1px solid rgba(255, 68, 68, 0.3);
    }
  
    .header-icon {
      font-size: 2rem;
      animation: pulse 2s ease infinite;
    }
  
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }
  
    .header-text {
      flex: 1;
    }
  
    .header-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      color: #ff4444;
      margin: 0;
      letter-spacing: 0.1em;
    }
  
    .header-subtitle {
      font-size: 0.8rem;
      color: #888;
      margin: 0.25rem 0 0;
    }
  
    /* ========== Items List ========== */
  
    .items-list {
      flex: 1;
      overflow-y: auto;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
  
    .dupe-item {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid rgba(255, 170, 0, 0.3);
      border-radius: 6px;
      padding: 1rem;
    }
  
    .dupe-item.blocked {
      border-color: rgba(255, 68, 68, 0.5);
      background: rgba(255, 68, 68, 0.05);
    }
  
    .item-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.75rem;
    }
  
    .status-badge {
      width: 2rem;
      height: 2rem;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 4px;
      font-size: 1rem;
    }
  
    .status-badge.blocked {
      background: rgba(255, 68, 68, 0.2);
    }
  
    .status-badge.capped {
      background: rgba(255, 170, 0, 0.2);
    }
  
    .item-info {
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }
  
    .item-sku {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: #00ffff;
    }
  
    .item-desc {
      font-size: 0.8rem;
      color: #e0e0e0;
    }
  
    /* ========== History Info ========== */
  
    .history-info {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.5rem;
      padding: 0.75rem;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 4px;
      margin-bottom: 0.75rem;
    }
  
    .history-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  
    .history-row.highlight {
      grid-column: span 2;
      padding-top: 0.5rem;
      border-top: 1px dashed rgba(255, 255, 255, 0.1);
    }
  
    .history-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem;
      color: #666;
      letter-spacing: 0.05em;
    }
  
    .history-value {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #e0e0e0;
    }
  
    .history-value.warning {
      color: #ffaa00;
    }
  
    .history-value.zero {
      color: #ff4444;
    }
  
    .history-value.requested {
      color: #00ffff;
      font-size: 0.9rem;
    }
  
    /* ========== Status Message ========== */
  
    .status-message {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #ffaa00;
      padding: 0.5rem 0.75rem;
      background: rgba(255, 170, 0, 0.1);
      border-radius: 3px;
      margin-bottom: 0.75rem;
    }
  
    .status-message.blocked {
      color: #ff4444;
      background: rgba(255, 68, 68, 0.1);
    }
  
    /* ========== Resolution Options ========== */
  
    .resolution-section {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
  
    .resolution-options {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
  
    .resolution-option {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.75rem;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
  
    .resolution-option:hover {
      border-color: rgba(0, 255, 65, 0.3);
    }
  
    .resolution-option.selected {
      border-color: #00ff41;
      background: rgba(0, 255, 65, 0.05);
    }
  
    .resolution-option input {
      display: none;
    }
  
    .option-radio {
      width: 1rem;
      height: 1rem;
      border: 2px solid #555;
      border-radius: 50%;
      position: relative;
      flex-shrink: 0;
    }
  
    .resolution-option.selected .option-radio {
      border-color: #00ff41;
    }
  
    .resolution-option.selected .option-radio::after {
      content: '';
      position: absolute;
      inset: 3px;
      background: #00ff41;
      border-radius: 50%;
      box-shadow: 0 0 8px #00ff41;
    }
  
    .option-text {
      font-size: 0.8rem;
      color: #ccc;
    }
  
    .option-text strong {
      color: #00ffff;
    }
  
    .blocked-notice {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem;
      background: rgba(255, 68, 68, 0.1);
      border-radius: 4px;
    }
  
    .blocked-icon {
      font-size: 0.9rem;
    }
  
    .blocked-text {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: #ff4444;
    }
  
    /* ========== Explanation Field ========== */
  
    .explanation-field {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }
  
    .explanation-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem;
      color: #888;
      letter-spacing: 0.05em;
    }
  
    .required-indicator {
      color: #ff4444;
    }
  
    .explanation-input {
      width: 100%;
      padding: 0.6rem 0.75rem;
      background: rgba(0, 0, 0, 0.5);
      border: 1px solid rgba(255, 68, 68, 0.3);
      border-radius: 4px;
      color: #e0e0e0;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      resize: vertical;
      outline: none;
      transition: all 0.2s ease;
    }
  
    .explanation-input:focus {
      border-color: #ff4444;
      box-shadow: 0 0 15px rgba(255, 68, 68, 0.2);
    }
  
    .explanation-input::placeholder {
      color: #555;
    }
  
    .field-error {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem;
      color: #ff4444;
    }
  
    /* ========== Warning Footer ========== */
  
    .warning-footer {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      padding: 0.75rem;
      background: rgba(255, 170, 0, 0.1);
      border-top: 1px solid rgba(255, 170, 0, 0.2);
    }
  
    .warning-icon {
      font-size: 1rem;
    }
  
    .warning-text {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: #ffaa00;
    }
  
    /* ========== Actions ========== */
  
    .modal-actions {
      display: flex;
      gap: 1rem;
      padding: 1rem 1.5rem;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
  
    .action-btn {
      flex: 1;
      padding: 0.875rem 1.5rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      letter-spacing: 0.1em;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
  
    .action-btn.cancel {
      background: transparent;
      border: 1px solid #555;
      color: #888;
    }
  
    .action-btn.cancel:hover {
      border-color: #888;
      color: #ccc;
    }
  
    .action-btn.submit {
      background: rgba(255, 68, 68, 0.2);
      border: 2px solid #ff4444;
      color: #ff4444;
    }
  
    .action-btn.submit:hover:not(:disabled) {
      background: rgba(255, 68, 68, 0.3);
      box-shadow: 0 0 20px rgba(255, 68, 68, 0.3);
    }
  
    .action-btn.submit.disabled,
    .action-btn.submit:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      border-color: #666;
      color: #666;
      background: transparent;
    }
  
    /* ========== Scrollbar ========== */
  
    .items-list::-webkit-scrollbar {
      width: 6px;
    }
  
    .items-list::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.3);
      border-radius: 3px;
    }
  
    .items-list::-webkit-scrollbar-thumb {
      background: rgba(255, 68, 68, 0.3);
      border-radius: 3px;
    }
  
    .items-list::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 68, 68, 0.5);
    }
  </style>