# Driscoll CreditManagement Database Schema

**Last Updated:** 2024-12-29
**Server:** BID1 (SQL Server)
**Database:** CreditManagement
**Authentication:** Windows Authentication (Trusted_Connection)

---

## Overview

| Object Type | Count | Purpose |
|-------------|-------|---------|
| Tables | 6 | Credit requests, invoices, staging |
| Views | 4 | Flattened queries for API consumption |

---

## Tables

### dbo.CreditRequests
Credit request header - one row per submission.

| # | Column | Type | Size | Nullable | Default | Notes |
|---|--------|------|------|----------|---------|-------|
| 1 | RequestID | int | | NO | IDENTITY | PK |
| 2 | InvoiceNo | varchar | 50 | NO | | FK reference |
| 3 | CustomerNo | varchar | 50 | NO | | Customer number |
| 4 | SalesmanID | varchar | 50 | NO | | Submitting salesman |
| 5 | TotalCredit | decimal | | NO | | Sum of line items |
| 6 | Status | varchar | 20 | YES | 'pending' | pending/approved/rejected/completed |
| 7 | Notes | nvarchar | MAX | YES | | Free text notes |
| 8 | CreatedAt | datetime2 | | YES | getdate() | Submission timestamp |
| 9 | ProcessedAt | datetime2 | | YES | | When credit was entered |
| 10 | ProcessedBy | varchar | 100 | YES | | Who entered to telnet |

---

### dbo.CreditRequestItems
Credit request line items - multiple rows per request.

| # | Column | Type | Size | Nullable | Default | Notes |
|---|--------|------|------|----------|---------|-------|
| 1 | ItemID | int | | NO | IDENTITY | PK |
| 2 | RequestID | int | | YES | | FK → CreditRequests.RequestID |
| 3 | InvoiceNo | varchar | 50 | NO | | Denormalized for queries |
| 4 | ItemNo | varchar | 50 | NO | | Product SKU |
| 5 | Description | varchar | 255 | YES | | Product description |
| 6 | Qty | decimal | | NO | | Credit quantity |
| 7 | Price | decimal | | NO | | Unit price |
| 8 | CreditAmount | decimal | | NO | | Qty × Price (may differ) |
| 9 | Reason | varchar | 100 | NO | | **EXACT** - reason code |

**Reason Codes (EXACT - case sensitive):**
```
(01) MISPICK
(02) SHORT ON TRUCK
(03) SHORT/FOUND ON TRUCK
(04) SALES ERROR
(05) PRODUCT QUALITY/TEMP
(06) PRODUCT DAMAGED
(10) NYC DOE REFUSED
(13) REBATE
(14) FOUND ON DOCK
(15) MISLOAD
(16) C2C CUST TO CUST
(25) DONATION
(XX) INTERNAL GOODWILL
```

---

### dbo.InvoiceHeader
Invoice master data - imported from ERP.

| # | Column | Type | Size | Nullable | Default | Notes |
|---|--------|------|------|----------|---------|-------|
| 1 | InvoiceNo | varchar | 50 | NO | | PK |
| 2 | OrderNo | varchar | 50 | YES | | Order reference |
| 3 | CustomerNo | varchar | 50 | YES | | Customer number |
| 4 | CustomerName | varchar | 500 | YES | | Customer name |
| 5 | BillToAddress | varchar | 500 | YES | | |
| 6 | BillToAddress2 | varchar | 500 | YES | | |
| 7 | BillToCity | varchar | 100 | YES | | |
| 8 | BillToState | varchar | 50 | YES | | |
| 9 | BillToZip | varchar | 20 | YES | | |
| 10 | ShipToName | varchar | 500 | YES | | |
| 11 | ShipToAddress1 | varchar | 500 | YES | | |
| 12 | ShipToAddress2 | varchar | 500 | YES | | |
| 13 | ShipToAddress3 | varchar | 500 | YES | | |
| 14 | InvoiceDate | date | | YES | | |
| 15 | PONo | varchar | 100 | YES | | PO number |
| 16 | Salesman | varchar | 100 | YES | | Salesman ID |
| 17 | Warehouse | varchar | 50 | YES | | Warehouse code |

---

### dbo.InvoiceDetail
Invoice line items - imported from ERP.

| # | Column | Type | Size | Nullable | Default | Notes |
|---|--------|------|------|----------|---------|-------|
| 1 | DetailID | int | | NO | IDENTITY | PK |
| 2 | InvoiceNo | varchar | 50 | NO | | FK → InvoiceHeader |
| 3 | OrderNo | varchar | 50 | YES | | |
| 4 | ItemNo | varchar | 50 | YES | | Product SKU |
| 5 | Description | varchar | 500 | YES | | Product description |
| 6 | PackSize | varchar | 100 | YES | | Pack configuration |
| 7 | Qty | decimal | | YES | | Quantity ordered |
| 8 | Weight | decimal | | YES | | Weight |
| 9 | UOM | varchar | 50 | YES | | **EXACT** - unit of measure |
| 10 | Cost | decimal | | YES | | Cost |
| 11 | Price | decimal | | YES | | Sell price |

**UOM Values (EXACT - case sensitive):**
```
CS      - Case
EACH    - Each/Unit
LB      - Pound
(others as defined in ERP)
```

---

### dbo.stg_Header
Staging table for invoice header imports.

| # | Column | Type | Size | Nullable | Notes |
|---|--------|------|------|----------|-------|
| 1 | OrderNo | varchar | 50 | YES | |
| 2 | InvoiceNo | varchar | 50 | YES | |
| 3 | CustomerNo | varchar | 50 | YES | |
| 4 | CustomerName | varchar | 500 | YES | |
| 5 | BillToAddress | varchar | 500 | YES | |
| 6 | BillToAddress2 | varchar | 500 | YES | |
| 7 | BillToCity | varchar | 100 | YES | |
| 8 | BillToState | varchar | 50 | YES | |
| 9 | BillToZip | varchar | 20 | YES | |
| 10 | ShipToName | varchar | 500 | YES | |
| 11 | ShipToAddress1 | varchar | 500 | YES | |
| 12 | ShipToAddress2 | varchar | 500 | YES | |
| 13 | ShipToAddress3 | varchar | 500 | YES | |
| 14 | InvoiceDate | varchar | 50 | YES | String before conversion |
| 15 | PONo | varchar | MAX | YES | |
| 16 | Salesman | varchar | 100 | YES | |
| 17 | Warehouse | varchar | 50 | YES | |

---

### dbo.stg_Detail
Staging table for invoice detail imports.

| # | Column | Type | Size | Nullable | Notes |
|---|--------|------|------|----------|-------|
| 1 | OrderNo | varchar | 50 | YES | |
| 2 | InvoiceNo | varchar | 50 | YES | |
| 3 | ItemNo | varchar | 50 | YES | |
| 4 | Description | varchar | 500 | YES | |
| 5 | PackSize | varchar | 100 | YES | |
| 6 | Qty | varchar | 50 | YES | String before conversion |
| 7 | Weight | varchar | 50 | YES | String before conversion |
| 8 | UOM | varchar | 50 | YES | |
| 9 | Cost | varchar | 50 | YES | String before conversion |
| 10 | Price | varchar | 50 | YES | String before conversion |

---

## Views

### dbo.vw_UniqueCustomers
Distinct customer list for search dropdown.

| # | Column | Type | Size | Source |
|---|--------|------|------|--------|
| 1 | CustomerNumber | varchar | 50 | InvoiceHeader.CustomerNo |
| 2 | CustomerName | varchar | 500 | InvoiceHeader.CustomerName |
| 3 | SalesmanID | varchar | 100 | InvoiceHeader.Salesman |
| 4 | City | varchar | 100 | InvoiceHeader.BillToCity |
| 5 | State | varchar | 50 | InvoiceHeader.BillToState |

**Usage:** Customer search autocomplete
```sql
SELECT * FROM vw_UniqueCustomers
WHERE CustomerName LIKE '%search%' OR CustomerNumber LIKE '%search%'
```

---

### dbo.vw_CustomerInvoices
Invoices for a selected customer.

| # | Column | Type | Size | Source |
|---|--------|------|------|--------|
| 1 | InvoiceNumber | varchar | 50 | InvoiceHeader.InvoiceNo |
| 2 | CustomerNumber | varchar | 50 | InvoiceHeader.CustomerNo |
| 3 | CustomerName | varchar | 500 | InvoiceHeader.CustomerName |
| 4 | InvoiceDate | varchar | 50 | InvoiceHeader.InvoiceDate (formatted) |
| 5 | OrderNumber | varchar | 50 | InvoiceHeader.OrderNo |
| 6 | PONumber | varchar | MAX | InvoiceHeader.PONo |
| 7 | SalesmanID | varchar | 100 | InvoiceHeader.Salesman |
| 8 | Warehouse | varchar | 50 | InvoiceHeader.Warehouse |

**Usage:** Invoice dropdown after customer selected
```sql
SELECT * FROM vw_CustomerInvoices
WHERE CustomerNumber = '12345'
ORDER BY InvoiceDate DESC
```

---

### dbo.vw_InvoiceLineItems
Line items for a selected invoice - **primary view for credit form**.

| # | Column | Type | Size | Source |
|---|--------|------|------|--------|
| 1 | InvoiceNumber | varchar | 50 | InvoiceDetail.InvoiceNo |
| 2 | ItemNumber | varchar | 50 | InvoiceDetail.ItemNo |
| 3 | ItemDescription | varchar | 500 | InvoiceDetail.Description |
| 4 | Pack | varchar | 100 | InvoiceDetail.PackSize |
| 5 | Quantity | varchar | 50 | InvoiceDetail.Qty (formatted) |
| 6 | Weight | varchar | 50 | InvoiceDetail.Weight (formatted) |
| 7 | UOM | varchar | 50 | InvoiceDetail.UOM |
| 8 | Cost | varchar | 50 | InvoiceDetail.Cost (formatted) |
| 9 | UnitPrice | varchar | 50 | InvoiceDetail.Price (formatted) |
| 10 | LineTotal | decimal | | Calculated: Qty × Price |
| 11 | CustomerNumber | varchar | 50 | Joined from InvoiceHeader |
| 12 | CustomerName | varchar | 500 | Joined from InvoiceHeader |
| 13 | OrderNumber | varchar | 50 | Joined from InvoiceHeader |
| 14 | InvoiceDate | varchar | 50 | Joined from InvoiceHeader |
| 15 | PONumber | varchar | MAX | Joined from InvoiceHeader |
| 16 | Salesman | varchar | 100 | Joined from InvoiceHeader |
| 17 | Warehouse | varchar | 50 | Joined from InvoiceHeader |

**Usage:** Line items grid in credit form
```sql
SELECT * FROM vw_InvoiceLineItems
WHERE InvoiceNumber = 'INV-2024-001'
ORDER BY ItemNumber
```

**CRITICAL:** `UOM` column must be returned exactly as stored - no case modification.

---

### dbo.vw_SalesmanLookup
Distinct salesman list.

| # | Column | Type | Size | Source |
|---|--------|------|------|--------|
| 1 | SalesmanID | varchar | 100 | InvoiceHeader.Salesman |

**Usage:** Salesman validation/dropdown
```sql
SELECT DISTINCT SalesmanID FROM vw_SalesmanLookup
WHERE SalesmanID IS NOT NULL
ORDER BY SalesmanID
```

---

## Relationships

```
┌─────────────────┐       ┌─────────────────┐
│ InvoiceHeader   │───────│ InvoiceDetail   │
│ (InvoiceNo PK)  │ 1───M │ (InvoiceNo FK)  │
└─────────────────┘       └─────────────────┘
         │
         │ (lookup)
         ▼
┌─────────────────┐       ┌─────────────────────┐
│ CreditRequests  │───────│ CreditRequestItems  │
│ (RequestID PK)  │ 1───M │ (RequestID FK)      │
│ (InvoiceNo ref) │       │ (InvoiceNo ref)     │
└─────────────────┘       └─────────────────────┘
```

---

## API Field Mapping

### Read Path (Views → API)

| View Column | API Response Field |
|-------------|-------------------|
| `vw_UniqueCustomers.CustomerNumber` | `CustomerNumber` |
| `vw_UniqueCustomers.CustomerName` | `CustomerName` |
| `vw_UniqueCustomers.SalesmanID` | `SalesmanID` |
| `vw_CustomerInvoices.InvoiceNumber` | `InvoiceNumber` |
| `vw_CustomerInvoices.InvoiceDate` | `InvoiceDate` |
| `vw_CustomerInvoices.PONumber` | `PONumber` |
| `vw_InvoiceLineItems.ItemNumber` | `ItemNumber` |
| `vw_InvoiceLineItems.ItemDescription` | `ItemDescription` |
| `vw_InvoiceLineItems.UOM` | `UOM` ⚠️ EXACT |
| `vw_InvoiceLineItems.UnitPrice` | `UnitPrice` |
| `vw_InvoiceLineItems.Quantity` | `Quantity` |
| `vw_InvoiceLineItems.LineTotal` | `LineTotal` |

### Write Path (API → Tables)

| API Request Field | Table.Column |
|-------------------|--------------|
| `CustomerNumber` | `CreditRequests.CustomerNo` |
| `InvoiceNumber` | `CreditRequests.InvoiceNo` |
| `SalesmanID` | `CreditRequests.SalesmanID` |
| `TotalCredit` | `CreditRequests.TotalCredit` |
| `Notes` | `CreditRequests.Notes` |
| `ItemNumber` | `CreditRequestItems.ItemNo` |
| `ItemDescription` | `CreditRequestItems.Description` |
| `CreditQuantity` | `CreditRequestItems.Qty` |
| `CreditAmount` | `CreditRequestItems.CreditAmount` |
| `Reason` | `CreditRequestItems.Reason` ⚠️ EXACT |

---

## Connection

```python
import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=BID1;"
    "DATABASE=CreditManagement;"
    "Trusted_Connection=yes;"
)

conn = pyodbc.connect(conn_str)
```

**Requirements:**
- Must be on Driscoll network
- Windows Authentication (domain account)
- ODBC Driver 17 for SQL Server installed

---

## Notes

1. **Staging tables** (`stg_Header`, `stg_Detail`) are varchar for all numeric fields - used for raw imports before type conversion
2. **Views return varchar** for some numeric fields (Quantity, UnitPrice, etc.) - parse in application code
3. **UOM and Reason are case-sensitive** - must match exactly for credit processing
4. **InvoiceDate in views** may be formatted string, not date type

---

**END OF SCHEMA**
