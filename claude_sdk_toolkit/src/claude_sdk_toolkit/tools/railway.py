"""
Railway Tools - SDK Compatible Wrappers

This module wraps the Railway GraphQL API functions with SDK-compatible async tools.
"""

import os
import json
from typing import Dict, Any
from claude_agent_sdk import tool

# HTTP client
try:
    import httpx
    HTTP_AVAILABLE = True
except ImportError:
    try:
        import requests as httpx
        HTTP_AVAILABLE = True
    except ImportError:
        HTTP_AVAILABLE = False


# =============================================================================
# GRAPHQL CLIENT
# =============================================================================

RAILWAY_API = "https://backboard.railway.app/graphql/v2"


def get_headers():
    """Get Railway API headers."""
    token = os.getenv("RAILWAY_TOKEN")
    if not token:
        raise ValueError("RAILWAY_TOKEN not set")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def graphql_query(query: str, variables: dict = None) -> dict:
    """Execute GraphQL query against Railway API."""
    if not HTTP_AVAILABLE:
        raise RuntimeError("httpx or requests required: pip install httpx")

    response = httpx.post(
        RAILWAY_API,
        headers=get_headers(),
        json={"query": query, "variables": variables or {}},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


# =============================================================================
# SDK TOOLS
# =============================================================================

@tool(
    name="railway_services",
    description="List all services in a Railway project with their IDs, names, and environments",
    input_schema={"project_id": str}
)
async def railway_services(args: dict) -> Dict[str, Any]:
    """List all services in a Railway project."""
    project_id = args.get("project_id") or os.getenv("RAILWAY_PROJECT_ID")

    if not project_id:
        return {
            "content": [{"type": "text", "text": "Error: No project_id provided and RAILWAY_PROJECT_ID environment variable not set"}],
            "isError": True
        }

    query = """
        query ($projectId: String!) {
            project(id: $projectId) {
                id
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

    try:
        result = graphql_query(query, {"projectId": project_id})

        if "errors" in result:
            return {
                "content": [{"type": "text", "text": f"Railway API Error: {result['errors'][0]['message']}"}],
                "isError": True
            }

        project = result.get("data", {}).get("project", {})

        services = [
            {
                "id": edge["node"]["id"],
                "name": edge["node"]["name"],
                "icon": edge["node"].get("icon"),
                "updated_at": edge["node"].get("updatedAt"),
            }
            for edge in project.get("services", {}).get("edges", [])
        ]

        environments = [
            {
                "id": edge["node"]["id"],
                "name": edge["node"]["name"],
            }
            for edge in project.get("environments", {}).get("edges", [])
        ]

        result_text = f"""Railway Project: {project.get('name')}
Project ID: {project_id}

Services ({len(services)}):
"""
        for svc in services:
            result_text += f"  • {svc['name']} (ID: {svc['id'][:12]}...)\n"

        result_text += f"\nEnvironments: {', '.join([e['name'] for e in environments])}"

        return {
            "content": [{"type": "text", "text": result_text}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error calling Railway API: {str(e)}"}],
            "isError": True
        }


@tool(
    name="railway_logs",
    description="Get recent logs from a Railway service deployment",
    input_schema={"service_name": str, "lines": int, "project_id": str}
)
async def railway_logs(args: dict) -> Dict[str, Any]:
    """Get recent logs from a Railway service."""
    service_name = args.get("service_name")
    lines = args.get("lines", 100)
    project_id = args.get("project_id") or os.getenv("RAILWAY_PROJECT_ID")

    if not project_id:
        return {
            "content": [{"type": "text", "text": "Error: No project_id provided and RAILWAY_PROJECT_ID not set"}],
            "isError": True
        }

    if not service_name:
        return {
            "content": [{"type": "text", "text": "Error: service_name is required"}],
            "isError": True
        }

    try:
        # First get service list to find service ID
        services_result = await railway_services({"project_id": project_id})

        # Parse service ID from result (this is hacky but works for now)
        # In production, we'd call the graphql directly

        return {
            "content": [{"type": "text", "text": f"Log retrieval for {service_name} - Feature in progress\n\nNote: Railway log API requires deployment ID which requires additional GraphQL queries. This tool is being enhanced."}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True
        }


@tool(
    name="railway_status",
    description="Get deployment status for a Railway service",
    input_schema={"service_name": str, "project_id": str}
)
async def railway_status(args: dict) -> Dict[str, Any]:
    """Get deployment status for a Railway service."""
    service_name = args.get("service_name")
    project_id = args.get("project_id") or os.getenv("RAILWAY_PROJECT_ID")

    if not project_id:
        return {
            "content": [{"type": "text", "text": "Error: No project_id provided and RAILWAY_PROJECT_ID not set"}],
            "isError": True
        }

    if not service_name:
        return {
            "content": [{"type": "text", "text": "Error: service_name is required"}],
            "isError": True
        }

    return {
        "content": [{"type": "text", "text": f"Status check for {service_name} - Feature in progress"}]
    }


# Export tools list
TOOLS = [railway_services, railway_logs, railway_status]
