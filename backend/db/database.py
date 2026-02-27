"""SQLite database setup for pipeline persistence and model registry."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "studio.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist and seed default agents."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                description     TEXT    DEFAULT '',
                nodes_json      TEXT    NOT NULL DEFAULT '[]',
                edges_json      TEXT    NOT NULL DEFAULT '[]',
                node_configs_json TEXT  NOT NULL DEFAULT '{}',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_registry (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                role            TEXT NOT NULL,
                provider_type   TEXT NOT NULL,
                model_id        TEXT NOT NULL,
                system_prompt   TEXT NOT NULL,
                max_tokens      INTEGER DEFAULT 512,
                temperature     REAL DEFAULT 0.7,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Always ensure validator uses latest model (migration for existing DBs)
        conn.execute(
            "UPDATE agent_registry SET model_id=?, name=? WHERE id='validator-1' AND model_id IN (?, ?)",
            ("microsoft/Phi-4-mini-instruct", "Phi-4 Mini Validator (3.8B)",
             "google/gemma-2-2b-it", "google/gemma-3-4b-it")
        )

        count = conn.execute("SELECT COUNT(*) as c FROM agent_registry").fetchone()["c"]
        if count == 0:
            seed_agents = [
                (
                    "router-1", "Plano Orchestrator (4B)", "router", "transformers", "katanemo/Plano-Orchestrator-4B",
                    "You are a task routing system. Analyze the user request briefly. "
                    "Classify the task type, estimate complexity, and decide which specialist "
                    "agents are needed: 'coder-1' (for coding/programming), 'analyzer-1' (for architecture/security review).\n\n"
                    "CRITICAL: You MUST include a line exactly like this in your response:\n"
                    "[TARGET_AGENTS] coder-1, analyzer-1\n"
                    "If no specialists are needed (e.g. general chat), output: [TARGET_AGENTS] none",
                    256, 0.3
                ),
                (
                    "coder-1", "LocoOperator Coder (4B)", "coder", "transformers", "LocoreMind/LocoOperator-4B",
                    "You are an expert programmer. Generate clean, working code for the task. "
                    "Include type hints and brief comments. Keep the implementation concise.",
                    1024, 0.1
                ),
                (
                    "analyzer-1", "Nanbeige Analyzer (3B)", "analyzer", "transformers", "heretic-org/Nanbeige4.1-3B-heretic",
                    "You are a technical analyst. Review the task and any code provided. "
                    "Identify security issues, performance concerns, and give brief recommendations.",
                    512, 0.5
                ),
                (
                    "validator-1", "Phi-4 Mini Validator (3.8B)", "validator", "transformers", "microsoft/Phi-4-mini-instruct",
                    "You are a code quality expert. Score the provided code out of 100 for "
                    "quality and security. List top 3 issues. Give a final verdict: APPROVED or NEEDS_REVISION.",
                    512, 0.2
                ),
                (
                    "synthesizer-1", "Jan Synthesizer (4B)", "synthesizer", "transformers", "janhq/Jan-v3-4B-base-instruct",
                    "You are a technical writer. Synthesize the outputs from all agents into "
                    "a clear final summary. Include: implementation overview, quality score, "
                    "top recommendations. Be concise.",
                    768, 0.4
                ),
                (
                    "vision-1", "LFM Vision (1.6B)", "vision", "transformers", "LiquidAI/LFM2.5-VL-1.6B",
                    "You are an expert vision analyst. Analyze the provided image or UI and provide "
                    "feedback on accessibility, design, and structure.",
                    512, 0.4
                )
            ]
            conn.executemany(
                "INSERT INTO agent_registry (id, name, role, provider_type, model_id, system_prompt, max_tokens, temperature) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                seed_agents
            )
        conn.commit()
