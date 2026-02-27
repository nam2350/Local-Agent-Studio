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

# Human-readable tool prompt injection (for models without native tool support)
TOOL_PROMPT_PREFIX = """You have access to the following tools. Use them when you need external information.

Available tools:
{tools_list}

To call a tool, output EXACTLY this format (on its own line):
[TOOL: tool_name] {{"key": "value"}} [/TOOL]

Example:
[TOOL: web_search] {{"query": "FastAPI JWT authentication"}} [/TOOL]

Wait for the tool result before writing your full response.
---
"""


def build_tool_prompt(enabled_tools: list[str]) -> str:
    schemas = {s["name"]: s for s in TOOL_SCHEMAS}
    lines = []
    for name in enabled_tools:
        if name in schemas:
            s = schemas[name]
            params = list(s["parameters"]["properties"].keys())
            lines.append(f"- {name}({', '.join(params)}): {s['description']}")
    return TOOL_PROMPT_PREFIX.format(tools_list="\n".join(lines))
