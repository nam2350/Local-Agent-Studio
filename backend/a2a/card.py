"""Agent Card — Google A2A 프로토콜 명세 준수.

Agent Card는 에이전트의 메타데이터 + 지원 기능을 JSON으로 노출하여
다른 에이전트가 자동으로 협업할 수 있게 한다.

Reference: https://google.github.io/A2A/specification/
"""

from __future__ import annotations

def build_agent_card(base_url: str = "http://localhost:8000") -> dict:
    """A2A Agent Card JSON 반환."""
    return {
        "protocolVersion": "0.2",
        "name": "Local Agent Studio",
        "description": (
            "A multi-agent orchestration system with RAG, Tool Calling, "
            "Code Sandbox, and MCP support."
        ),
        "url": base_url,
        "iconUrl": f"{base_url}/a2a/icon.png",
        "capabilities": {
            "streaming": True,
            "stateTransitionHistory": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "run_pipeline",
                "name": "Run Pipeline",
                "description": "Execute the multi-agent DAG pipeline with a user prompt.",
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
                "examples": [
                    "Write a Python function that sorts a list",
                    "Analyze security vulnerabilities in this code",
                ],
            },
            {
                "id": "rag_query",
                "name": "RAG Knowledge Query",
                "description": "Query the RAG knowledge base and return relevant context.",
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["application/json"],
                "examples": [
                    {"collection": "docs", "query": "What is the API endpoint?"},
                ],
            },
        ],
        "provider": {
            "organization": "Local-Agent-Studio",
            "url": "https://github.com/local-agent-studio",
        },
        "version": "0.2.0",
    }
