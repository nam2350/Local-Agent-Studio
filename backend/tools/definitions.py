"""Tool schemas and definitions for function calling."""

AVAILABLE_TOOLS: list[str] = ["web_search", "calculator", "read_file"]

# OpenAI-compatible function calling schemas
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "web_search",
        "description": "Search the web for current information, docs, or news.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculator",
        "description": "Evaluate a mathematical expression and return the result.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression, e.g. '2+2', '(15*8)/3', 'sqrt(144)'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file from the local workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the workspace root",
                }
            },
            "required": ["path"],
        },
    },
]
