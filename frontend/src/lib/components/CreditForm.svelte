<script lang="ts">
    import DupeOverrideModal from '$lib/components/DupeOverrideModal.svelte';
    import type { Customer, Invoice, LineItem, LineItemCredit, OverrideResolution } from '$lib/stores/credit';
    import {
        canSubmit,
        credit,
        filteredInvoices,
        itemsWithOverride,
        REASON_CODES,
        selectedItemCount,
        totalCreditAmount,
        UOM_OPTIONS
    } from '$lib/stores/credit';
    import { createEventDispatcher } from 'svelte';
  
    const dispatch = createEventDispatcher<{
      close: void;
      complete: { requestId: string };
    }>();

    // Standalone mode - renders inline without fixed overlay
    export let standalone: boolean = false;
  
    // ========== Customer/Invoice Selection State ==========
    let customerInputFocused = false;
    let invoiceDropdownOpen = false;
    let searchTimeout: ReturnType<typeof setTimeout>;
  
    // ========== Expanded Search Modal State ==========
    let customerSearchExpanded = false;
    let invoiceSearchExpanded = false;
  
    // ========== Line Item Expansion State ==========
    let expandedNotes: Set<string> = new Set();
    let expandedAttachments: Set<string> = new Set();
  
    // Track which items have partial credit (notes required)
    let itemNotes: Map<string, string> = new Map();
  
    // ========== Customer Search ==========
    function handleCustomerInput(e: Event) {
      const value = (e.target as HTMLInputElement).value;
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        credit.searchCustomers(value);
      }, 150);
    }
  
    function openCustomerSearch() {
      customerSearchExpanded = true;
      customerInputFocused = true;
    }
  
    function selectCustomer(customer: Customer) {
      credit.selectCustomer(customer);
      customerInputFocused = false;
      customerSearchExpanded = false;
    }
  
    function closeCustomerSearch() {
      customerSearchExpanded = false;
      customerInputFocused = false;
    }
  
    // ========== Invoice Selection ==========
    function openInvoiceSearch() {
      if ($credit.selectedCustomer) {
        invoiceSearchExpanded = true;
        invoiceDropdownOpen = true;
      }
    }
  
    function selectInvoice(invoice: Invoice) {
      credit.selectInvoice(invoice);
      invoiceDropdownOpen = false;
      invoiceSearchExpanded = false;
    }
  
    function closeInvoiceSearch() {
      invoiceSearchExpanded = false;
      invoiceDropdownOpen = false;
    }
  
    function handleInvoiceSearch(e: Event) {
      const value = (e.target as HTMLInputElement).value;
      credit.searchInvoices(value);
    }
  
    // ========== Line Item Handlers ==========
    function handleToggle(item: LineItem) {
      credit.toggleLineItem(item.lineItemId);
    }
  
    function handleFieldChange(
      lineItemId: string,
      field: keyof LineItemCredit,
      value: string | number | boolean
    ) {
      credit.updateLineItemCredit(lineItemId, { [field]: value });
    }
  
    function handleQuantityChange(item: LineItem, e: Event) {
      const value = parseInt((e.target as HTMLInputElement).value) || 0;
      const clamped = Math.min(Math.max(0, value), item.quantity);
      credit.updateLineItemCredit(item.lineItemId, { creditQuantity: clamped });
    }
  
    function handleAmountChange(item: LineItem, e: Event) {
      const value = parseFloat((e.target as HTMLInputElement).value) || 0;
      const maxAmount = item.unitPrice * item.credit.creditQuantity;
      const clamped = Math.min(Math.max(0, value), maxAmount);
      credit.updateLineItemCredit(item.lineItemId, { creditAmount: clamped });
    }
  
    // ========== Notes/Attachments Toggle ==========
    function toggleNotes(lineItemId: string) {
      if (expandedNotes.has(lineItemId)) {
        expandedNotes.delete(lineItemId);
      } else {
        expandedNotes.add(lineItemId);
      }
      expandedNotes = expandedNotes; // trigger reactivity
    }
  
    function toggleAttachments(lineItemId: string) {
      if (expandedAttachments.has(lineItemId)) {
        expandedAttachments.delete(lineItemId);
      } else {
        expandedAttachments.add(lineItemId);
      }
      expandedAttachments = expandedAttachments;
    }
  
    // Handle partial credit toggle - auto expand notes
    function handlePartialToggle(lineItemId: string, currentValue: boolean) {
      const newValue = !currentValue;
      handleFieldChange(lineItemId, 'isPartialCredit', newValue);
  
      // Auto-expand notes when partial credit is enabled
      if (newValue) {
        expandedNotes.add(lineItemId);
        expandedNotes = expandedNotes;
      }
    }
  
    // Update item notes
    function handleItemNotes(lineItemId: string, value: string) {
      itemNotes.set(lineItemId, value);
      itemNotes = itemNotes;
    }
  
    // Check if item notes are valid (required if partial credit)
    function isItemNotesValid(item: LineItem): boolean {
      if (!item.credit.isPartialCredit) return true;
      const notes = itemNotes.get(item.lineItemId) || '';
      return notes.trim().length > 0;
    }
  
    // ========== File Handling ==========
    function handleFileInput(lineItemId: string, e: Event) {
      const input = e.target as HTMLInputElement;
      if (!input.files) return;
      // For now, add to global attachments - could be per-item later
      Array.from(input.files).forEach(file => {
        credit.addAttachment(file);
      });
      input.value = '';
    }
  
    // ========== Submit Flow ==========
    function handleSubmitClick() {
      if (!$canSubmit) return;
      const canProceed = credit.initiateSubmit();
      if (canProceed) {
        performSubmit();
      }
    }
  
    function handleOverrideCancel() {
      credit.closeOverrideModal();
    }
  
    function handleOverrideSubmit(e: CustomEvent<{ resolutions: OverrideResolution[] }>) {
      credit.applyOverrideResolutions(e.detail.resolutions);
      performSubmit();
    }
  
    async function performSubmit() {
      // Integrate item notes into line item credits before submission
      itemNotes.forEach((notes, lineItemId) => {
        if (notes.trim()) {
          credit.updateLineItemCredit(lineItemId, { partialExplanation: notes });
        }
      });
  
      const requestId = await credit.submitCreditRequest();
      if (requestId) {
        dispatch('complete', { requestId });
      }
    }
  
    // ========== Utilities ==========
    function getItemWarningLevel(item: LineItem): 'none' | 'capped' | 'blocked' {
      if (item.credit.wasCapped) return 'capped';
      if (item.credit.requiresOverride) return 'blocked';
      return 'none';
    }
  
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest('.customer-field') && !target.closest('.search-modal')) {
        customerInputFocused = false;
        customerSearchExpanded = false;
      }
      if (!target.closest('.invoice-field') && !target.closest('.search-modal')) {
        invoiceDropdownOpen = false;
        invoiceSearchExpanded = false;
      }
    }
  
    function handleClose() {
      // Could add dirty check here
      dispatch('close');
    }
  </script>
  
  <svelte:window on:click={handleClickOutside} />
  
  <div class="credit-form-overlay" class:standalone>
    <div class="credit-form-panel">
      <!-- Header -->
      <header class="panel-header">
        <h1 class="panel-title">CREDIT REQUEST</h1>
        <button class="close-btn" on:click={handleClose} aria-label="Close">
          <span class="close-icon">Ã—</span>
        </button>
      </header>
  
      <!-- Scrollable Content -->
      <div class="panel-content">
        <!-- Customer Selection -->
        <div class="form-field customer-field">
          <label class="field-label">CUSTOMER</label>
          <button
            class="search-trigger"
            class:has-value={$credit.selectedCustomer}
            on:click={openCustomerSearch}
          >
            {#if $credit.selectedCustomer}
              <span class="trigger-value">{$credit.selectedCustomer.customerName}</span>
              <span class="trigger-code">#{$credit.selectedCustomer.customerNumber}</span>
            {:else}
              <span class="trigger-placeholder">Search customer...</span>
            {/if}
            <span class="trigger-icon">â–¾</span>
          </button>
        </div>
  
        <!-- Customer Search Modal (expanded) -->
        {#if customerSearchExpanded}
          <div class="search-modal-backdrop" on:click={closeCustomerSearch}></div>
          <div class="search-modal">
            <div class="search-modal-header">
              <span class="search-modal-title">SELECT CUSTOMER</span>
              <button class="search-modal-close" on:click={closeCustomerSearch}>Ã—</button>
            </div>
            <div class="search-modal-input-wrap">
              <input
                type="text"
                class="search-modal-input"
                placeholder="Type to search..."
                value={$credit.customerSearch}
                on:input={handleCustomerInput}
                autofocus
              />
              {#if $credit.loadingCustomers}
                <span class="input-spinner"></span>
              {/if}
            </div>
            <div class="search-modal-results">
              {#if $credit.customerResults.length > 0}
                {#each $credit.customerResults as customer (customer.customerId)}
                  <button class="search-modal-item" on:click={() => selectCustomer(customer)}>
                    <span class="item-name">{customer.customerName}</span>
                    <span class="item-code">#{customer.customerNumber}</span>
                  </button>
                {/each}
              {:else if $credit.customerSearch.length >= 2 && !$credit.loadingCustomers}
                <div class="search-modal-empty">No customers found</div>
              {:else}
                <div class="search-modal-empty">Start typing to search...</div>
              {/if}
            </div>
          </div>
        {/if}
  
        <!-- Invoice Selection -->
        <div class="form-field invoice-field">
          <label class="field-label">INVOICE</label>
          <button
            class="search-trigger"
            class:has-value={$credit.selectedInvoice}
            class:disabled={!$credit.selectedCustomer}
            on:click={openInvoiceSearch}
            disabled={!$credit.selectedCustomer}
          >
            {#if $credit.selectedInvoice}
              <span class="trigger-value">{$credit.selectedInvoice.invoiceNumber}</span>
              <span class="trigger-amount">${$credit.selectedInvoice.totalAmount.toFixed(2)}</span>
            {:else if $credit.selectedCustomer}
              <span class="trigger-placeholder">Select invoice...</span>
            {:else}
              <span class="trigger-placeholder disabled">Select customer first</span>
            {/if}
            <span class="trigger-icon">â–¾</span>
          </button>
  
          {#if $credit.selectedInvoice}
            <div class="invoice-summary">
              <span class="invoice-total">${$credit.selectedInvoice.totalAmount.toFixed(2)}</span>
              <span class="invoice-label">(approx)</span>
            </div>
          {/if}
        </div>
  
        <!-- Invoice Search Modal (expanded) -->
        {#if invoiceSearchExpanded}
          <div class="search-modal-backdrop" on:click={closeInvoiceSearch}></div>
          <div class="search-modal">
            <div class="search-modal-header">
              <span class="search-modal-title">SELECT INVOICE</span>
              <button class="search-modal-close" on:click={closeInvoiceSearch}>Ã—</button>
            </div>
            <div class="search-modal-input-wrap">
              <input
                type="text"
                class="search-modal-input"
                placeholder="Search invoice..."
                value={$credit.invoiceSearch}
                on:input={handleInvoiceSearch}
                autofocus
              />
            </div>
            <div class="search-modal-results">
              {#if $filteredInvoices.length > 0}
                {#each $filteredInvoices as invoice (invoice.invoiceId)}
                  <button class="search-modal-item invoice-item" on:click={() => selectInvoice(invoice)}>
                    <div class="invoice-row">
                      <span class="invoice-number">{invoice.invoiceNumber}</span>
                      <span class="invoice-amount">${invoice.totalAmount.toFixed(2)}</span>
                    </div>
                    <div class="invoice-meta">
                      <span class="invoice-date">{invoice.invoiceDate}</span>
                      {#if invoice.poNumber}
                        <span class="invoice-po">PO: {invoice.poNumber}</span>
                      {/if}
                    </div>
                  </button>
                {/each}
              {:else}
                <div class="search-modal-empty">No invoices found</div>
              {/if}
            </div>
          </div>
        {/if}
  
        <!-- Line Items Section -->
        {#if $credit.selectedInvoice}
          <div class="line-items-section">
            <div class="section-header">
              <span class="section-title">LINE ITEMS</span>
              <span class="section-count">{$selectedItemCount} selected</span>
            </div>
  
            {#if $credit.loadingLineItems}
              <div class="loading-state">
                <div class="loading-pulse"></div>
                <span>Loading items...</span>
              </div>
            {:else}
              <div class="items-list">
                {#each $credit.lineItems as item (item.lineItemId)}
                  {@const warningLevel = getItemWarningLevel(item)}
                  <div
                    class="item-card"
                    class:selected={item.credit.selected}
                    class:has-errors={item.credit.selected && !item.credit.isValid}
                    class:was-capped={warningLevel === 'capped'}
                    class:has-override={warningLevel === 'blocked'}
                  >
                    <!-- Item Header (clickable) -->
                    <button class="item-header" on:click={() => handleToggle(item)}>
                      <div class="item-checkbox" class:checked={item.credit.selected}>
                        {#if item.credit.selected}
                          <span class="check-mark">âœ“</span>
                        {/if}
                      </div>
  
                      <div class="item-info">
                        <div class="item-top-row">
                          <span class="item-sku">{item.itemNumber}</span>
                          {#if warningLevel === 'capped'}
                            <span class="item-badge capped">CAPPED</span>
                          {:else if warningLevel === 'blocked'}
                            <span class="item-badge override">OVERRIDE</span>
                          {/if}
                        </div>
                        <span class="item-desc">{item.description}</span>
                      </div>
  
                      <div class="item-amounts">
                        <span class="item-qty">{item.quantity} {item.uom}</span>
                        <span class="item-price">${item.extendedPrice.toFixed(2)}</span>
                      </div>
                    </button>
  
                    <!-- Expanded Fields -->
                    {#if item.credit.selected}
                      <div class="item-fields">
                        <!-- Warning Notices -->
                        {#if item.credit.requiresOverride}
                          <div class="notice override-notice">
                            <span class="notice-icon">âš </span>
                            <span>Override required - will be flagged for review</span>
                          </div>
                        {/if}
  
                        {#if item.credit.wasCapped}
                          <div class="notice capped-notice">
                            <span class="notice-icon">â†“</span>
                            <span>Qty capped from {item.credit.originalRequestedQty} to {item.credit.creditQuantity}</span>
                          </div>
                        {/if}
  
                        <!-- Fields Row -->
                        <div class="fields-row">
                          <div class="field">
                            <label class="mini-label">REASON</label>
                            <select
                              class="cyber-select"
                              value={item.credit.creditReason}
                              on:change={(e) => handleFieldChange(item.lineItemId, 'creditReason', e.currentTarget.value)}
                            >
                              <option value="">Select...</option>
                              {#each REASON_CODES as reason}
                                <option value={reason.code}>{reason.label}</option>
                              {/each}
                            </select>
                          </div>
  
                          <div class="field compact">
                            <label class="mini-label">QTY</label>
                            <input
                              type="number"
                              class="cyber-input"
                              value={item.credit.creditQuantity}
                              min="1"
                              max={item.quantity}
                              on:change={(e) => handleQuantityChange(item, e)}
                            />
                          </div>
  
                          <div class="field compact">
                            <label class="mini-label">UOM</label>
                            <select
                              class="cyber-select"
                              value={item.credit.creditUOM}
                              on:change={(e) => handleFieldChange(item.lineItemId, 'creditUOM', e.currentTarget.value)}
                            >
                              {#each UOM_OPTIONS as uom}
                                <option value={uom.value}>{uom.label}</option>
                              {/each}
                            </select>
                          </div>
  
                          <div class="field compact">
                            <label class="mini-label">CREDIT $</label>
                            <input
                              type="number"
                              class="cyber-input"
                              value={item.credit.creditAmount.toFixed(2)}
                              min="0"
                              step="0.01"
                              on:change={(e) => handleAmountChange(item, e)}
                            />
                          </div>
                        </div>
  
                        <!-- Actions Row -->
                        <div class="actions-row">
                          <button
                            class="action-toggle"
                            class:active={item.credit.isPartialCredit}
                            on:click={() => handlePartialToggle(item.lineItemId, item.credit.isPartialCredit)}
                          >
                            <span class="toggle-dot" class:on={item.credit.isPartialCredit}></span>
                            <span>PARTIAL</span>
                          </button>
  
                          <div class="action-icons">
                            <button
                              class="icon-btn"
                              class:active={expandedAttachments.has(item.lineItemId)}
                              on:click={() => toggleAttachments(item.lineItemId)}
                              title="Attachments"
                            >
                              ðŸ“Ž
                            </button>
                            <button
                              class="icon-btn"
                              class:active={expandedNotes.has(item.lineItemId)}
                              class:required={item.credit.isPartialCredit}
                              class:invalid={item.credit.isPartialCredit && !isItemNotesValid(item)}
                              on:click={() => toggleNotes(item.lineItemId)}
                              title={item.credit.isPartialCredit ? "Notes (REQUIRED for partial)" : "Notes"}
                            >
                              ðŸ’¬
                              {#if item.credit.isPartialCredit}
                                <span class="required-badge">!</span>
                              {/if}
                            </button>
                          </div>
                        </div>
  
                        <!-- Notes Section (always visible if partial credit, otherwise toggleable) -->
                        {#if expandedNotes.has(item.lineItemId) || item.credit.isPartialCredit}
                          <div class="notes-field" class:required={item.credit.isPartialCredit}>
                            {#if item.credit.isPartialCredit}
                              <label class="notes-label required">NOTES (REQUIRED FOR PARTIAL CREDIT)</label>
                            {/if}
                            <textarea
                              class="cyber-textarea"
                              class:invalid={item.credit.isPartialCredit && !isItemNotesValid(item)}
                              placeholder={item.credit.isPartialCredit ? "Explain partial credit reason... (required)" : "Additional notes..."}
                              value={itemNotes.get(item.lineItemId) || ''}
                              on:input={(e) => handleItemNotes(item.lineItemId, e.currentTarget.value)}
                              rows="2"
                            ></textarea>
                            {#if item.credit.isPartialCredit && !isItemNotesValid(item)}
                              <span class="notes-error">Notes required for partial credit</span>
                            {/if}
                          </div>
                        {/if}
  
                        <!-- Attachments Expansion -->
                        {#if expandedAttachments.has(item.lineItemId)}
                          <div class="attachment-zone">
                            <label class="attachment-label">
                              <input
                                type="file"
                                multiple
                                on:change={(e) => handleFileInput(item.lineItemId, e)}
                                class="file-input"
                              />
                              <span class="attachment-text">Click or drop files</span>
                            </label>
                          </div>
                        {/if}
  
                        <!-- Validation Errors -->
                        {#if item.credit.validationErrors.length > 0}
                          <div class="validation-errors">
                            {#each item.credit.validationErrors as error}
                              <span class="error-tag">âš  {error}</span>
                            {/each}
                          </div>
                        {/if}
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>
  
      <!-- Footer -->
      <footer class="panel-footer">
        {#if $credit.error}
          <div class="error-banner">
            <span>âš  {$credit.error}</span>
            <button class="error-dismiss" on:click={() => credit.clearError()}>Ã—</button>
          </div>
        {/if}
  
        <div class="submit-row">
          <div class="submit-summary">
            <span class="summary-item">{$selectedItemCount} items</span>
            <span class="summary-total">${$totalCreditAmount.toFixed(2)}</span>
          </div>
  
          <button
            class="submit-btn"
            class:ready={$canSubmit}
            class:has-overrides={$itemsWithOverride.length > 0}
            disabled={!$canSubmit || $credit.submitting}
            on:click={handleSubmitClick}
          >
            {#if $credit.submitting}
              <span class="btn-spinner"></span>
              SUBMITTING...
            {:else if $itemsWithOverride.length > 0}
              SUBMIT WITH OVERRIDES
            {:else}
              SUBMIT REQUEST
            {/if}
          </button>
        </div>
      </footer>
    </div>
  
    <!-- Override Modal -->
    {#if $credit.showOverrideModal}
      <DupeOverrideModal
        items={$credit.pendingOverrides}
        on:cancel={handleOverrideCancel}
        on:submit={handleOverrideSubmit}
      />
    {/if}
  </div>
  
  <style>
    /* ========== Layout ========== */
    .credit-form-overlay {
      position: fixed;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.8);
      z-index: 1000;
      padding: 1rem;
    }

    /* Standalone mode - flows with page layout */
    .credit-form-overlay.standalone {
      position: relative;
      inset: auto;
      background: transparent;
      padding: 0;
      z-index: auto;
    }

    .credit-form-overlay.standalone .credit-form-panel {
      max-height: none;
      max-width: 100%;
    }
  
    .credit-form-panel {
      display: flex;
      flex-direction: column;
      width: 100%;
      max-width: 600px;
      max-height: 90vh;
      background: #1a1a1a;
      border: 1px solid rgba(0, 255, 65, 0.4);
      border-radius: 8px;
      box-shadow:
        0 0 30px rgba(0, 255, 65, 0.15),
        0 0 60px rgba(0, 255, 65, 0.05),
        0 25px 50px rgba(0, 0, 0, 0.5);
      overflow: hidden;
    }
  
    /* ========== Header ========== */
    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 1.25rem;
      border-bottom: 1px solid rgba(0, 255, 65, 0.2);
      background: rgba(0, 0, 0, 0.3);
    }
  
    .panel-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      font-weight: 700;
      letter-spacing: 0.15em;
      color: #00ff41;
      text-shadow: 0 0 20px rgba(0, 255, 65, 0.5);
      margin: 0;
    }
  
    .close-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 2rem;
      height: 2rem;
      background: transparent;
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 4px;
      color: #888;
      font-size: 1.25rem;
      cursor: pointer;
      transition: all 0.2s;
    }
  
    .close-btn:hover {
      border-color: #ff4444;
      color: #ff4444;
      box-shadow: 0 0 15px rgba(255, 68, 68, 0.3);
    }
  
    /* ========== Content Area ========== */
    .panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }
  
    /* ========== Form Fields ========== */
    .form-field {
      position: relative;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
  
    .field-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      color: #00ff41;
    }
  
    /* ========== Search Trigger Button ========== */
    .search-trigger {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      padding: 0.875rem 1rem;
      background: #000000;
      border: 1px solid rgba(0, 255, 65, 0.4);
      border-radius: 6px;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      cursor: pointer;
      transition: all 0.2s;
      text-align: left;
    }
  
    .search-trigger:hover:not(.disabled) {
      border-color: #00ff41;
      box-shadow: 0 0 15px rgba(0, 255, 65, 0.3);
    }
  
    .search-trigger.has-value {
      border-color: #00ff41;
    }
  
    .search-trigger.disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  
    .trigger-value {
      flex: 1;
      color: #ffffff;
    }
  
    .trigger-code,
    .trigger-amount {
      color: #00ff41;
      font-size: 0.85rem;
      margin-left: 0.5rem;
    }
  
    .trigger-placeholder {
      color: #555;
    }
  
    .trigger-placeholder.disabled {
      color: #333;
    }
  
    .trigger-icon {
      color: #00ff41;
      margin-left: 0.5rem;
    }
  
    /* ========== Search Modal (Expanded) ========== */
    .search-modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.7);
      z-index: 2000;
    }
  
    .search-modal {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 90%;
      max-width: 500px;
      max-height: 70vh;
      background: #1a1a1a;
      border: 2px solid #00ff41;
      border-radius: 12px;
      box-shadow:
        0 0 40px rgba(0, 255, 65, 0.3),
        0 0 80px rgba(0, 255, 65, 0.1),
        0 25px 50px rgba(0, 0, 0, 0.5);
      z-index: 2001;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      animation: modalPop 0.2s ease;
    }
  
    @keyframes modalPop {
      from {
        opacity: 0;
        transform: translate(-50%, -50%) scale(0.95);
      }
      to {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1);
      }
    }
  
    .search-modal-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 1.25rem;
      border-bottom: 1px solid rgba(0, 255, 65, 0.3);
      background: rgba(0, 0, 0, 0.3);
    }
  
    .search-modal-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      color: #00ff41;
    }
  
    .search-modal-close {
      background: none;
      border: none;
      color: #888;
      font-size: 1.5rem;
      cursor: pointer;
      padding: 0;
      line-height: 1;
      transition: color 0.2s;
    }
  
    .search-modal-close:hover {
      color: #ff4444;
    }
  
    .search-modal-input-wrap {
      display: flex;
      align-items: center;
      padding: 1rem 1.25rem;
      border-bottom: 1px solid rgba(0, 255, 65, 0.2);
    }
  
    .search-modal-input {
      flex: 1;
      background: #000000;
      border: 2px solid #00ff41;
      border-radius: 6px;
      padding: 1rem 1.25rem;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.1rem;
      outline: none;
      box-shadow: 0 0 20px rgba(0, 255, 65, 0.2);
    }
  
    .search-modal-input::placeholder {
      color: #555;
    }
  
    .search-modal-results {
      flex: 1;
      overflow-y: auto;
      max-height: 350px;
    }
  
    /* Fat scrollbar for touchpad users */
    .search-modal-results::-webkit-scrollbar {
      width: 16px;
    }
  
    .search-modal-results::-webkit-scrollbar-track {
      background: #0a0a0a;
      border-radius: 8px;
    }
  
    .search-modal-results::-webkit-scrollbar-thumb {
      background: #00ff41;
      border-radius: 8px;
      border: 4px solid #0a0a0a;
    }
  
    .search-modal-results::-webkit-scrollbar-thumb:hover {
      background: #00ff65;
    }
  
    .search-modal-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      padding: 1rem 1.25rem;
      background: transparent;
      border: none;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      cursor: pointer;
      text-align: left;
      transition: background 0.15s;
    }
  
    .search-modal-item:last-child {
      border-bottom: none;
    }
  
    .search-modal-item:hover {
      background: rgba(0, 255, 65, 0.15);
    }
  
    .search-modal-item.invoice-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.25rem;
    }
  
    .search-modal-empty {
      padding: 2rem;
      text-align: center;
      color: #555;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.9rem;
    }
  
    /* ========== Input Fields ========== */
    .cyber-input {
      flex: 1;
      background: transparent;
      border: none;
      padding: 0.875rem 1rem;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      outline: none;
    }
  
    .cyber-input::placeholder {
      color: #555;
    }
  
    .cyber-input:disabled {
      cursor: not-allowed;
    }
  
    .input-spinner {
      width: 1rem;
      height: 1rem;
      border: 2px solid rgba(0, 255, 65, 0.3);
      border-top-color: #00ff41;
      border-radius: 50%;
      margin-right: 0.75rem;
      animation: spin 1s linear infinite;
    }
  
    /* ========== Invoice Display ========== */
    .invoice-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.25rem;
    }
  
    .invoice-row {
      display: flex;
      justify-content: space-between;
      width: 100%;
    }
  
    .invoice-number {
      color: #ffffff;
      font-weight: 600;
    }
  
    .invoice-amount {
      color: #00ff41;
    }
  
    .invoice-meta {
      display: flex;
      gap: 1rem;
      font-size: 0.75rem;
      color: #666;
    }
  
    .invoice-summary {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      margin-top: 0.25rem;
    }
  
    .invoice-total {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.25rem;
      font-weight: 700;
      color: #00ff41;
      text-shadow: 0 0 15px rgba(0, 255, 65, 0.4);
    }
  
    .invoice-label {
      font-size: 0.75rem;
      color: #555;
    }
  
    /* ========== Line Items Section ========== */
    .line-items-section {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
  
    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid rgba(0, 255, 65, 0.2);
    }
  
    .section-title {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      color: #00ff41;
    }
  
    .section-count {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #888;
    }
  
    .items-list {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
  
    /* ========== Item Card ========== */
    .item-card {
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 6px;
      transition: all 0.2s;
      overflow: hidden;
    }
  
    .item-card:hover {
      border-color: rgba(0, 255, 65, 0.3);
    }
  
    .item-card.selected {
      border-color: #00ff41;
      background: rgba(0, 255, 65, 0.03);
      box-shadow:
        0 0 20px rgba(0, 255, 65, 0.15),
        0 0 40px rgba(0, 255, 65, 0.05);
    }
  
    .item-card.has-errors {
      border-color: #ff4444;
      box-shadow: 0 0 15px rgba(255, 68, 68, 0.2);
    }
  
    .item-card.was-capped {
      border-color: #ffaa00;
    }
  
    .item-card.has-override {
      border-color: #ff4444;
    }
  
    .item-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      width: 100%;
      padding: 0.875rem;
      background: transparent;
      border: none;
      color: inherit;
      cursor: pointer;
      text-align: left;
      transition: background 0.15s;
    }
  
    .item-header:hover {
      background: rgba(0, 255, 65, 0.05);
    }
  
    .item-checkbox {
      width: 1.5rem;
      height: 1.5rem;
      border: 2px solid rgba(0, 255, 65, 0.4);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: all 0.2s;
    }
  
    .item-checkbox.checked {
      background: rgba(0, 255, 65, 0.2);
      border-color: #00ff41;
      box-shadow: 0 0 10px rgba(0, 255, 65, 0.4);
    }
  
    .check-mark {
      color: #00ff41;
      font-size: 0.9rem;
      text-shadow: 0 0 5px #00ff41;
    }
  
    .item-info {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      min-width: 0;
    }
  
    .item-top-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
  
    .item-sku {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: #00ff41;
    }
  
    .item-badge {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem;
      padding: 0.15rem 0.4rem;
      border-radius: 3px;
      letter-spacing: 0.05em;
    }
  
    .item-badge.capped {
      background: rgba(255, 170, 0, 0.2);
      color: #ffaa00;
      border: 1px solid rgba(255, 170, 0, 0.4);
    }
  
    .item-badge.override {
      background: rgba(255, 68, 68, 0.2);
      color: #ff4444;
      border: 1px solid rgba(255, 68, 68, 0.4);
    }
  
    .item-desc {
      font-size: 0.85rem;
      color: #cccccc;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  
    .item-amounts {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.1rem;
      flex-shrink: 0;
    }
  
    .item-qty {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #888;
    }
  
    .item-price {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.95rem;
      font-weight: 600;
      color: #ffffff;
    }
  
    /* ========== Item Fields (Expanded) ========== */
    .item-fields {
      padding: 0.875rem;
      padding-top: 0;
      border-top: 1px solid rgba(0, 255, 65, 0.15);
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      animation: slideDown 0.2s ease;
    }
  
    @keyframes slideDown {
      from { opacity: 0; transform: translateY(-8px); }
      to { opacity: 1; transform: translateY(0); }
    }
  
    .notice {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem;
      border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
    }
  
    .override-notice {
      background: rgba(255, 68, 68, 0.1);
      border: 1px solid rgba(255, 68, 68, 0.3);
      color: #ff4444;
    }
  
    .capped-notice {
      background: rgba(255, 170, 0, 0.1);
      border: 1px solid rgba(255, 170, 0, 0.3);
      color: #ffaa00;
    }
  
    .fields-row {
      display: grid;
      grid-template-columns: 1.5fr 0.7fr 0.7fr 1fr;
      gap: 0.75rem;
    }
  
    .field {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
  
    .mini-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem;
      letter-spacing: 0.1em;
      color: rgba(0, 255, 65, 0.6);
    }
  
    .cyber-select {
      width: 100%;
      padding: 0.5rem 0.75rem;
      background: #000000;
      border: 1px solid rgba(0, 255, 65, 0.4);
      border-radius: 4px;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      cursor: pointer;
      outline: none;
      transition: all 0.2s;
    }
  
    .cyber-select:focus {
      border-color: #00ff41;
      box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }
  
    .item-fields .cyber-input {
      padding: 0.5rem 0.75rem;
      font-size: 0.85rem;
      background: #000000;
      border: 1px solid rgba(0, 255, 65, 0.4);
      border-radius: 4px;
    }
  
    .item-fields .cyber-input:focus {
      border-color: #00ff41;
      box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }
  
    /* ========== Actions Row ========== */
    .actions-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
  
    .action-toggle {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      background: none;
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 4px;
      padding: 0.4rem 0.75rem;
      color: #888;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      letter-spacing: 0.05em;
      cursor: pointer;
      transition: all 0.2s;
    }
  
    .action-toggle:hover {
      border-color: rgba(0, 255, 65, 0.4);
      color: #aaa;
    }
  
    .action-toggle.active {
      border-color: #00ff41;
      color: #00ff41;
    }
  
    .toggle-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #444;
      transition: all 0.2s;
    }
  
    .toggle-dot.on {
      background: #00ff41;
      box-shadow: 0 0 8px #00ff41;
    }
  
    .action-icons {
      display: flex;
      gap: 0.5rem;
    }
  
    .icon-btn {
      background: none;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 4px;
      padding: 0.4rem 0.6rem;
      font-size: 0.9rem;
      cursor: pointer;
      transition: all 0.2s;
      opacity: 0.6;
    }
  
    .icon-btn:hover {
      opacity: 1;
      border-color: rgba(0, 255, 65, 0.4);
    }
  
    .icon-btn.active {
      opacity: 1;
      border-color: #00ff41;
      background: rgba(0, 255, 65, 0.1);
    }
  
    .icon-btn.required {
      position: relative;
      border-color: #ffaa00;
    }
  
    .icon-btn.required.invalid {
      border-color: #ff4444;
      animation: pulse-error 1s ease infinite;
    }
  
    @keyframes pulse-error {
      0%, 100% { box-shadow: 0 0 0 0 rgba(255, 68, 68, 0.4); }
      50% { box-shadow: 0 0 10px 2px rgba(255, 68, 68, 0.3); }
    }
  
    .required-badge {
      position: absolute;
      top: -4px;
      right: -4px;
      width: 14px;
      height: 14px;
      background: #ff4444;
      border-radius: 50%;
      font-size: 0.6rem;
      font-weight: bold;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
    }
  
    /* ========== Notes Field (with required state) ========== */
    .notes-field {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
  
    .notes-field.required {
      padding: 0.5rem;
      background: rgba(255, 170, 0, 0.05);
      border: 1px solid rgba(255, 170, 0, 0.3);
      border-radius: 4px;
    }
  
    .notes-label {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.6rem;
      letter-spacing: 0.1em;
      color: #888;
    }
  
    .notes-label.required {
      color: #ffaa00;
      font-weight: 600;
    }
  
    .notes-error {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: #ff4444;
    }
  
    /* ========== Textareas ========== */
    .cyber-textarea {
      width: 100%;
      padding: 0.5rem 0.75rem;
      background: #000000;
      border: 1px solid rgba(0, 255, 65, 0.4);
      border-radius: 4px;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      resize: vertical;
      outline: none;
      transition: all 0.2s;
    }
  
    .cyber-textarea::placeholder {
      color: #444;
    }
  
    .cyber-textarea:focus {
      border-color: #00ff41;
      box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
    }
  
    .cyber-textarea.invalid {
      border-color: #ff4444;
      box-shadow: 0 0 10px rgba(255, 68, 68, 0.2);
    }
  
    /* ========== Attachment Zone ========== */
    .attachment-zone {
      border: 1px dashed rgba(0, 255, 65, 0.4);
      border-radius: 4px;
      padding: 0.75rem;
      text-align: center;
      transition: all 0.2s;
    }
  
    .attachment-zone:hover {
      border-color: #00ff41;
      background: rgba(0, 255, 65, 0.05);
    }
  
    .attachment-label {
      cursor: pointer;
    }
  
    .file-input {
      display: none;
    }
  
    .attachment-text {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #666;
    }
  
    /* ========== Validation Errors ========== */
    .validation-errors {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
  
    .error-tag {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem;
      color: #ff4444;
      background: rgba(255, 68, 68, 0.1);
      border: 1px solid rgba(255, 68, 68, 0.3);
      border-radius: 3px;
      padding: 0.25rem 0.5rem;
    }
  
    /* ========== Loading State ========== */
    .loading-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1rem;
      padding: 2rem;
      color: #666;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
    }
  
    .loading-pulse {
      width: 3rem;
      height: 3rem;
      border: 2px solid rgba(0, 255, 65, 0.3);
      border-radius: 50%;
      animation: pulse-ring 1.5s ease infinite;
    }
  
    @keyframes pulse-ring {
      0% { transform: scale(0.8); opacity: 1; }
      100% { transform: scale(1.5); opacity: 0; }
    }
  
    /* ========== Footer ========== */
    .panel-footer {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      padding: 1rem 1.25rem;
      border-top: 1px solid rgba(0, 255, 65, 0.2);
      background: rgba(0, 0, 0, 0.3);
    }
  
    .error-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(255, 68, 68, 0.1);
      border: 1px solid rgba(255, 68, 68, 0.4);
      border-radius: 4px;
      padding: 0.5rem 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #ff4444;
    }
  
    .error-dismiss {
      background: none;
      border: none;
      color: #ff4444;
      font-size: 1.25rem;
      cursor: pointer;
      opacity: 0.7;
    }
  
    .error-dismiss:hover {
      opacity: 1;
    }
  
    .submit-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }
  
    .submit-summary {
      display: flex;
      flex-direction: column;
      gap: 0.1rem;
    }
  
    .summary-item {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #888;
    }
  
    .summary-total {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.1rem;
      font-weight: 700;
      color: #00ff41;
      text-shadow: 0 0 15px rgba(0, 255, 65, 0.4);
    }
  
    .submit-btn {
      flex: 1;
      max-width: 250px;
      padding: 0.875rem 1.5rem;
      background: rgba(0, 255, 65, 0.1);
      border: 2px solid rgba(0, 255, 65, 0.3);
      border-radius: 6px;
      color: rgba(0, 255, 65, 0.5);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      cursor: not-allowed;
      transition: all 0.3s;
    }
  
    .submit-btn.ready {
      cursor: pointer;
      color: #00ff41;
      border-color: #00ff41;
      box-shadow: 0 0 25px rgba(0, 255, 65, 0.25);
    }
  
    .submit-btn.ready:hover {
      background: rgba(0, 255, 65, 0.2);
      box-shadow:
        0 0 35px rgba(0, 255, 65, 0.35),
        inset 0 0 20px rgba(0, 255, 65, 0.05);
    }
  
    .submit-btn.has-overrides {
      border-color: #ff4444;
      color: #ff4444;
      background: rgba(255, 68, 68, 0.1);
      box-shadow: 0 0 20px rgba(255, 68, 68, 0.2);
    }
  
    .submit-btn.has-overrides:hover {
      background: rgba(255, 68, 68, 0.2);
    }
  
    .submit-btn:disabled {
      cursor: not-allowed;
    }
  
    .btn-spinner {
      display: inline-block;
      width: 1rem;
      height: 1rem;
      border: 2px solid rgba(0, 255, 65, 0.3);
      border-top-color: #00ff41;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-right: 0.5rem;
    }
  
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  
    /* ========== Scrollbar ========== */
    .panel-content::-webkit-scrollbar {
      width: 6px;
    }
  
    .panel-content::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.3);
      border-radius: 3px;
    }
  
    .panel-content::-webkit-scrollbar-thumb {
      background: rgba(0, 255, 65, 0.3);
      border-radius: 3px;
    }
  
    .panel-content::-webkit-scrollbar-thumb:hover {
      background: rgba(0, 255, 65, 0.5);
    }
  </style>