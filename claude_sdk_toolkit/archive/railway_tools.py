"""
Railway Tools - Deployment Management

Direct Railway control as first-class Claude tools.
Claude can now read logs, check status, redeploy, and manage env vars.

Tools:
    railway_logs: Get service logs
    railway_status: Check deployment status
    railway_redeploy: Trigger redeployment
    railway_env_get: Get environment variable
    railway_env_set: Set environment variable
    railway_services: List all services in project

Required env vars:
    RAILWAY_TOKEN: Railway API token
    RAILWAY_PROJECT_ID: Default project ID (optional)
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime

# SDK tool decorator
try:
    from claude_agent_sdk import tool
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Fallback decorator for testing - matches SDK signature
    def tool(name: str, description: str, input_schema: dict):
        def decorator(fn):
            fn._is_tool = True
            fn._tool_name = name
            fn._tool_description = description
            fn._tool_schema = input_schema
            return fn
        return decorator

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
# CONFIG
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
# TOOLS
# =============================================================================

@tool(
    name="railway_services",
    description="List all services in a Railway project with their IDs, names, and environments",
    input_schema={"project_id": str}
)
async def railway_services(args: dict) -> Dict[str, Any]:
    """
    List all services in a Railway project.

    Args:
        args: Dict with optional 'project_id' key (uses RAILWAY_PROJECT_ID env var if not specified)

    Returns:
        Dict with 'content' containing services list
    """
    project_id = args.get("project_id") or os.getenv("RAILWAY_PROJECT_ID")
    if not project_id:
        return {
            "content": [{"type": "text", "text": "Error: No project_id provided and RAILWAY_PROJECT_ID not set"}],
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
            return {"error": result["errors"][0]["message"]}
        
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
        
        result = {
            "project_id": project_id,
            "project_name": project.get("name"),
            "service_count": len(services),
            "services": services,
            "environments": environments,
        }

        return {
            "content": [{
                "type": "text",
                "text": f"Found {len(services)} services in project '{project.get('name')}':\n\n" +
                       "\n".join([f"- {s['name']} (ID: {s['id']})" for s in services]) +
                       f"\n\nEnvironments: {', '.join([e['name'] for e in environments])}\n\nFull data: {result}"
            }]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "isError": True
        }


def railway_status(service_name: str, project_id: str = None) -> Dict[str, Any]:
    """
    Get deployment status for a Railway service.
    
    Args:
        service_name: Name of the service
        project_id: Project ID (uses RAILWAY_PROJECT_ID if not specified)
        
    Returns:
        Dict with deployment status, health, and recent deploy info
    """
    project_id = project_id or os.getenv("RAILWAY_PROJECT_ID")
    if not project_id:
        return {"error": "No project_id provided and RAILWAY_PROJECT_ID not set"}
    
    # First get service ID from name
    services_result = railway_services(project_id)
    if "error" in services_result:
        return services_result
    
    service = next(
        (s for s in services_result.get("services", []) if s["name"].lower() == service_name.lower()),
        None
    )
    
    if not service:
        return {
            "error": f"Service '{service_name}' not found",
            "available_services": [s["name"] for s in services_result.get("services", [])]
        }
    
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
    
    try:
        result = graphql_query(query, {"serviceId": service["id"]})
        
        if "errors" in result:
            return {"error": result["errors"][0]["message"]}
        
        svc = result.get("data", {}).get("service", {})
        deployments = [
            {
                "id": edge["node"]["id"],
                "status": edge["node"]["status"],
                "created_at": edge["node"]["createdAt"],
                "meta": edge["node"].get("meta"),
            }
            for edge in svc.get("deployments", {}).get("edges", [])
        ]
        
        current = deployments[0] if deployments else None
        
        return {
            "service_name": service_name,
            "service_id": service["id"],
            "current_status": current["status"] if current else "unknown",
            "last_deploy": current["created_at"] if current else None,
            "recent_deployments": deployments,
        }
        
    except Exception as e:
        return {"error": str(e)}


# @tool  # TODO: Convert to async SDK format
def railway_logs(
    service_name: str,
    lines: int = 100,
    project_id: str = None
) -> Dict[str, Any]:
    """
    Get recent logs from a Railway service.
    
    Args:
        service_name: Name of the service
        lines: Number of log lines to retrieve (default: 100)
        project_id: Project ID (uses RAILWAY_PROJECT_ID if not specified)
        
    Returns:
        Dict with 'logs' list containing timestamp and message
        
    Examples:
        railway_logs("enterprise-bot")
        railway_logs("frontend", lines=50)
    """
    project_id = project_id or os.getenv("RAILWAY_PROJECT_ID")
    if not project_id:
        return {"error": "No project_id provided and RAILWAY_PROJECT_ID not set"}
    
    # Get service ID
    services_result = railway_services(project_id)
    if "error" in services_result:
        return services_result
    
    service = next(
        (s for s in services_result.get("services", []) if s["name"].lower() == service_name.lower()),
        None
    )
    
    if not service:
        return {
            "error": f"Service '{service_name}' not found",
            "available_services": [s["name"] for s in services_result.get("services", [])]
        }
    
    # Note: Railway's log API is via deployments, not direct service logs
    # This gets logs from the latest deployment
    query = """
        query ($serviceId: String!, $limit: Int!) {
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
            deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
                timestamp
                message
                severity
            }
        }
    """
    
    # Two-step: get latest deployment, then its logs
    try:
        # Get latest deployment
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
        
        deploy_result = graphql_query(deploy_query, {"serviceId": service["id"]})
        
        if "errors" in deploy_result:
            return {"error": deploy_result["errors"][0]["message"]}
        
        deployments = deploy_result.get("data", {}).get("service", {}).get("deployments", {}).get("edges", [])
        
        if not deployments:
            return {
                "service_name": service_name,
                "message": "No deployments found for this service",
                "logs": []
            }
        
        deployment_id = deployments[0]["node"]["id"]
        deployment_status = deployments[0]["node"]["status"]
        
        # Get logs for this deployment
        logs_query = """
            query ($deploymentId: String!, $limit: Int!) {
                deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
                    timestamp
                    message
                    severity
                }
            }
        """
        
        logs_result = graphql_query(logs_query, {"deploymentId": deployment_id, "limit": lines})
        
        if "errors" in logs_result:
            # Log fetching might not be available for all plans
            return {
                "service_name": service_name,
                "deployment_id": deployment_id,
                "deployment_status": deployment_status,
                "error": logs_result["errors"][0]["message"],
                "hint": "Log access may require a paid Railway plan"
            }
        
        logs = logs_result.get("data", {}).get("deploymentLogs", []) or []
        
        return {
            "service_name": service_name,
            "deployment_id": deployment_id,
            "deployment_status": deployment_status,
            "log_count": len(logs),
            "logs": logs,
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def railway_redeploy(
    service_name: str,
    project_id: str = None
) -> Dict[str, Any]:
    """
    Trigger a redeployment of a Railway service.
    
    This redeploys the latest commit. Use when you need to restart
    a service or apply env var changes.
    
    Args:
        service_name: Name of the service to redeploy
        project_id: Project ID (uses RAILWAY_PROJECT_ID if not specified)
        
    Returns:
        Dict with deployment ID and status
        
    Examples:
        railway_redeploy("enterprise-bot")
    """
    project_id = project_id or os.getenv("RAILWAY_PROJECT_ID")
    if not project_id:
        return {"error": "No project_id provided and RAILWAY_PROJECT_ID not set"}
    
    # Get service ID
    services_result = railway_services(project_id)
    if "error" in services_result:
        return services_result
    
    service = next(
        (s for s in services_result.get("services", []) if s["name"].lower() == service_name.lower()),
        None
    )
    
    if not service:
        return {
            "error": f"Service '{service_name}' not found",
            "available_services": [s["name"] for s in services_result.get("services", [])]
        }
    
    # Get environment ID (usually "production")
    env_id = None
    for env in services_result.get("environments", []):
        if env["name"].lower() == "production":
            env_id = env["id"]
            break
    
    if not env_id and services_result.get("environments"):
        env_id = services_result["environments"][0]["id"]
    
    if not env_id:
        return {"error": "No environment found for project"}
    
    mutation = """
        mutation ($serviceId: String!, $environmentId: String!) {
            serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
        }
    """
    
    try:
        result = graphql_query(mutation, {
            "serviceId": service["id"],
            "environmentId": env_id,
        })
        
        if "errors" in result:
            return {"error": result["errors"][0]["message"]}
        
        return {
            "service_name": service_name,
            "service_id": service["id"],
            "environment_id": env_id,
            "status": "redeploying",
            "message": f"Redeployment triggered for {service_name}",
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def railway_env_get(
    service_name: str,
    key: str = None,
    project_id: str = None
) -> Dict[str, Any]:
    """
    Get environment variables from a Railway service.
    
    Args:
        service_name: Name of the service
        key: Specific env var key (returns all if not specified)
        project_id: Project ID (uses RAILWAY_PROJECT_ID if not specified)
        
    Returns:
        Dict with env var(s) - values may be masked for security
        
    Examples:
        railway_env_get("enterprise-bot", "DATABASE_URL")
        railway_env_get("enterprise-bot")  # Get all
    """
    project_id = project_id or os.getenv("RAILWAY_PROJECT_ID")
    if not project_id:
        return {"error": "No project_id provided and RAILWAY_PROJECT_ID not set"}
    
    # Get service ID
    services_result = railway_services(project_id)
    if "error" in services_result:
        return services_result
    
    service = next(
        (s for s in services_result.get("services", []) if s["name"].lower() == service_name.lower()),
        None
    )
    
    if not service:
        return {
            "error": f"Service '{service_name}' not found",
        }
    
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
    
    try:
        result = graphql_query(query, {"serviceId": service["id"]})
        
        if "errors" in result:
            return {"error": result["errors"][0]["message"]}
        
        instances = result.get("data", {}).get("service", {}).get("serviceInstances", {}).get("edges", [])
        
        if not instances:
            return {"service_name": service_name, "variables": {}}
        
        variables = instances[0]["node"].get("variables", {})
        
        # Mask sensitive values
        masked = {}
        for k, v in variables.items():
            if key and k.upper() != key.upper():
                continue
            
            # Mask passwords/secrets
            if any(secret in k.upper() for secret in ["PASSWORD", "SECRET", "TOKEN", "KEY", "CREDENTIAL"]):
                masked[k] = v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
            else:
                masked[k] = v
        
        if key:
            return {
                "service_name": service_name,
                "key": key,
                "value": masked.get(key.upper()) or masked.get(key) or "NOT_FOUND",
            }
        
        return {
            "service_name": service_name,
            "variable_count": len(masked),
            "variables": masked,
        }
        
    except Exception as e:
        return {"error": str(e)}


@tool
def railway_env_set(
    service_name: str,
    key: str,
    value: str,
    project_id: str = None
) -> Dict[str, Any]:
    """
    Set an environment variable on a Railway service.
    
    NOTE: This changes the variable but does NOT automatically redeploy.
    Call railway_redeploy after to apply changes.
    
    Args:
        service_name: Name of the service
        key: Environment variable key
        value: Value to set
        project_id: Project ID (uses RAILWAY_PROJECT_ID if not specified)
        
    Returns:
        Dict with success status
        
    Examples:
        railway_env_set("enterprise-bot", "LOG_LEVEL", "debug")
    """
    project_id = project_id or os.getenv("RAILWAY_PROJECT_ID")
    if not project_id:
        return {"error": "No project_id provided and RAILWAY_PROJECT_ID not set"}
    
    # Get service and environment IDs
    services_result = railway_services(project_id)
    if "error" in services_result:
        return services_result
    
    service = next(
        (s for s in services_result.get("services", []) if s["name"].lower() == service_name.lower()),
        None
    )
    
    if not service:
        return {"error": f"Service '{service_name}' not found"}
    
    # Get production environment
    env_id = None
    for env in services_result.get("environments", []):
        if env["name"].lower() == "production":
            env_id = env["id"]
            break
    
    if not env_id and services_result.get("environments"):
        env_id = services_result["environments"][0]["id"]
    
    if not env_id:
        return {"error": "No environment found"}
    
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
    
    try:
        result = graphql_query(mutation, {
            "serviceId": service["id"],
            "environmentId": env_id,
            "variables": {key: value},
        })
        
        if "errors" in result:
            return {"error": result["errors"][0]["message"]}
        
        return {
            "service_name": service_name,
            "key": key,
            "status": "set",
            "message": f"Set {key} on {service_name}. Run railway_redeploy to apply.",
        }
        
    except Exception as e:
        return {"error": str(e)}


# Export tools list
TOOLS = [
    railway_services,
    railway_status,
    railway_logs,
    railway_redeploy,
    railway_env_get,
    railway_env_set,
]