"""Base classes for custom tool system."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, boolean, object, array)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Any = Field(default=None, description="Default value if not provided")
    enum: Optional[list[str]] = Field(default=None, description="Allowed values (for enums)")


class ToolMetadata(BaseModel):
    """Metadata describing a tool."""

    name: str = Field(..., description="Tool name (unique identifier)")
    description: str = Field(..., description="Brief description of what the tool does")
    version: str = Field(default="1.0.0", description="Tool version")
    author: Optional[str] = Field(default=None, description="Tool author")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    skill_file: Optional[str] = Field(default=None, description="Associated .skill.md file")


class ToolResult(BaseModel):
    """Result from tool execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    data: Any = Field(default=None, description="Result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @classmethod
    def success_result(cls, data: Any, **metadata) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def error_result(cls, error: str, **metadata) -> "ToolResult":
        """Create an error result."""
        return cls(success=False, error=error, metadata=metadata)


class BaseTool(ABC):
    """Abstract base class for all custom tools."""

    def __init__(self):
        """Initialize the tool."""
        self._metadata = self.metadata
        self._parameters = self.parameters

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """
        Get tool metadata.

        Returns:
            ToolMetadata describing this tool
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """
        Get tool parameters schema.

        Returns:
            List of ToolParameter objects describing expected inputs
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with provided parameters.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        pass

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parameters before execution.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for param in self._parameters:
            if param.required and param.name not in params:
                return False, f"Missing required parameter: {param.name}"

        # Check parameter types (basic validation)
        for param_name, param_value in params.items():
            param_def = next((p for p in self._parameters if p.name == param_name), None)
            if param_def is None:
                return False, f"Unknown parameter: {param_name}"

            # Type checking
            if param_def.type == "string" and not isinstance(param_value, str):
                return False, f"Parameter {param_name} must be a string"
            elif param_def.type == "number" and not isinstance(param_value, (int, float)):
                return False, f"Parameter {param_name} must be a number"
            elif param_def.type == "boolean" and not isinstance(param_value, bool):
                return False, f"Parameter {param_name} must be a boolean"
            elif param_def.type == "object" and not isinstance(param_value, dict):
                return False, f"Parameter {param_name} must be an object"
            elif param_def.type == "array" and not isinstance(param_value, list):
                return False, f"Parameter {param_name} must be an array"

            # Enum validation
            if param_def.enum and param_value not in param_def.enum:
                return False, f"Parameter {param_name} must be one of: {', '.join(param_def.enum)}"

        return True, None

    async def execute_safe(self, **kwargs) -> ToolResult:
        """
        Execute tool with validation and error handling.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        # Validate parameters
        is_valid, error = self.validate_params(kwargs)
        if not is_valid:
            return ToolResult.error_result(error)

        # Execute with error handling
        try:
            return await self.execute(**kwargs)
        except Exception as e:
            return ToolResult.error_result(f"Tool execution failed: {str(e)}")

    def to_mcp_schema(self) -> dict[str, Any]:
        """
        Convert tool to MCP tool definition schema.

        Returns:
            Dictionary conforming to MCP tool schema
        """
        properties = {}
        required = []

        for param in self._parameters:
            prop_schema = {
                "type": param.type,
                "description": param.description,
            }

            if param.enum:
                prop_schema["enum"] = param.enum

            if param.default is not None:
                prop_schema["default"] = param.default

            properties[param.name] = prop_schema

            if param.required:
                required.append(param.name)

        return {
            "name": self._metadata.name,
            "description": self._metadata.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def __repr__(self) -> str:
        """String representation of the tool."""
        return f"<{self.__class__.__name__}: {self._metadata.name}>"
