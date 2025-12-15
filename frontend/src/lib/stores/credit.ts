/**
 * Credit Pipeline Store v3
 *
 * Phase 3: Duplicate Prevention System
 * - Invoice key generation
 * - Return history tracking
 * - Delta calculation
 * - Override flow for blocked/capped items
 */

import { derived, get, writable } from 'svelte/store';

// ============================================
// CONSTANTS
// ============================================

export const REASON_CODES = [
    { code: '01', label: '(01) MISPICK' },
    { code: '02', label: '(02) SHORT ON TRUCK' },
    { code: '03', label: '(03) SHORT/FOUND ON TRUCK' },
    { code: '04', label: '(04) SALES ERROR' },
    { code: '05', label: '(05) PRODUCT QUALITY/TEMP' },
    { code: '06', label: '(06) PRODUCT DAMAGED' },
    { code: '10', label: '(10) NYC DOE REFUSED' },
    { code: '13', label: '(13) REBATE' },
    { code: '14', label: '(14) FOUND ON DOCK' },
    { code: '15', label: '(15) MISLOAD' },
    { code: '16', label: '(16) C2C CUST TO CUST' },
    { code: '25', label: '(25) DONATION' },
    { code: 'XX', label: '(XX) INTERNAL GOODWILL' },
] as const;

export const UOM_OPTIONS = [
    { value: 'CS', label: 'CS' },
    { value: 'EACH', label: 'EACH' },
] as const;

export const NOTES_MAX_LENGTH = 500;
export const NOTES_OVERFLOW_MESSAGE = "for a sob story this long you're gonna have to sum it up or call credit bro";

// API base URL - empty for same-origin requests in production
const API_BASE = 'http://localhost:8000';

// ============================================
// TYPES
// ============================================

export interface Customer {
    customerId: string;
    customerName: string;
    customerNumber: string;
    displayText: string;
}

export interface Invoice {
    invoiceId: string;
    invoiceNumber: string;
    invoiceDate: string;
    poNumber: string | null;
    customerId: string;
    totalAmount: number;
    displayText: string;
}

export interface Attachment {
    id: string;
    fileName: string;
    fileSize: number;
    mimeType: string;
    thumbnailUrl?: string;
    uploadedAt: Date;
}

export interface LineItemCredit {
    // Selection state
    selected: boolean;
    // Credit details
    creditQuantity: number;
    creditUOM: 'CS' | 'EACH';
    creditReason: string;
    creditAmount: number;
    // Partial credit
    isPartialCredit: boolean;
    partialExplanation: string;
    // Validation
    isValid: boolean;
    validationErrors: string[];
    // Phase 3: Override tracking
    requiresOverride: boolean;
    overrideExplanation: string;
    wasCapped: boolean;
    originalRequestedQty: number;
}

export interface LineItem {
    lineItemId: string;
    invoiceId: string;
    itemNumber: string;
    description: string;
    // Original invoice values
    quantity: number;
    uom: string;
    unitPrice: number;
    extendedPrice: number;
    // For duplicate checking (InvoiceNumber|ItemNumber)
    invoiceKey: string;
    // Credit request fields
    credit: LineItemCredit;
}

// Phase 3: Return History Types
export interface ReturnRecord {
    creditRequestId: string;
    quantity: number;
    date: Date;
    wasOverride: boolean;
}

export interface ReturnHistory {
    key: string;                    // SalesmanId-InvoiceNumber-ItemNumber
    salesmanId: string;
    invoiceNumber: string;
    itemNumber: string;
    originalQty: number;
    returnedQty: number;
    delta: number;                  // originalQty - returnedQty
    returns: ReturnRecord[];
    lastUpdated: Date;
}

export type DupeStatus = 'ok' | 'capped' | 'blocked';

export interface DupeCheckResult {
    lineItemId: string;
    itemNumber: string;
    description: string;
    requestedQty: number;
    originalQty: number;
    previouslyReturned: number;
    availableDelta: number;
    status: DupeStatus;
    message: string;
}

export interface OverrideResolution {
    lineItemId: string;
    action: 'cap' | 'override';
    explanation?: string;
}

export interface CreditRequest {
    requestId: string | null;
    customerId: string;
    customerName: string;
    invoiceId: string;
    invoiceNumber: string;
    poNumber: string | null;
    items: LineItem[];
    notes: string;
    attachments: Attachment[];
    totalCreditAmount: number;
    status: 'draft' | 'pending' | 'approved' | 'rejected';
    submittedAt: Date | null;
    submittedBy: string;
    // Phase 3: Override tracking
    hasOverrides: boolean;
    overrideCount: number;
}

export type PanelState = 'locked' | 'materializing' | 'active' | 'complete';

export interface CreditPipelineState {
    // Panel states
    panel1State: PanelState;
    panel2State: PanelState;

    // Panel 1: Customer & Invoice
    customerSearch: string;
    customerResults: Customer[];
    selectedCustomer: Customer | null;
    invoiceSearch: string;
    invoiceResults: Invoice[];
    selectedInvoice: Invoice | null;

    // Panel 2: Line Items + Notes + Attachments + Submit
    lineItems: LineItem[];
    notes: string;
    attachments: Attachment[];

    // Final request
    creditRequest: CreditRequest | null;

    // Loading states
    loadingCustomers: boolean;
    loadingInvoices: boolean;
    loadingLineItems: boolean;
    submitting: boolean;

    // Error state
    error: string | null;

    // Phase 3: Dupe detection
    returnHistory: Map<string, ReturnHistory>;
    dupeCheckResults: DupeCheckResult[];
    showOverrideModal: boolean;
    pendingOverrides: DupeCheckResult[];
}

// ============================================
// HELPER: Create default credit state
// ============================================

function createDefaultCredit(): LineItemCredit {
    return {
        selected: false,
        creditQuantity: 0,
        creditUOM: 'CS',
        creditReason: '',
        creditAmount: 0,
        isPartialCredit: false,
        partialExplanation: '',
        isValid: false,
        validationErrors: [],
        requiresOverride: false,
        overrideExplanation: '',
        wasCapped: false,
        originalRequestedQty: 0,
    };
}

// ============================================
// HELPER: Validate line item credit
// ============================================

function validateLineItemCredit(item: LineItem): LineItemCredit {
    const errors: string[] = [];
    const credit = item.credit;

    if (!credit.selected) {
        return { ...credit, isValid: true, validationErrors: [] };
    }

    // Reason required
    if (!credit.creditReason) {
        errors.push('Reason required');
    }

    // Quantity validation
    if (credit.creditQuantity <= 0) {
        errors.push('Quantity must be > 0');
    }
    if (credit.creditQuantity > item.quantity) {
        errors.push(`Quantity cannot exceed ${item.quantity}`);
    }

    // Credit amount validation
    const maxCredit = item.unitPrice * credit.creditQuantity;
    if (credit.creditAmount <= 0) {
        errors.push('Credit amount must be > 0');
    }
    if (credit.creditAmount > maxCredit) {
        errors.push(`Credit cannot exceed $${maxCredit.toFixed(2)}`);
    }

    // Partial credit explanation required if partial
    if (credit.isPartialCredit && !credit.partialExplanation.trim()) {
        errors.push('Partial credit requires explanation');
    }

    // Override explanation required if override flagged
    if (credit.requiresOverride && !credit.overrideExplanation.trim()) {
        errors.push('Override requires explanation');
    }

    return {
        ...credit,
        isValid: errors.length === 0,
        validationErrors: errors,
    };
}

// ============================================
// HELPER: Build return history key
// ============================================

function buildReturnKey(invoiceNumber: string, itemNumber: string): string {
    return `${invoiceNumber}-${itemNumber}`;
}

// ============================================
// STORE
// ============================================

const initialState: CreditPipelineState = {
    panel1State: 'materializing',
    panel2State: 'locked',

    customerSearch: '',
    customerResults: [],
    selectedCustomer: null,
    invoiceSearch: '',
    invoiceResults: [],
    selectedInvoice: null,

    lineItems: [],
    notes: '',
    attachments: [],

    creditRequest: null,

    loadingCustomers: false,
    loadingInvoices: false,
    loadingLineItems: false,
    submitting: false,

    error: null,

    // Phase 3: Dupe detection (starts empty, populated during session)
    returnHistory: new Map<string, ReturnHistory>(),
    dupeCheckResults: [],
    showOverrideModal: false,
    pendingOverrides: [],
};

function createCreditStore() {
    const { subscribe, set, update } = writable<CreditPipelineState>(initialState);

    const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    return {
        subscribe,

        // ========== Panel State Management ==========

        initPipeline() {
            update(s => ({ ...s, panel1State: 'materializing' }));
            setTimeout(() => {
                update(s => ({ ...s, panel1State: 'active' }));
            }, 1500);
        },

        advanceToPanel2() {
            update(s => ({
                ...s,
                panel1State: 'complete',
                panel2State: 'materializing',
            }));
            setTimeout(() => {
                update(s => ({ ...s, panel2State: 'active' }));
            }, 800);
        },

        completePanel2() {
            update(s => ({ ...s, panel2State: 'complete' }));
        },

        // ========== Panel 1: Customer & Invoice ==========

        async searchCustomers(query: string) {
            update(s => ({ ...s, customerSearch: query, loadingCustomers: true }));

            if (query.length < 2) {
                update(s => ({ ...s, customerResults: [], loadingCustomers: false }));
                return;
            }

            try {
                const res = await fetch(
                    `${API_BASE}/api/credit/customers?search=${encodeURIComponent(query)}`
                );

                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }

                const data = await res.json();
                const customers: Customer[] = data.customers.map((c: any) => ({
                    customerId: c.customerNumber,
                    customerName: c.customerName,
                    customerNumber: c.customerNumber,
                    displayText: c.displayText || `${c.customerName} (${c.customerNumber})`,
                }));

                update(s => ({ ...s, customerResults: customers, loadingCustomers: false }));
            } catch (err) {
                console.error('Failed to load customers:', err);
                update(s => ({ ...s, error: 'Failed to load customers', loadingCustomers: false }));
            }
        },

        selectCustomer(customer: Customer) {
            update(s => ({
                ...s,
                selectedCustomer: customer,
                customerSearch: customer.displayText,
                customerResults: [],
                selectedInvoice: null,
                invoiceResults: [],
                invoiceSearch: '',
                lineItems: [],
            }));

            this.loadInvoicesForCustomer(customer.customerId);
        },

        clearCustomer() {
            update(s => ({
                ...s,
                selectedCustomer: null,
                customerSearch: '',
                customerResults: [],
                selectedInvoice: null,
                invoiceResults: [],
                invoiceSearch: '',
                lineItems: [],
                panel2State: 'locked',
            }));
        },

        clearInvoice() {
            update(s => ({
                ...s,
                selectedInvoice: null,
                invoiceSearch: '',
                lineItems: [],
                panel2State: 'locked',
            }));
        },

        async loadInvoicesForCustomer(customerId: string) {
            update(s => ({ ...s, loadingInvoices: true }));

            try {
                const res = await fetch(
                    `${API_BASE}/api/credit/invoices?customer_id=${encodeURIComponent(customerId)}`
                );

                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }

                const data = await res.json();
                const invoices: Invoice[] = data.invoices.map((inv: any) => ({
                    invoiceId: inv.invoiceNumber,
                    invoiceNumber: inv.invoiceNumber,
                    invoiceDate: inv.invoiceDate,
                    poNumber: inv.poNumber,
                    customerId: inv.customerId,
                    totalAmount: inv.totalAmount || 0,
                    displayText: inv.displayText || `${inv.invoiceNumber} | ${inv.invoiceDate} | ${inv.poNumber ? 'PO: ' + inv.poNumber : 'No PO'}`,
                }));

                update(s => ({
                    ...s,
                    invoiceResults: invoices,
                    loadingInvoices: false,
                }));
            } catch (err) {
                console.error('Failed to load invoices:', err);
                update(s => ({ ...s, error: 'Failed to load invoices', loadingInvoices: false }));
            }
        },

        searchInvoices(query: string) {
            update(s => ({ ...s, invoiceSearch: query }));
        },

        async selectInvoice(invoice: Invoice) {
            update(s => ({
                ...s,
                selectedInvoice: invoice,
                invoiceSearch: invoice.displayText,
            }));

            await this.loadLineItems(invoice.invoiceId);
            this.advanceToPanel2();
        },

        // ========== Panel 2: Line Items ==========

        async loadLineItems(invoiceId: string) {
            update(s => ({ ...s, loadingLineItems: true }));

            try {
                const res = await fetch(
                    `${API_BASE}/api/credit/lineitems?invoice_id=${encodeURIComponent(invoiceId)}`
                );

                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }

                const data = await res.json();
                const items: LineItem[] = data.lineItems.map((li: any) => ({
                    lineItemId: li.lineItemId || `${li.invoiceId}-${li.itemNumber}`,
                    invoiceId: li.invoiceId,
                    itemNumber: li.itemNumber,
                    description: li.description,
                    quantity: li.quantity,
                    uom: li.uom || 'CS',
                    unitPrice: li.unitPrice,
                    extendedPrice: li.extendedPrice,
                    invoiceKey: li.invoiceKey || `${li.invoiceId}|${li.itemNumber}`,
                    credit: createDefaultCredit(),
                }));

                update(s => ({
                    ...s,
                    lineItems: items,
                    loadingLineItems: false,
                }));
            } catch (err) {
                console.error('Failed to load line items:', err);
                update(s => ({ ...s, error: 'Failed to load line items', loadingLineItems: false }));
            }
        },

        toggleLineItem(lineItemId: string) {
            update(s => ({
                ...s,
                lineItems: s.lineItems.map(item => {
                    if (item.lineItemId !== lineItemId) return item;

                    const newSelected = !item.credit.selected;
                    const newCredit: LineItemCredit = newSelected
                        ? {
                            ...item.credit,
                            selected: true,
                            creditQuantity: item.quantity,
                            creditUOM: item.uom as 'CS' | 'EACH',
                            creditAmount: item.extendedPrice,
                            originalRequestedQty: item.quantity,
                        }
                        : createDefaultCredit();

                    return { ...item, credit: newCredit };
                }),
            }));
        },

        updateLineItemCredit(lineItemId: string, updates: Partial<LineItemCredit>) {
            update(s => ({
                ...s,
                lineItems: s.lineItems.map(item => {
                    if (item.lineItemId !== lineItemId) return item;

                    const updatedCredit = { ...item.credit, ...updates };

                    // Auto-calculate credit amount if quantity changes
                    if ('creditQuantity' in updates && !('creditAmount' in updates)) {
                        updatedCredit.creditAmount = updatedCredit.creditQuantity * item.unitPrice;
                    }

                    // Track original requested qty for override flow
                    if ('creditQuantity' in updates && !updatedCredit.wasCapped) {
                        updatedCredit.originalRequestedQty = updates.creditQuantity!;
                    }

                    // Validate
                    const validatedItem = { ...item, credit: updatedCredit };
                    const validated = validateLineItemCredit(validatedItem);

                    return { ...item, credit: validated };
                }),
            }));
        },

        // ========== Notes & Attachments ==========

        updateNotes(notes: string) {
            update(s => ({ ...s, notes }));
        },

        addAttachment(file: File) {
            const attachment: Attachment = {
                id: `ATT-${Date.now()}`,
                fileName: file.name,
                fileSize: file.size,
                mimeType: file.type,
                thumbnailUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
                uploadedAt: new Date(),
            };

            update(s => ({
                ...s,
                attachments: [...s.attachments, attachment],
            }));
        },

        removeAttachment(attachmentId: string) {
            update(s => ({
                ...s,
                attachments: s.attachments.filter(a => a.id !== attachmentId),
            }));
        },

        // ========== Phase 3: Duplicate Detection ==========

        /**
         * Check selected items against return history
         * Returns array of items that need attention (capped or blocked)
         */
        checkForDuplicates(): DupeCheckResult[] {
            const state = get({ subscribe });
            const results: DupeCheckResult[] = [];

            const selectedItems = state.lineItems.filter(item => item.credit.selected);

            for (const item of selectedItems) {
                const key = buildReturnKey(
                    state.selectedInvoice!.invoiceNumber,
                    item.itemNumber
                );

                const history = state.returnHistory.get(key);

                if (!history) {
                    // No history - OK
                    continue;
                }

                const requestedQty = item.credit.creditQuantity;
                const availableDelta = history.delta;

                if (availableDelta === 0) {
                    // Fully returned - BLOCKED
                    results.push({
                        lineItemId: item.lineItemId,
                        itemNumber: item.itemNumber,
                        description: item.description,
                        requestedQty,
                        originalQty: history.originalQty,
                        previouslyReturned: history.returnedQty,
                        availableDelta: 0,
                        status: 'blocked',
                        message: `Fully returned (${history.returnedQty} of ${history.originalQty} ${item.uom})`,
                    });
                } else if (requestedQty > availableDelta) {
                    // Partial return possible - CAPPED
                    results.push({
                        lineItemId: item.lineItemId,
                        itemNumber: item.itemNumber,
                        description: item.description,
                        requestedQty,
                        originalQty: history.originalQty,
                        previouslyReturned: history.returnedQty,
                        availableDelta,
                        status: 'capped',
                        message: `Only ${availableDelta} of ${history.originalQty} ${item.uom} remaining (${history.returnedQty} previously returned)`,
                    });
                }
                // If requestedQty <= availableDelta, it's OK - no entry needed
            }

            update(s => ({ ...s, dupeCheckResults: results }));
            return results;
        },

        /**
         * Show override modal with pending items
         */
        showOverrideModalWithItems(items: DupeCheckResult[]) {
            update(s => ({
                ...s,
                showOverrideModal: true,
                pendingOverrides: items,
            }));
        },

        /**
         * Close override modal
         */
        closeOverrideModal() {
            update(s => ({
                ...s,
                showOverrideModal: false,
                pendingOverrides: [],
            }));
        },

        /**
         * Apply override resolutions and continue submit
         */
        applyOverrideResolutions(resolutions: OverrideResolution[]) {
            update(s => {
                const updatedLineItems = s.lineItems.map(item => {
                    const resolution = resolutions.find(r => r.lineItemId === item.lineItemId);
                    if (!resolution) return item;

                    const dupeResult = s.pendingOverrides.find(d => d.lineItemId === item.lineItemId);
                    if (!dupeResult) return item;

                    if (resolution.action === 'cap') {
                        // Cap quantity to available delta
                        const cappedQty = dupeResult.availableDelta;
                        return {
                            ...item,
                            credit: {
                                ...item.credit,
                                creditQuantity: cappedQty,
                                creditAmount: cappedQty * item.unitPrice,
                                wasCapped: true,
                                requiresOverride: false,
                            },
                        };
                    } else {
                        // Override - keep original qty, flag it
                        return {
                            ...item,
                            credit: {
                                ...item.credit,
                                requiresOverride: true,
                                overrideExplanation: resolution.explanation || '',
                            },
                        };
                    }
                });

                return {
                    ...s,
                    lineItems: updatedLineItems,
                    showOverrideModal: false,
                    pendingOverrides: [],
                };
            });
        },

        /**
         * Record successful return in history
         */
        recordReturn(item: LineItem, creditRequestId: string) {
            update(s => {
                const key = buildReturnKey(
                    s.selectedInvoice!.invoiceNumber,
                    item.itemNumber
                );

                const existingHistory = s.returnHistory.get(key);
                const newReturnedQty = (existingHistory?.returnedQty || 0) + item.credit.creditQuantity;

                const updatedHistory: ReturnHistory = {
                    key,
                    salesmanId: '',  // No longer used
                    invoiceNumber: s.selectedInvoice!.invoiceNumber,
                    itemNumber: item.itemNumber,
                    originalQty: item.quantity,
                    returnedQty: newReturnedQty,
                    delta: item.quantity - newReturnedQty,
                    returns: [
                        ...(existingHistory?.returns || []),
                        {
                            creditRequestId,
                            quantity: item.credit.creditQuantity,
                            date: new Date(),
                            wasOverride: item.credit.requiresOverride,
                        },
                    ],
                    lastUpdated: new Date(),
                };

                const newHistory = new Map(s.returnHistory);
                newHistory.set(key, updatedHistory);

                return { ...s, returnHistory: newHistory };
            });
        },

        // ========== Submit Flow (Phase 3 Updated) ==========

        /**
         * Initiate submit - checks for dupes first
         * Returns true if can proceed, false if override modal shown
         */
        initiateSubmit(): boolean {
            const dupeResults = this.checkForDuplicates();

            if (dupeResults.length > 0) {
                this.showOverrideModalWithItems(dupeResults);
                return false;
            }

            return true;
        },

        /**
         * Final submit after any override resolution
         */
        async submitCreditRequest(): Promise<string | null> {
            const state = get({ subscribe });

            // Validate
            const selectedItems = state.lineItems.filter(item => item.credit.selected);
            if (selectedItems.length === 0) {
                update(s => ({ ...s, error: 'Select at least one item for credit' }));
                return null;
            }

            // Re-validate all items (including override explanations)
            const revalidatedItems = selectedItems.map(item => ({
                ...item,
                credit: validateLineItemCredit(item),
            }));

            const invalidItems = revalidatedItems.filter(item => !item.credit.isValid);
            if (invalidItems.length > 0) {
                update(s => ({ ...s, error: 'Please fix validation errors before submitting' }));
                return null;
            }

            if (state.notes.length > NOTES_MAX_LENGTH) {
                update(s => ({ ...s, error: NOTES_OVERFLOW_MESSAGE }));
                return null;
            }

            update(s => ({ ...s, submitting: true, error: null }));

            // Build credit request
            const overrideItems = selectedItems.filter(item => item.credit.requiresOverride);
            const totalCredit = selectedItems.reduce(
                (sum, item) => sum + item.credit.creditAmount,
                0
            );

            const creditRequest: CreditRequest = {
                requestId: null,
                customerId: state.selectedCustomer!.customerId,
                customerName: state.selectedCustomer!.customerName,
                invoiceId: state.selectedInvoice!.invoiceId,
                invoiceNumber: state.selectedInvoice!.invoiceNumber,
                poNumber: state.selectedInvoice!.poNumber,
                items: selectedItems,
                notes: state.notes,
                attachments: state.attachments,
                totalCreditAmount: totalCredit,
                status: 'draft',
                submittedAt: null,
                submittedBy: 'user',  // Will be set from auth when implemented
                hasOverrides: overrideItems.length > 0,
                overrideCount: overrideItems.length,
            };

            // Simulate API call
            await delay(1000);

            const requestId = `CR-${Date.now().toString(36).toUpperCase()}`;

            // Record returns in history
            for (const item of selectedItems) {
                this.recordReturn(item, requestId);
            }

            update(s => ({
                ...s,
                submitting: false,
                creditRequest: {
                    ...creditRequest,
                    requestId,
                    status: 'pending',
                    submittedAt: new Date(),
                },
            }));

            this.completePanel2();

            return requestId;
        },

        // ========== Reset ==========

        reset() {
            set({
                ...initialState,
                returnHistory: new Map<string, ReturnHistory>(),
            });
            setTimeout(() => {
                update(s => ({ ...s, panel1State: 'active' }));
            }, 800);
        },

        clearError() {
            update(s => ({ ...s, error: null }));
        },
    };
}

export const credit = createCreditStore();

// ============================================
// DERIVED STORES
// ============================================

/** Filtered invoices based on search */
export const filteredInvoices = derived(
    credit,
    $credit => {
        if (!$credit.invoiceSearch.trim()) {
            return $credit.invoiceResults;
        }
        const query = $credit.invoiceSearch.toLowerCase();
        return $credit.invoiceResults.filter(inv =>
            inv.invoiceNumber.toLowerCase().includes(query) ||
            inv.poNumber?.toLowerCase().includes(query) ||
            inv.invoiceDate.includes(query)
        );
    }
);

/** Selected line items only */
export const selectedLineItems = derived(
    credit,
    $credit => $credit.lineItems.filter(item => item.credit.selected)
);

/** Total credit amount for selected items */
export const totalCreditAmount = derived(
    selectedLineItems,
    $items => $items.reduce((sum, item) => sum + item.credit.creditAmount, 0)
);

/** Count of selected items */
export const selectedItemCount = derived(
    selectedLineItems,
    $items => $items.length
);

/** All selected items are valid */
export const allSelectedValid = derived(
    selectedLineItems,
    $items => $items.length > 0 && $items.every(item => item.credit.isValid)
);

/** Notes length check */
export const notesOverLimit = derived(
    credit,
    $credit => $credit.notes.length > NOTES_MAX_LENGTH
);

/** Can advance from panel 1 */
export const canAdvancePanel1 = derived(
    credit,
    $credit => $credit.selectedCustomer !== null && $credit.selectedInvoice !== null
);

/** Can submit (panel 2 ready) */
export const canSubmit = derived(
    [selectedLineItems, allSelectedValid, notesOverLimit, credit],
    ([$items, $valid, $overLimit, $credit]) =>
        $items.length > 0 && $valid && !$overLimit && !$credit.submitting
);

/** Items requiring override */
export const itemsWithOverride = derived(
    selectedLineItems,
    $items => $items.filter(item => item.credit.requiresOverride)
);