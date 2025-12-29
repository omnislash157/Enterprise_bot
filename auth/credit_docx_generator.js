/**
 * Credit Request DOCX Generator
 *
 * CRITICAL: Field names must match CreditManagement database exactly.
 * UOM and Reason codes are case-sensitive - do not modify.
 *
 * Usage: node credit_docx_generator.js <input_json> <output_docx>
 */

const fs = require('fs');
const {
    Document,
    Packer,
    Paragraph,
    TextRun,
    Table,
    TableRow,
    TableCell,
    AlignmentType,
    BorderStyle,
    WidthType,
    ShadingType,
    Header,
    Footer,
    PageNumber,
    HeadingLevel,
} = require('docx');

// Read command line args
const inputFile = process.argv[2];
const outputFile = process.argv[3];

if (!inputFile || !outputFile) {
    console.error('Usage: node credit_docx_generator.js <input_json> <output_docx>');
    process.exit(1);
}

// Read request data - field names match CreditManagement schema
const data = JSON.parse(fs.readFileSync(inputFile, 'utf8'));

// Colors - CogTwin theme
const COLORS = {
    primary: '1E3A5F',
    secondary: '3B82F6',
    accent: '10B981',
    text: '1F2937',
    muted: '6B7280',
    light: 'F3F4F6',
    border: 'D1D5DB',
    white: 'FFFFFF',
};

// Table border style
const tableBorder = { style: BorderStyle.SINGLE, size: 1, color: COLORS.border };
const cellBorders = { top: tableBorder, bottom: tableBorder, left: tableBorder, right: tableBorder };

// Generate current date
const now = new Date();
const dateStr = now.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
});

// Request number
const requestNumber = data.RequestNumber || `CR-${now.getTime().toString(36).toUpperCase()}`;

// Build line items table rows - using EXACT field names from schema
const lineItemRows = data.LineItems.map((item) => {
    return new TableRow({
        children: [
            // ItemNumber - from vw_InvoiceLineItems.ItemNumber
            new TableCell({
                borders: cellBorders,
                width: { size: 1200, type: WidthType.DXA },
                children: [new Paragraph({
                    children: [new TextRun({ text: String(item.ItemNumber || ''), size: 20 })]
                })]
            }),
            // ItemDescription - from vw_InvoiceLineItems.ItemDescription
            new TableCell({
                borders: cellBorders,
                width: { size: 3200, type: WidthType.DXA },
                children: [new Paragraph({
                    children: [new TextRun({ text: String(item.ItemDescription || ''), size: 20 })]
                })]
            }),
            // CreditQuantity - user input (maps to CreditRequestItems.Qty)
            new TableCell({
                borders: cellBorders,
                width: { size: 700, type: WidthType.DXA },
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [new TextRun({ text: String(item.CreditQuantity || 0), size: 20 })]
                })]
            }),
            // UOM - EXACT from vw_InvoiceLineItems.UOM - DO NOT MODIFY CASE
            new TableCell({
                borders: cellBorders,
                width: { size: 700, type: WidthType.DXA },
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [new TextRun({ text: String(item.UOM || ''), size: 20 })]
                })]
            }),
            // Reason - EXACT code (maps to CreditRequestItems.Reason)
            new TableCell({
                borders: cellBorders,
                width: { size: 1700, type: WidthType.DXA },
                children: [new Paragraph({
                    children: [new TextRun({ text: String(item.Reason || ''), size: 20 })]
                })]
            }),
            // CreditAmount - user input (maps to CreditRequestItems.CreditAmount)
            new TableCell({
                borders: cellBorders,
                width: { size: 1100, type: WidthType.DXA },
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({
                        text: `$${(item.CreditAmount || 0).toFixed(2)}`,
                        size: 20,
                        bold: true
                    })]
                })]
            }),
        ]
    });
});

// Create the document
const doc = new Document({
    styles: {
        default: {
            document: {
                run: { font: 'Arial', size: 22 }
            }
        },
        paragraphStyles: [
            {
                id: 'Title',
                name: 'Title',
                basedOn: 'Normal',
                run: { size: 48, bold: true, color: COLORS.primary, font: 'Arial' },
                paragraph: { spacing: { after: 200 }, alignment: AlignmentType.CENTER }
            },
            {
                id: 'Heading1',
                name: 'Heading 1',
                basedOn: 'Normal',
                run: { size: 28, bold: true, color: COLORS.primary, font: 'Arial' },
                paragraph: { spacing: { before: 300, after: 120 } }
            },
            {
                id: 'Subtitle',
                name: 'Subtitle',
                basedOn: 'Normal',
                run: { size: 24, color: COLORS.muted, font: 'Arial' },
                paragraph: { spacing: { after: 400 }, alignment: AlignmentType.CENTER }
            }
        ]
    },
    sections: [{
        properties: {
            page: {
                margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
            }
        },
        headers: {
            default: new Header({
                children: [
                    new Paragraph({
                        alignment: AlignmentType.RIGHT,
                        children: [
                            new TextRun({ text: 'DRISCOLL FOODS', bold: true, size: 18, color: COLORS.muted }),
                            new TextRun({ text: '  |  Credit Request', size: 18, color: COLORS.muted })
                        ]
                    })
                ]
            })
        },
        footers: {
            default: new Footer({
                children: [
                    new Paragraph({
                        alignment: AlignmentType.CENTER,
                        children: [
                            new TextRun({ text: 'Page ', size: 18, color: COLORS.muted }),
                            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: COLORS.muted }),
                            new TextRun({ text: ' of ', size: 18, color: COLORS.muted }),
                            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: COLORS.muted }),
                            new TextRun({ text: '  |  Generated by CogTwin', size: 18, color: COLORS.muted })
                        ]
                    })
                ]
            })
        },
        children: [
            // Title
            new Paragraph({
                heading: HeadingLevel.TITLE,
                children: [new TextRun({ text: 'CREDIT REQUEST', bold: true })]
            }),

            // Subtitle
            new Paragraph({
                style: 'Subtitle',
                children: [
                    new TextRun({ text: requestNumber, bold: true }),
                    new TextRun({ text: `  |  ${dateStr}` })
                ]
            }),

            // Request Details Section
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: 'Request Details' })]
            }),

            // Info table - using EXACT field names from schema
            new Table({
                columnWidths: [2500, 6500],
                rows: [
                    // CustomerNumber / CustomerName - from vw_UniqueCustomers
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 2500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'Customer', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 6500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [
                                        new TextRun({ text: data.CustomerName || '', size: 22 }),
                                        new TextRun({ text: ` (#${data.CustomerNumber || ''})`, size: 22, color: COLORS.muted })
                                    ]
                                })]
                            })
                        ]
                    }),
                    // InvoiceNumber / InvoiceDate - from vw_CustomerInvoices
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 2500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'Invoice', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 6500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [
                                        new TextRun({ text: data.InvoiceNumber || '', size: 22 }),
                                        new TextRun({ text: ` (${data.InvoiceDate || ''})`, size: 22, color: COLORS.muted })
                                    ]
                                })]
                            })
                        ]
                    }),
                    // PONumber - from vw_CustomerInvoices.PONumber
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 2500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'PO Number', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 6500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: data.PONumber || 'N/A', size: 22 })]
                                })]
                            })
                        ]
                    }),
                    // SalesmanID - from vw_CustomerInvoices.SalesmanID
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 2500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'Salesman', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 6500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: data.SalesmanID || '', size: 22 })]
                                })]
                            })
                        ]
                    }),
                    // Submitted By
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 2500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'Submitted By', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 6500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [
                                        new TextRun({ text: data.SubmittedBy || '', size: 22 }),
                                        new TextRun({ text: ` (${data.SubmittedByEmail || ''})`, size: 22, color: COLORS.muted })
                                    ]
                                })]
                            })
                        ]
                    }),
                    // DSM
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 2500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'DSM', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 6500, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [
                                        new TextRun({ text: data.DSMName || '', size: 22 }),
                                        new TextRun({ text: ` (${data.DSMEmail || ''})`, size: 22, color: COLORS.muted })
                                    ]
                                })]
                            })
                        ]
                    }),
                ]
            }),

            // Spacer
            new Paragraph({ children: [] }),

            // Line Items Section
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: 'Credit Line Items' })]
            }),

            // Line items table - columns match CreditRequestItems schema
            new Table({
                columnWidths: [1200, 3200, 700, 700, 1700, 1100],
                rows: [
                    // Header row
                    new TableRow({
                        tableHeader: true,
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.primary, type: ShadingType.CLEAR },
                                width: { size: 1200, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'ItemNo', bold: true, size: 20, color: COLORS.white })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.primary, type: ShadingType.CLEAR },
                                width: { size: 3200, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'Description', bold: true, size: 20, color: COLORS.white })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.primary, type: ShadingType.CLEAR },
                                width: { size: 700, type: WidthType.DXA },
                                children: [new Paragraph({
                                    alignment: AlignmentType.CENTER,
                                    children: [new TextRun({ text: 'Qty', bold: true, size: 20, color: COLORS.white })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.primary, type: ShadingType.CLEAR },
                                width: { size: 700, type: WidthType.DXA },
                                children: [new Paragraph({
                                    alignment: AlignmentType.CENTER,
                                    children: [new TextRun({ text: 'UOM', bold: true, size: 20, color: COLORS.white })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.primary, type: ShadingType.CLEAR },
                                width: { size: 1700, type: WidthType.DXA },
                                children: [new Paragraph({
                                    children: [new TextRun({ text: 'Reason', bold: true, size: 20, color: COLORS.white })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.primary, type: ShadingType.CLEAR },
                                width: { size: 1100, type: WidthType.DXA },
                                children: [new Paragraph({
                                    alignment: AlignmentType.RIGHT,
                                    children: [new TextRun({ text: 'Amount', bold: true, size: 20, color: COLORS.white })]
                                })]
                            }),
                        ]
                    }),
                    // Line item rows
                    ...lineItemRows,
                    // Total row - TotalCredit maps to CreditRequests.TotalCredit
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                columnSpan: 5,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                children: [new Paragraph({
                                    alignment: AlignmentType.RIGHT,
                                    children: [new TextRun({ text: 'TOTAL CREDIT:', bold: true, size: 22 })]
                                })]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                children: [new Paragraph({
                                    alignment: AlignmentType.RIGHT,
                                    children: [new TextRun({
                                        text: `$${(data.TotalCredit || 0).toFixed(2)}`,
                                        bold: true,
                                        size: 24,
                                        color: COLORS.primary
                                    })]
                                })]
                            }),
                        ]
                    }),
                ]
            }),

            // Notes section - maps to CreditRequests.Notes
            ...(data.Notes ? [
                new Paragraph({ children: [] }),
                new Paragraph({
                    heading: HeadingLevel.HEADING_1,
                    children: [new TextRun({ text: 'Notes' })]
                }),
                new Paragraph({
                    children: [new TextRun({ text: data.Notes, size: 22 })]
                })
            ] : []),

            // Spacer
            new Paragraph({ children: [] }),
            new Paragraph({ children: [] }),

            // Approval section
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun({ text: 'Approvals' })]
            }),

            new Table({
                columnWidths: [3000, 3000, 3000],
                rows: [
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 3000, type: WidthType.DXA },
                                children: [
                                    new Paragraph({
                                        alignment: AlignmentType.CENTER,
                                        children: [new TextRun({ text: 'DSM Approval', bold: true, size: 20 })]
                                    })
                                ]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 3000, type: WidthType.DXA },
                                children: [
                                    new Paragraph({
                                        alignment: AlignmentType.CENTER,
                                        children: [new TextRun({ text: 'Revenue Approval', bold: true, size: 20 })]
                                    })
                                ]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                shading: { fill: COLORS.light, type: ShadingType.CLEAR },
                                width: { size: 3000, type: WidthType.DXA },
                                children: [
                                    new Paragraph({
                                        alignment: AlignmentType.CENTER,
                                        children: [new TextRun({ text: 'Credit Processing', bold: true, size: 20 })]
                                    })
                                ]
                            }),
                        ]
                    }),
                    new TableRow({
                        children: [
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 3000, type: WidthType.DXA },
                                children: [
                                    new Paragraph({ children: [] }),
                                    new Paragraph({ children: [] }),
                                    new Paragraph({
                                        children: [new TextRun({ text: '________________________', size: 20 })]
                                    }),
                                    new Paragraph({
                                        alignment: AlignmentType.CENTER,
                                        children: [new TextRun({ text: 'Signature / Date', size: 18, color: COLORS.muted })]
                                    })
                                ]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 3000, type: WidthType.DXA },
                                children: [
                                    new Paragraph({ children: [] }),
                                    new Paragraph({ children: [] }),
                                    new Paragraph({
                                        children: [new TextRun({ text: '________________________', size: 20 })]
                                    }),
                                    new Paragraph({
                                        alignment: AlignmentType.CENTER,
                                        children: [new TextRun({ text: 'Signature / Date', size: 18, color: COLORS.muted })]
                                    })
                                ]
                            }),
                            new TableCell({
                                borders: cellBorders,
                                width: { size: 3000, type: WidthType.DXA },
                                children: [
                                    new Paragraph({ children: [] }),
                                    new Paragraph({ children: [] }),
                                    new Paragraph({
                                        children: [new TextRun({ text: '________________________', size: 20 })]
                                    }),
                                    new Paragraph({
                                        alignment: AlignmentType.CENTER,
                                        children: [new TextRun({ text: 'Completed / Date', size: 18, color: COLORS.muted })]
                                    })
                                ]
                            }),
                        ]
                    }),
                ]
            }),
        ]
    }]
});

// Generate and save
Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputFile, buffer);
    console.log(`Generated: ${outputFile}`);
}).catch(err => {
    console.error('Error generating DOCX:', err);
    process.exit(1);
});
