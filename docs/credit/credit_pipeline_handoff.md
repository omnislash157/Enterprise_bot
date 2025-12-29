# Credit Pipeline Handoff

**Date:** 2024-12-29
**Status:** Backend verified, waiting on IT for frontend test

---

## What We Built

```
Sales fills form → Selects DSM → Clicks Generate
       ↓
   DOCX downloads (their submission only)
       ↓
   Outlook opens (mailto: prefilled)
       ↓
   Old school email forwarding: DSM → Revenue → Credit Guy
```

---

## Tests Passed ✅

| Test | Result |
|------|--------|
| ODBC Driver 17 connection | ✅ Working |
| Windows Auth (Trusted_Connection) | ✅ Working |
| `GET /api/credit/customers?search=bel` | ✅ Returns real customers |
| `GET /api/credit/invoices?customer_id=BEL003` | ✅ Returns real invoices |
| DOCX generation (test file) | ✅ Generated correctly |

**Sample output:**
```
('BEL003', 'BELMONT MIDDLE HIGH SCHOOL ')
('681742', 'BASSO')
('683876', 'DERAILED TAP HOUSE')
Connection works!
```

---

## Files Created

| File | Location | Purpose |
|------|----------|---------|
| `credit_routes.py` | `auth/` | FastAPI routes - customers, invoices, lineitems, generate |
| `credit_docx_generator.js` | `auth/` | Node script for styled DOCX output |
| `DRISCOLL_CREDIT_SCHEMA.md` | `docs/` | CreditManagement DB schema reference |

---

## API Endpoints

| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/credit/config` | Ready |
| GET | `/api/credit/customers?search=` | ✅ Tested |
| GET | `/api/credit/invoices?customer_id=` | ✅ Tested |
| GET | `/api/credit/lineitems?invoice_id=` | Ready (not tested yet) |
| GET | `/api/credit/salesmen` | Ready |
| POST | `/api/credit/generate/unform` | Ready (PDF for Unform) |
| POST | `/api/credit/generate/visual` | Ready (DOCX for email) |
| POST | `/api/credit/submit` | Ready (saves to DB) |

---

## Connection Details

```python
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=BID1;"
    "DATABASE=CreditManagement;"
    "Trusted_Connection=yes;"
)
```

- **Auth:** Windows Authentication (domain login)
- **No .env secrets needed** for DB connection
- **Only works on:** Driscoll network (VM or laptop)

---

## Waiting On

| Blocker | Who | Why |
|---------|-----|-----|
| Azure AD admin consent | IT | Multi-tenant set to "organizations", need one-time approval |

Once IT approves → can login to frontend → test full flow

---

## TODO (Next Session)

### Priority 1: Frontend Test
- [ ] IT admin consent
- [ ] Login to frontend on Driscoll machine
- [ ] Test customer search → invoice select → line items load
- [ ] Test DOCX generation + download

### Priority 2: Frontend Field Mapping
- [ ] Update `credit.ts` to map PascalCase → camelCase
- [ ] Claude Code prompt ready (see previous chat)

### Priority 3: PDF for Unform
- [ ] Get Unform template/spec for bounding box coordinates
- [ ] Adjust X,Y positions in `generate_unform_pdf()`
- [ ] Test with actual Unform system

### Priority 4: Polish
- [ ] DSM dropdown - add real emails to `CREDIT_CONFIG`
- [ ] Test mailto: prefill opens Outlook correctly
- [ ] End-to-end: submit → DOCX → email → forward chain

---

## Quick Test Commands

```powershell
# Start backend
cd C:\Users\mhartigan\Documents\enterprise_bot
python -m uvicorn core.main:app --reload --port 8000

# Test endpoints (another terminal)
Invoke-RestMethod "http://localhost:8000/api/credit/customers?search=bel"
Invoke-RestMethod "http://localhost:8000/api/credit/invoices?customer_id=BEL003"
```

---

## Architecture Reminder

```
Frontend (credit.ts)     →  Backend (credit_routes.py)  →  SQL Server (BID1)
     │                              │                            │
     │ Svelte store                 │ FastAPI                    │ CreditManagement DB
     │ API calls                    │ pyodbc                     │ Windows Auth
     ↓                              ↓                            ↓
 CreditForm.svelte          DOCX generator (Node)         vw_UniqueCustomers
                                    │                     vw_CustomerInvoices
                                    ↓                     vw_InvoiceLineItems
                            Unform PDF (reportlab)        CreditRequests (write)
                                                          CreditRequestItems (write)
```

---

**END OF HANDOFF**
