"""SQLite database setup for pipeline persistence and model registry."""

import sqlite3
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # CASCADE 삭제 실제 동작 보장
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

        # Phase 12A: router-1 system_prompt 마이그레이션 (구버전인 경우에만 업데이트)
        # Phase Qwen3.5: Thinking Mode 비활성화 지시 추가
        _NEW_ROUTER_PROMPT = (
            "You are a task routing system. Analyze the user request and decide "
            "which specialist agents are needed.\n\n"
            "Available agents:\n"
            "- coder-1: code generation, programming, implementation tasks\n"
            "- analyzer-1: architecture review, security analysis, requirements\n\n"
            "IMPORTANT: Do NOT output <think>...</think> thinking blocks. "
            "Respond directly without any internal chain-of-thought.\n\n"
            "CRITICAL: You MUST output a JSON object somewhere in your response:\n"
            "{\"target_agents\": [\"coder-1\", \"analyzer-1\"], "
            "\"reason\": \"Brief explanation of routing decision\"}\n\n"
            "Rules:\n"
            "- List only the agents actually needed for this task\n"
            "- If no specialists needed: "
            "{\"target_agents\": [], \"reason\": \"Simple response, no specialists needed\"}\n"
            "- The JSON MUST appear in your response\n\n"
            "Legacy fallback line (include this too for compatibility):\n"
            "[TARGET_AGENTS] coder-1, analyzer-1"
        )
        # router-1 시스템 프롬프트: JSON 출력 지시 없는 구버전만 업데이트
        conn.execute(
            "UPDATE agent_registry SET system_prompt=? WHERE id='router-1' AND system_prompt NOT LIKE '%target_agents%'",
            (_NEW_ROUTER_PROMPT,)
        )

        # Phase Qwen3.5: 구버전 모델 ID를 가진 경우에만 교체
        _qwen35_migrations = [
            ("router-1",      "Qwen/Qwen3.5-4B",   "Qwen3.5 Router (4B)"),
            ("analyzer-1",    "Qwen/Qwen3.5-4B",   "Qwen3.5 Analyzer (4B)"),
            ("vision-1",      "Qwen/Qwen3.5-0.8B", "Qwen3.5 Vision (0.8B)"),
            ("synthesizer-1", "Qwen/Qwen3.5-2B",   "Qwen3.5 Synthesizer (2B)"),
        ]
        for agent_id, new_model, new_name in _qwen35_migrations:
            conn.execute(
                "UPDATE agent_registry SET model_id=?, name=? WHERE id=? AND model_id != ?",
                (new_model, new_name, agent_id, new_model),
            )

        # ── Phase 13: 대화 히스토리 테이블 ────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New Conversation',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id         TEXT NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
                turn_index         INTEGER NOT NULL,
                user_prompt        TEXT NOT NULL,
                orchestration_mode TEXT NOT NULL DEFAULT 'dag',
                created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_outputs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id     INTEGER NOT NULL REFERENCES conversation_turns(id) ON DELETE CASCADE,
                agent_id    TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT '',
                full_output TEXT NOT NULL DEFAULT '',
                token_count INTEGER DEFAULT 0,
                latency_ms  INTEGER DEFAULT 0,
                vram_gb     REAL DEFAULT 0.0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        count = conn.execute("SELECT COUNT(*) as c FROM agent_registry").fetchone()["c"]
        if count == 0:
            seed_agents = [
                (
                    "router-1", "Qwen3.5 Router (4B)", "router", "transformers", "Qwen/Qwen3.5-4B",
                    "You are a task routing system. Analyze the user request and decide "
                    "which specialist agents are needed.\n\n"
                    "Available agents:\n"
                    "- coder-1: code generation, programming, implementation tasks\n"
                    "- analyzer-1: architecture review, security analysis, requirements\n\n"
                    "IMPORTANT: Do NOT output <think>...</think> thinking blocks. "
                    "Respond directly without any internal chain-of-thought.\n\n"
                    "CRITICAL: You MUST output a JSON object somewhere in your response:\n"
                    "{\"target_agents\": [\"coder-1\", \"analyzer-1\"], "
                    "\"reason\": \"Brief explanation of routing decision\"}\n\n"
                    "Rules:\n"
                    "- List only the agents actually needed for this task\n"
                    "- If no specialists needed: "
                    "{\"target_agents\": [], \"reason\": \"Simple response, no specialists needed\"}\n"
                    "- The JSON MUST appear in your response\n\n"
                    "Legacy fallback line (include this too for compatibility):\n"
                    "[TARGET_AGENTS] coder-1, analyzer-1",
                    256, 0.3
                ),
                (
                    "coder-1", "LocoOperator Coder (4B)", "coder", "transformers", "LocoreMind/LocoOperator-4B",
                    "You are an expert programmer. Generate clean, working code for the task. "
                    "Include type hints and brief comments. Keep the implementation concise.",
                    1024, 0.1
                ),
                (
                    "analyzer-1", "Qwen3.5 Analyzer (4B)", "analyzer", "transformers", "Qwen/Qwen3.5-4B",
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
                    "synthesizer-1", "Qwen3.5 Synthesizer (2B)", "synthesizer", "transformers", "Qwen/Qwen3.5-2B",
                    "You are a technical writer. Synthesize the outputs from all agents into "
                    "a clear final summary. Include: implementation overview, quality score, "
                    "top recommendations. Be concise.",
                    768, 0.4
                ),
                (
                    "vision-1", "Qwen3.5 Vision (0.8B)", "vision", "transformers", "Qwen/Qwen3.5-0.8B",
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
