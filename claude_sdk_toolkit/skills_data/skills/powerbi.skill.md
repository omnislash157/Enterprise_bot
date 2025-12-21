# Skill: Power BI Integration (powerbi)

## Overview
Push datasets to Power BI, generate DAX measures, create data models optimized for reporting.

## Capabilities

### Dataset Operations
- Push datasets via REST API
- Refresh existing datasets
- Create/update tables
- Define relationships

### DAX Generation
- Common measures (SUM, COUNT, AVERAGE)
- Time intelligence (YTD, MTD, YoY)
- Calculated columns
- KPI definitions

### Data Modeling
- Star schema design
- Fact/dimension identification
- Relationship mapping
- Hierarchy definition

## Power BI REST API

### Authentication
```python
import msal

# App registration required in Azure AD
CLIENT_ID = os.getenv("POWERBI_CLIENT_ID")
CLIENT_SECRET = os.getenv("POWERBI_CLIENT_SECRET")
TENANT_ID = os.getenv("POWERBI_TENANT_ID")

def get_powerbi_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(
        scopes=["https://analysis.windows.net/powerbi/api/.default"]
    )
    return result["access_token"]
```

### Push Dataset
```python
import requests

def push_dataset(workspace_id, dataset_name, tables):
    token = get_powerbi_token()
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"

    headers = {"Authorization": f"Bearer {token}"}

    # Define dataset schema
    dataset = {
        "name": dataset_name,
        "defaultMode": "Push",
        "tables": tables
    }

    response = requests.post(url, headers=headers, json=dataset)
    return response.json()
```

### Table Schema Definition
```python
tables = [
    {
        "name": "Sales",
        "columns": [
            {"name": "SaleID", "dataType": "Int64"},
            {"name": "Date", "dataType": "DateTime"},
            {"name": "Amount", "dataType": "Double"},
            {"name": "CustomerID", "dataType": "Int64"}
        ]
    },
    {
        "name": "Customers",
        "columns": [
            {"name": "CustomerID", "dataType": "Int64"},
            {"name": "Name", "dataType": "String"},
            {"name": "Region", "dataType": "String"}
        ]
    }
]
```

### Push Rows
```python
def push_rows(workspace_id, dataset_id, table_name, rows):
    token = get_powerbi_token()
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/tables/{table_name}/rows"

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(url, headers=headers, json={"rows": rows})
    return response.status_code == 200
```

## DAX Templates

### Basic Measures
```dax
// Total Sales
Total Sales = SUM(Sales[Amount])

// Order Count
Order Count = COUNTROWS(Sales)

// Average Order Value
Avg Order Value = DIVIDE([Total Sales], [Order Count])
```

### Time Intelligence
```dax
// Year to Date
Sales YTD = TOTALYTD([Total Sales], 'Date'[Date])

// Month to Date
Sales MTD = TOTALMTD([Total Sales], 'Date'[Date])

// Year over Year
Sales YoY =
VAR CurrentYear = [Total Sales]
VAR PreviousYear = CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Date'[Date]))
RETURN DIVIDE(CurrentYear - PreviousYear, PreviousYear)

// Rolling 12 Months
Sales R12M = CALCULATE([Total Sales], DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -12, MONTH))
```

### Calculated Columns
```dax
// Profit Margin
Profit Margin = DIVIDE(Sales[Profit], Sales[Revenue])

// Customer Segment
Customer Segment =
SWITCH(
    TRUE(),
    Customers[TotalPurchases] > 10000, "Platinum",
    Customers[TotalPurchases] > 5000, "Gold",
    Customers[TotalPurchases] > 1000, "Silver",
    "Bronze"
)
```

## CLI Commands (Planned)

```
/powerbi connect                     Authenticate with Power BI
/powerbi workspaces                  List workspaces
/powerbi datasets <workspace>        List datasets
/powerbi push <table> <workspace>    Push table to Power BI
/powerbi refresh <dataset>           Refresh dataset
/powerbi dax <measure_type>          Generate DAX template
```

## Star Schema Generation

```python
def generate_star_schema(fact_table, dimension_tables):
    """Generate Power BI-optimized star schema."""
    schema = {
        "tables": [],
        "relationships": []
    }

    # Fact table
    schema["tables"].append({
        "name": f"Fact_{fact_table}",
        "columns": get_fact_columns(fact_table)
    })

    # Dimension tables
    for dim in dimension_tables:
        schema["tables"].append({
            "name": f"Dim_{dim['name']}",
            "columns": get_dim_columns(dim)
        })
        schema["relationships"].append({
            "from": f"Fact_{fact_table}.{dim['key']}",
            "to": f"Dim_{dim['name']}.{dim['key']}"
        })

    return schema
```

## Dependencies

```bash
pip install msal requests pandas
```

## Environment Variables

```
POWERBI_CLIENT_ID=your_app_client_id
POWERBI_CLIENT_SECRET=your_app_secret
POWERBI_TENANT_ID=your_azure_tenant_id
POWERBI_WORKSPACE_ID=target_workspace_id
```

## Best Practices

1. **Incremental Refresh** - Push only changed data
2. **Data Types** - Match Power BI types exactly
3. **Relationships** - Define in dataset, not in Power BI Desktop
4. **Row Limits** - Push API has 10,000 row limit per call
5. **Rate Limits** - Max 120 requests/minute per dataset
