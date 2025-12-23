# T2: Railway - Deployment Management

## Overview
Railway GraphQL API for managing deployments, services, logs, and environment variables.

---

## 🔑 Authentication

```python
import os
import httpx

RAILWAY_API = "https://backboard.railway.app/graphql/v2"

def get_headers():
    token = os.getenv("RAILWAY_TOKEN")
    if not token:
        raise ValueError("RAILWAY_TOKEN not set")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

def graphql_query(query: str, variables: dict = None):
    response = httpx.post(
        RAILWAY_API,
        headers=get_headers(),
        json={"query": query, "variables": variables or {}},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()
```

---

## 📋 List Services

```python
query = """
    query ($projectId: String!) {
        project(id: $projectId) {
            name
            services {
                edges {
                    node {
                        id
                        name
                        icon
                        updatedAt
                    }
                }
            }
            environments {
                edges {
                    node {
                        id
                        name
                    }
                }
            }
        }
    }
"""

result = graphql_query(query, {"projectId": PROJECT_ID})
services = result["data"]["project"]["services"]["edges"]
```

---

## 📊 Get Deployment Status

```python
query = """
    query ($serviceId: String!) {
        service(id: $serviceId) {
            id
            name
            deployments(first: 3) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        meta
                    }
                }
            }
        }
    }
"""

result = graphql_query(query, {"serviceId": SERVICE_ID})
deployments = result["data"]["service"]["deployments"]["edges"]

# Status values: BUILDING, DEPLOYING, SUCCESS, FAILED, CRASHED
current_status = deployments[0]["node"]["status"] if deployments else "unknown"
```

---

## 📝 Get Logs

**Note**: Railway logs require deployment ID (not service ID)

```python
# Step 1: Get latest deployment
deploy_query = """
    query ($serviceId: String!) {
        service(id: $serviceId) {
            deployments(first: 1) {
                edges {
                    node {
                        id
                        status
                    }
                }
            }
        }
    }
"""

deploy_result = graphql_query(deploy_query, {"serviceId": SERVICE_ID})
deployment_id = deploy_result["data"]["service"]["deployments"]["edges"][0]["node"]["id"]

# Step 2: Get logs for deployment
logs_query = """
    query ($deploymentId: String!, $limit: Int!) {
        deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
            timestamp
            message
            severity
        }
    }
"""

logs_result = graphql_query(logs_query, {"deploymentId": deployment_id, "limit": 100})
logs = logs_result["data"]["deploymentLogs"]
```

---

## 🔄 Trigger Redeploy

```python
mutation = """
    mutation ($serviceId: String!, $environmentId: String!) {
        serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
    }
"""

# Get production environment ID first
# Then trigger redeploy
result = graphql_query(mutation, {
    "serviceId": SERVICE_ID,
    "environmentId": ENV_ID  # Usually "production"
})
```

---

## ⚙️ Environment Variables

### Get Variables
```python
query = """
    query ($serviceId: String!) {
        service(id: $serviceId) {
            serviceInstances {
                edges {
                    node {
                        environmentId
                        variables
                    }
                }
            }
        }
    }
"""

result = graphql_query(query, {"serviceId": SERVICE_ID})
variables = result["data"]["service"]["serviceInstances"]["edges"][0]["node"]["variables"]

# Mask sensitive values
for key, value in variables.items():
    if any(secret in key.upper() for secret in ["PASSWORD", "SECRET", "TOKEN"]):
        print(f"{key}: {value[:4]}****{value[-4:]}")
```

### Set Variable
```python
mutation = """
    mutation ($serviceId: String!, $environmentId: String!, $variables: JSON!) {
        variableCollectionUpsert(
            input: {
                serviceId: $serviceId
                environmentId: $environmentId
                variables: $variables
            }
        )
    }
"""

result = graphql_query(mutation, {
    "serviceId": SERVICE_ID,
    "environmentId": ENV_ID,
    "variables": {"KEY_NAME": "value"}
})

# NOTE: Changes don't apply until redeploy!
```

---

## 🎯 Common Patterns

### Get Service ID by Name
```python
def get_service_id(project_id: str, service_name: str) -> str:
    """Find service ID from name."""
    services_result = graphql_query(LIST_SERVICES_QUERY, {"projectId": project_id})

    for edge in services_result["data"]["project"]["services"]["edges"]:
        if edge["node"]["name"].lower() == service_name.lower():
            return edge["node"]["id"]

    raise ValueError(f"Service '{service_name}' not found")
```

### Get Production Environment
```python
def get_prod_env(project_id: str) -> str:
    """Get production environment ID."""
    result = graphql_query(PROJECT_QUERY, {"projectId": project_id})

    for edge in result["data"]["project"]["environments"]["edges"]:
        if edge["node"]["name"].lower() == "production":
            return edge["node"]["id"]

    # Fallback to first environment
    return result["data"]["project"]["environments"]["edges"][0]["node"]["id"]
```

---

## 🚨 Error Handling

```python
try:
    result = graphql_query(query, variables)

    if "errors" in result:
        error_msg = result["errors"][0]["message"]
        return {"error": error_msg}

    # Process data
    data = result["data"]

except httpx.HTTPStatusError as e:
    return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
except Exception as e:
    return {"error": str(e)}
```

---

## 📖 GraphQL Schema Explorer

Use Railway's GraphiQL interface:
1. Go to https://railway.app
2. Open browser dev tools
3. Look for GraphQL endpoint in Network tab
4. Use token from Account Settings

Or explore schema:
```python
introspection_query = """
    query {
        __schema {
            types {
                name
                description
            }
        }
    }
"""
```

---

## 🔧 Environment Setup

```bash
# .env file
RAILWAY_TOKEN=rxxx-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
RAILWAY_PROJECT_ID=abc123de-f456-7890-abcd-ef1234567890
```

Get credentials:
1. Dashboard: https://railway.app → Account Settings → Tokens
2. Project ID: From project URL

---

## 🎯 SDK Tool Example

```python
from claude_agent_sdk import tool

@tool(
    name="railway_status",
    description="Get deployment status for a Railway service",
    input_schema={"service_name": str, "project_id": str}
)
async def railway_status(args: dict):
    service_name = args.get("service_name")
    project_id = args.get("project_id") or os.getenv("RAILWAY_PROJECT_ID")

    # Get service ID
    service_id = get_service_id(project_id, service_name)

    # Get deployments
    result = graphql_query(DEPLOYMENT_QUERY, {"serviceId": service_id})
    deployments = result["data"]["service"]["deployments"]["edges"]

    current = deployments[0]["node"] if deployments else None
    status_text = f"Service: {service_name}\n"
    status_text += f"Status: {current['status'] if current else 'unknown'}\n"
    status_text += f"Last deploy: {current['createdAt'] if current else 'never'}\n"

    return {
        "content": [{"type": "text", "text": status_text}]
    }
```

---

## 📊 Useful Queries

### List all projects
```graphql
query {
    projects {
        edges {
            node {
                id
                name
                description
            }
        }
    }
}
```

### Service metrics
```graphql
query ($serviceId: String!) {
    service(id: $serviceId) {
        id
        name
        deployments(first: 10) {
            edges {
                node {
                    status
                    createdAt
                }
            }
        }
    }
}
```

---

*Railway GraphQL API is powerful but undocumented. Explore via browser dev tools.*
