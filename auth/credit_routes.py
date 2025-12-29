"""
Credit Pipeline Routes

Location: auth/credit_routes.py

Endpoints:
- GET  /api/credit/customers      - Search customers (hits Driscoll DB)
- GET  /api/credit/invoices       - Get invoices for customer
- GET  /api/credit/lineitems      - Get line items for invoice
- GET  /api/credit/config         - Get DSM/Revenue dropdown options
- POST /api/credit/generate/unform - Generate Unform PDF (staging folder)
- POST /api/credit/generate/visual - Generate Visual DOCX (download)

The generate endpoints work independently of Driscoll DB - they just
take the form data and produce documents.

Wire into main.py:
    from auth.credit_routes import router as credit_router
    app.include_router(credit_router)
"""

import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Internal imports (when in auth/ folder)
from core.config_loader import cfg

router = APIRouter(prefix="/api/credit", tags=["credit"])


# =============================================================================
# MODELS
# =============================================================================


class LineItemRequest(BaseModel):
    itemNumber: str
    description: str
    quantity: int
    uom: str
    unitPrice: float
    extendedPrice: float
    creditQuantity: int
    creditUOM: str
    creditReason: str
    creditAmount: float
    isPartialCredit: bool = False
    partialExplanation: str = ""


class CreditGenerateRequest(BaseModel):
    """Request body for generating credit documents"""

    requestNumber: Optional[str] = None  # Auto-generated if not provided
    customerNumber: str
    customerName: str
    invoiceNumber: str
    invoiceDate: str
    poNumber: Optional[str] = None
    lineItems: list[LineItemRequest]
    totalAmount: float
    notes: str = ""
    submittedBy: str
    submittedByEmail: str
    dsmName: str
    dsmEmail: str


class ConfigPerson(BaseModel):
    email: str
    name: str
    role: str  # 'dsm', 'revenue', 'credit'


# =============================================================================
# CONFIG - DSM/Revenue/Credit people (hardcoded for now, can move to DB)
# =============================================================================

CREDIT_CONFIG: list[ConfigPerson] = [
    # DSMs
    ConfigPerson(email="john.smith@driscoll.com", name="John Smith", role="dsm"),
    ConfigPerson(email="jane.doe@driscoll.com", name="Jane Doe", role="dsm"),
    ConfigPerson(email="mike.wilson@driscoll.com", name="Mike Wilson", role="dsm"),
    # Revenue
    ConfigPerson(email="revenue1@driscoll.com", name="Revenue Team 1", role="revenue"),
    ConfigPerson(email="revenue2@driscoll.com", name="Revenue Team 2", role="revenue"),
    # Credit Admin
    ConfigPerson(email="credit.admin@driscoll.com", name="Credit Admin", role="credit"),
]

# Staging folder for Unform PDFs
UNFORM_STAGING_PATH = Path(cfg("credit.unform_staging_path", "/tmp/unform_staging"))


# =============================================================================
# DRISCOLL DB CONNECTION (Wire up on Driscoll laptop)
# =============================================================================


def get_driscoll_cursor():
    """
    Get a cursor to Driscoll SQL Server.

    Uses Windows Authentication - only works on Driscoll network.

    TODO: Replace SERVER and DATABASE with actual values from BID1
    """
    import pyodbc

    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=BID1;"  # TODO: Confirm server name
        "DATABASE=DriscollERP;"  # TODO: Confirm database name
        "Trusted_Connection=yes;"
    )

    conn = pyodbc.connect(conn_str)
    return conn.cursor()


# =============================================================================
# CONFIG ENDPOINT
# =============================================================================


@router.get("/config")
async def get_credit_config():
    """Get DSM/Revenue dropdown options"""
    return {
        "dsm": [p.model_dump() for p in CREDIT_CONFIG if p.role == "dsm"],
        "revenue": [p.model_dump() for p in CREDIT_CONFIG if p.role == "revenue"],
        "credit": [p.model_dump() for p in CREDIT_CONFIG if p.role == "credit"],
    }


# =============================================================================
# DRISCOLL DB ENDPOINTS (stubs - wire up with pyodbc tomorrow)
# =============================================================================


@router.get("/customers")
async def search_customers(search: str = Query(..., min_length=2)):
    """
    Search customers by name or number.

    TODO: Wire to Driscoll DB via pyodbc + Windows Auth
    """
    # STUB - replace with actual DB query
    return {
        "customers": [
            {
                "customerNumber": "12345",
                "customerName": f"ACME Foods (matched: {search})",
                "displayText": f"ACME Foods (#12345)",
            },
            {
                "customerNumber": "67890",
                "customerName": f"Beta Corp (matched: {search})",
                "displayText": f"Beta Corp (#67890)",
            },
        ]
    }


@router.get("/invoices")
async def get_customer_invoices(customer_id: str = Query(...)):
    """
    Get invoices for a customer.

    TODO: Wire to Driscoll DB
    """
    # STUB
    return {
        "invoices": [
            {
                "invoiceNumber": "INV-2024-001",
                "invoiceDate": "2024-12-15",
                "poNumber": "PO-8765",
                "customerId": customer_id,
                "totalAmount": 1250.00,
                "displayText": "INV-2024-001 | 2024-12-15 | PO: PO-8765",
            },
            {
                "invoiceNumber": "INV-2024-002",
                "invoiceDate": "2024-12-20",
                "poNumber": None,
                "customerId": customer_id,
                "totalAmount": 875.50,
                "displayText": "INV-2024-002 | 2024-12-20 | No PO",
            },
        ]
    }


@router.get("/lineitems")
async def get_invoice_lineitems(invoice_id: str = Query(...)):
    """
    Get line items for an invoice.

    TODO: Wire to Driscoll DB
    """
    # STUB
    return {
        "lineItems": [
            {
                "lineItemId": f"{invoice_id}-001",
                "invoiceId": invoice_id,
                "itemNumber": "SKU-001",
                "description": "Organic Apples - Case of 40",
                "quantity": 10,
                "uom": "CS",
                "unitPrice": 45.00,
                "extendedPrice": 450.00,
                "invoiceKey": f"{invoice_id}|SKU-001",
            },
            {
                "lineItemId": f"{invoice_id}-002",
                "invoiceId": invoice_id,
                "itemNumber": "SKU-002",
                "description": "Bananas - Case of 50",
                "quantity": 5,
                "uom": "CS",
                "unitPrice": 32.00,
                "extendedPrice": 160.00,
                "invoiceKey": f"{invoice_id}|SKU-002",
            },
        ]
    }


# =============================================================================
# DOCUMENT GENERATION
# =============================================================================


def generate_request_number() -> str:
    """Generate a unique credit request number"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_suffix = secrets.token_hex(3).upper()
    return f"CR-{timestamp}-{random_suffix}"


@router.post("/generate/unform")
async def generate_unform_pdf(request: CreditGenerateRequest):
    """
    Generate PDF with fixed bounding boxes for Unform processing.

    Saves to staging folder and returns the path.
    Unform will pick this up and process it.
    """
    request_number = request.requestNumber or generate_request_number()

    # Ensure staging directory exists
    UNFORM_STAGING_PATH.mkdir(parents=True, exist_ok=True)

    # Generate filename
    filename = f"{request_number}.pdf"
    filepath = UNFORM_STAGING_PATH / filename

    # Create PDF with reportlab
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    # ==========================================================
    # UNFORM BOUNDING BOX COORDINATES
    # Adjust these X,Y values to match your Unform template
    # Y coordinates are from BOTTOM of page in reportlab
    # ==========================================================

    # Header section
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 50, "CREDIT REQUEST")

    c.setFont("Helvetica", 10)

    # Request number - BOX 1
    c.drawString(450, height - 50, f"Request #: {request_number}")

    # Date - BOX 2
    c.drawString(450, height - 65, f"Date: {datetime.now().strftime('%m/%d/%Y')}")

    # Customer info section
    # Customer Number - BOX 3
    c.drawString(50, height - 100, f"Customer #: {request.customerNumber}")

    # Customer Name - BOX 4
    c.drawString(200, height - 100, f"Name: {request.customerName}")

    # Invoice info
    # Invoice Number - BOX 5
    c.drawString(50, height - 120, f"Invoice #: {request.invoiceNumber}")

    # Invoice Date - BOX 6
    c.drawString(200, height - 120, f"Invoice Date: {request.invoiceDate}")

    # PO Number - BOX 7
    po_display = request.poNumber or "N/A"
    c.drawString(350, height - 120, f"PO #: {po_display}")

    # Line items header
    y_pos = height - 160
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y_pos, "Item #")
    c.drawString(100, y_pos, "Description")
    c.drawString(300, y_pos, "Qty")
    c.drawString(340, y_pos, "UOM")
    c.drawString(380, y_pos, "Reason")
    c.drawString(450, y_pos, "Amount")

    # Line items - BOX 8 (repeating)
    c.setFont("Helvetica", 9)
    y_pos -= 20

    for item in request.lineItems:
        if y_pos < 100:  # New page if needed
            c.showPage()
            y_pos = height - 50

        c.drawString(50, y_pos, item.itemNumber[:10])
        c.drawString(100, y_pos, item.description[:35])
        c.drawString(300, y_pos, str(item.creditQuantity))
        c.drawString(340, y_pos, item.creditUOM)
        c.drawString(380, y_pos, item.creditReason)
        c.drawString(450, y_pos, f"${item.creditAmount:.2f}")

        y_pos -= 15

    # Total - BOX 9
    y_pos -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(380, y_pos, "TOTAL:")
    c.drawString(450, y_pos, f"${request.totalAmount:.2f}")

    # Notes - BOX 10
    if request.notes:
        y_pos -= 30
        c.setFont("Helvetica", 9)
        c.drawString(50, y_pos, f"Notes: {request.notes[:200]}")

    # Submitter info - BOX 11
    y_pos -= 30
    c.drawString(50, y_pos, f"Submitted by: {request.submittedBy}")
    c.drawString(250, y_pos, f"Email: {request.submittedByEmail}")

    # DSM - BOX 12
    y_pos -= 15
    c.drawString(50, y_pos, f"DSM: {request.dsmName}")
    c.drawString(250, y_pos, f"Email: {request.dsmEmail}")

    c.save()

    return {
        "success": True,
        "requestNumber": request_number,
        "filename": filename,
        "filepath": str(filepath),
        "message": f"PDF saved to Unform staging: {filepath}",
    }


@router.post("/generate/visual")
async def generate_visual_docx(request: CreditGenerateRequest):
    """
    Generate a styled DOCX document for email/review.

    Uses Node.js docx library via subprocess.
    Returns the file for download.
    """
    import json
    import subprocess
    import tempfile

    request_number = request.requestNumber or generate_request_number()

    # Create temp directory for the operation
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write request data to JSON for the Node script
        data_file = Path(tmpdir) / "request_data.json"
        output_file = Path(tmpdir) / f"{request_number}.docx"

        data_file.write_text(json.dumps(request.model_dump(), default=str))

        # Path to our docx generator script (in same folder as this file)
        script_path = Path(__file__).parent / "credit_docx_generator.js"

        if not script_path.exists():
            raise HTTPException(
                status_code=500,
                detail="DOCX generator script not found. Run setup first.",
            )

        # Run Node script
        result = subprocess.run(
            ["node", str(script_path), str(data_file), str(output_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"DOCX generation failed: {result.stderr}"
            )

        # Read the generated file
        docx_bytes = output_file.read_bytes()

    # Return as downloadable file
    from fastapi.responses import Response

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{request_number}.docx"'
        },
    )
