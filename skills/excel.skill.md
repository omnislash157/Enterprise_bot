# Skill: Excel Export (excel)

## Overview
Export database queries to formatted Excel files using openpyxl. Supports multiple sheets, styling, and formulas.

## Capabilities

- Multi-sheet workbooks
- Auto-column width
- Header styling (bold, colors)
- Number formatting (currency, dates, percentages)
- Conditional formatting
- Freeze panes
- Auto-filters
- Basic formulas (SUM, COUNT, AVERAGE)

## Python API

```python
from excel_tools import ExcelExporter

# Create exporter
excel = ExcelExporter("report.xlsx")

# Add sheets from queries
excel.add_sheet("Users", db.query("SELECT * FROM users"))
excel.add_sheet("Orders", db.query("SELECT * FROM orders"))

# Add sheet with styling
excel.add_sheet("Summary", data, style={
    "header_color": "#4472C4",
    "header_font_color": "#FFFFFF",
    "alternate_rows": True,
    "number_format": {"amount": "$#,##0.00", "date": "YYYY-MM-DD"}
})

# Save
excel.save()
```

## CLI Commands (Planned)

```
/db excel <table> <file.xlsx>           Export table to Excel
/db excel query "SELECT..." <file.xlsx> Export query to Excel
/db excel multi <file.xlsx>             Interactive multi-sheet export
```

## Styling Options

```python
style = {
    # Header
    "header_color": "#4472C4",      # Background color
    "header_font_color": "#FFFFFF", # Font color
    "header_bold": True,

    # Body
    "alternate_rows": True,         # Zebra striping
    "alternate_color": "#E7E6E6",

    # Column formats
    "number_format": {
        "price": "$#,##0.00",
        "date": "YYYY-MM-DD",
        "percent": "0.00%"
    },

    # Layout
    "freeze_panes": "A2",           # Freeze header row
    "auto_filter": True,
    "auto_width": True
}
```

## Multi-Sheet Reports

```python
excel = ExcelExporter("monthly_report.xlsx")

# Summary sheet
excel.add_sheet("Summary", [
    {"metric": "Total Users", "value": 1234},
    {"metric": "Active Orders", "value": 567},
    {"metric": "Revenue", "value": 89012.34}
], style={"number_format": {"value": "#,##0"}})

# Detail sheets
excel.add_sheet("Users", users_df)
excel.add_sheet("Orders", orders_df)
excel.add_sheet("Products", products_df)

excel.save()
```

## Formula Support

```python
# Add formulas to a sheet
excel.add_sheet("Sales", sales_data)
excel.add_formula("Sales", "E2", "=SUM(D:D)")  # Total
excel.add_formula("Sales", "E3", "=AVERAGE(D:D)")  # Average
excel.add_formula("Sales", "E4", "=COUNT(A:A)")  # Count
```

## Dependencies

```bash
pip install openpyxl pandas
```

## Integration with db_tools

```python
from db_tools import get_db
from excel_tools import ExcelExporter

db = get_db()

# Query and export
results = db.query("SELECT * FROM users")
excel = ExcelExporter("users.xlsx")
excel.add_sheet("Users", results)
excel.save()
```

## Template Reports

Pre-built report templates:
- `table_dump` - Simple table export
- `summary_detail` - Summary + detail sheets
- `dashboard` - KPIs with charts placeholder
- `audit` - Before/after comparison
