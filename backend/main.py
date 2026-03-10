from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pipeline.models import RunRequest
from pipeline.orchestrator import run_pipeline
from providers.registry import registry, ModelWatcher
from db import crud, database
from config import MODEL_REGISTRY, get_model_info
from pydantic import BaseModel
from typing import Any, Optional
from pathlib import Path
import asyncio
import json
import os
import time

# 로컬 모델 저장 경로 (HF 캐시 미사용)
MODELS_DIR = Path(__file__).parent / "models"

# Ensure SQLite tables exist and default agents are seeded on startup
database.init_db()

# 업로드 디렉토리 생성 및 마운트 (정적 파일 서빙용)
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


# ─── Lifecycle (FastAPI lifespan — on_event deprecated 대체) ──────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 관리."""
    # startup
    await ModelWatcher.get_instance().start()
    yield
    # shutdown
    await ModelWatcher.get_instance().stop()
    from providers.transformers_provider import _executor
    _executor.shutdown(wait=True)


app = FastAPI(title="Local Agent Studio", lifespan=lifespan)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# ─── CORS ─────────────────────────────────────────────────────────────────────
_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra = os.environ.get("CORS_ORIGINS", "")
_cors_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Cache-Control", "X-Requested-With"],
)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "online", "version": "0.2.0"}


@app.get("/api/status")
def status():
    return {"status": "online", "backend": "Local Agent Studio"}


@app.get("/api/providers")
async def get_providers():
    """Health check for all provider backends."""
    results = await registry.health_check_all()
    return {"providers": results}


@app.get("/api/models")
async def get_models():
    """List available models from each reachable provider."""
    models = await registry.list_models_all()
    return {"models": models}


@app.get("/api/registry/agents")
def get_registry_agents():
    """List all SOTA configurable agent templates from SQLite registry."""
    agents = crud.list_agents()
    return {"agents": agents}


# ─── Agent Registry CRUD ──────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    id: str
    name: str
    role: str
    provider_type: str
    model_id: str
    system_prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    tools: str = "[]"


class AgentUpdate(BaseModel):
    name: str
    role: str
    provider_type: str
    model_id: str
    system_prompt: str
    max_tokens: int
    temperature: float
    tools: str = "[]"


@app.post("/api/registry/agents", status_code=201)
def create_agent_endpoint(body: AgentCreate):
    """신규 에이전트를 DB에 등록."""
    if crud.get_agent(body.id):
        raise HTTPException(status_code=409, detail=f"Agent '{body.id}' already exists")
    crud.create_agent(
        body.id, body.name, body.role, body.provider_type,
        body.model_id, body.system_prompt, body.max_tokens, body.temperature, body.tools,
    )
    return {"ok": True, "id": body.id}


@app.put("/api/registry/agents/{agent_id}")
def update_agent_endpoint(agent_id: str, body: AgentUpdate):
    """기존 에이전트 정보 수정."""
    if not crud.get_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    crud.update_agent(
        agent_id, body.name, body.role, body.provider_type,
        body.model_id, body.system_prompt, body.max_tokens, body.temperature, body.tools,
    )
    return {"ok": True}


@app.delete("/api/registry/agents/{agent_id}")
def delete_agent_endpoint(agent_id: str):
    """에이전트를 DB에서 삭제."""
    if not crud.get_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    crud.delete_agent(agent_id)
    return {"ok": True}


# ─── Pipeline CRUD ────────────────────────────────────────────────────────────

class PipelineSaveRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[Any] = []
    edges: list[Any] = []
    node_configs: dict[str, Any] = {}


@app.get("/api/pipelines")
def list_pipelines():
    """List all saved pipeline presets."""
    return {"pipelines": crud.list_pipelines()}


@app.post("/api/pipelines", status_code=201)
def create_pipeline(body: PipelineSaveRequest):
    """Save a new pipeline preset."""
    pid = crud.create_pipeline(
        body.name, body.description, body.nodes, body.edges, body.node_configs
    )
    return {"id": pid}


@app.get("/api/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: int):
    """Load a pipeline preset by ID."""
    row = crud.get_pipeline(pipeline_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return row


@app.put("/api/pipelines/{pipeline_id}")
def update_pipeline(pipeline_id: int, body: PipelineSaveRequest):
    """Update an existing pipeline preset."""
    row = crud.get_pipeline(pipeline_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    crud.update_pipeline(
        pipeline_id, body.name, body.description, body.nodes, body.edges, body.node_configs
    )
    return {"ok": True}


@app.delete("/api/pipelines/{pipeline_id}")
def delete_pipeline(pipeline_id: int):
    """Delete a pipeline preset."""
    crud.delete_pipeline(pipeline_id)
    return {"ok": True}


# ─── Model Info ───────────────────────────────────────────────────────────────

@app.get("/api/models/info")
def get_model_info_all():
    """등록된 모든 모델의 개발사 정보 + 권장 파라미터 반환."""
    return {"models": MODEL_REGISTRY}


@app.get("/api/models/info/{model_id:path}")
def get_model_info_one(model_id: str):
    """특정 모델의 개발사 정보 + 권장 파라미터 반환."""
    info = get_model_info(model_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not in registry")
    return info


# ─── Dynamic Model Discovery (Phase 19) ──────────────────────────────────────

@app.get("/api/models/watch")
async def watch_models(req: Request):
    """
    SSE 스트림: Ollama/LMStudio 모델 목록 변경을 실시간으로 전송.
    - 연결 직후: 현재 전체 목록을 model_snapshot 이벤트로 전송
    - 이후: model_added / model_removed 이벤트 (변경 시에만)
    - 30초마다 ping 이벤트 (연결 유지)
    """
    watcher = ModelWatcher.get_instance()
    q = watcher.subscribe()

    def sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async def generate():
        # 1) 연결 직후 현재 스냅샷 전송
        snapshot = watcher.get_current_models()
        for provider, models in snapshot.items():
            yield sse({"type": "model_snapshot", "provider": provider, "models": models})

        last_ping = time.time()
        try:
            while True:
                if await req.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield sse(event)
                except asyncio.TimeoutError:
                    now = time.time()
                    if now - last_ping >= 30.0:
                        yield sse({"type": "ping", "timestamp": now})
                        last_ping = now
        finally:
            watcher.unsubscribe(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.post("/api/models/refresh")
async def refresh_models():
    """수동 새로고침: ModelWatcher를 즉시 1회 폴링하고 현재 목록 반환."""
    watcher = ModelWatcher.get_instance()
    await watcher._poll_once()
    return {"models": watcher.get_current_models(), "ok": True}


# ─── Model Download ───────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    model_id: str


@app.get("/api/models/local")
async def get_local_models():
    """List locally downloaded models.
    - flat:  models/<org>--<name>/
    - role:  models/<role>/<org>--<name>/
    """
    result = []
    if not MODELS_DIR.exists():
        return {"models": result}

    for top in sorted(MODELS_DIR.iterdir()):
        if not top.is_dir() or top.name.startswith(".") or top.name == "__pycache__":
            continue

        # role 하위 폴더 구조: config.json 없고 하위에 모델 폴더 존재
        if not (top / "config.json").exists():
            for model_dir in sorted(top.iterdir()):
                if not model_dir.is_dir() or not (model_dir / "config.json").exists():
                    continue
                total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
                result.append({
                    "model_id": model_dir.name.replace("--", "/", 1),
                    "role": top.name,
                    "local_path": str(model_dir),
                    "size": total_size,
                    "size_str": f"{round(total_size / (1024**3), 2)} GB",
                    "nb_files": sum(1 for f in model_dir.rglob("*") if f.is_file()),
                })
        else:
            # flat 구조
            total_size = sum(f.stat().st_size for f in top.rglob("*") if f.is_file())
            result.append({
                "model_id": top.name.replace("--", "/", 1),
                "role": None,
                "local_path": str(top),
                "size": total_size,
                "size_str": f"{round(total_size / (1024**3), 2)} GB",
                "nb_files": sum(1 for f in top.rglob("*") if f.is_file()),
            })

    return {"models": result}


@app.post("/api/models/download")
async def download_model(body: DownloadRequest, req: Request):
    """
    HuggingFace 모델을 backend/models/<org>--<name>/ 에 다운로드 (HF 캐시 미사용).
    snapshot_download + tqdm 진행률 콜백을 SSE로 스트리밍.
    """
    def sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async def generate():
        model_id = body.model_id.strip()
        import re as _re
        # 1. 경로 순회 패턴 즉시 거부 (../ ..\\ 시퀀스)
        if _re.search(r"\.\.[/\\]", model_id) or model_id in ("..", "."):
            yield sse({"type": "download_error", "message": "Invalid model_id: path traversal detected"})
            return
        # 2. 슬래시를 이중 대시로 변환 (org/model → org--model)
        safe_name = model_id.replace("/", "--").replace("\\", "--")
        # 3. 영문자·숫자·하이픈·점·언더스코어만 허용
        safe_name = _re.sub(r"[^\w\-.]", "", safe_name)
        if not safe_name:
            yield sse({"type": "download_error", "message": "Invalid model_id"})
            return
        # 4. MODELS_DIR 경계 이중 검사
        candidate = (MODELS_DIR / safe_name).resolve()
        try:
            candidate.relative_to(MODELS_DIR.resolve())
        except ValueError:
            yield sse({"type": "download_error", "message": "Path traversal detected"})
            return
        local_dir = candidate
        local_dir.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_running_loop()

        # ── 1. 파일 목록 조회 ────────────────────────────────────────────────
        yield sse({"type": "download_listing", "modelId": model_id})
        try:
            from huggingface_hub import list_repo_files
            all_files: list[str] = await loop.run_in_executor(
                None, lambda: list(list_repo_files(model_id))
            )
        except Exception as e:
            yield sse({"type": "download_error", "message": str(e)})
            return

        skip_exts = {".msgpack", ".h5", ".ot", ".onnx", ".onnx_data"}
        essential = [f for f in all_files if not any(f.endswith(ext) for ext in skip_exts)]
        total = len(essential)

        yield sse({"type": "download_start", "modelId": model_id, "totalFiles": total})

        # ── 2. 파일별 순차 다운로드 (hf_hub_download → local_dir) ───────────
        from huggingface_hub import hf_hub_download
        downloaded = 0
        errors = 0

        for i, filename in enumerate(essential):
            if await req.is_disconnected():
                return

            yield sse({
                "type": "download_file",
                "filename": filename,
                "fileIndex": i,
                "totalFiles": total,
                "pct": round(i / total * 100, 1),
            })

            try:
                await loop.run_in_executor(
                    None,
                    lambda f=filename: hf_hub_download(
                        repo_id=model_id,
                        filename=f,
                        local_dir=str(local_dir),
                        local_dir_use_symlinks=False,  # 심볼릭 링크 없이 실제 파일 복사
                    ),
                )
                downloaded += 1
            except Exception as e:
                errors += 1
                yield sse({"type": "download_file_error", "filename": filename, "message": str(e)})

        # ── 3. 완료 ──────────────────────────────────────────────────────────
        # 전체 크기 계산
        total_bytes = sum(f.stat().st_size for f in local_dir.rglob("*") if f.is_file())
        size_gb = round(total_bytes / (1024 ** 3), 2)

        yield sse({
            "type": "download_complete",
            "modelId": model_id,
            "localPath": str(local_dir),
            "totalFiles": total,
            "downloaded": downloaded,
            "errors": errors,
            "sizeGb": size_gb,
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── GPU VRAM & 모델 언로드 ───────────────────────────────────────────────────

@app.get("/api/vram")
def get_vram_status():
    """현재 GPU VRAM 사용량 + 캐시된 모델 목록 반환."""
    from providers.transformers_provider import TransformersProvider, _model_cache
    return {
        "vram": TransformersProvider.get_vram_info(),
        "cached_models": list(_model_cache.keys()),
        "cached_count": len(_model_cache),
    }


class UnloadRequest(BaseModel):
    model_id: str


@app.post("/api/models/unload")
def unload_model_endpoint(body: UnloadRequest):
    """GPU VRAM에서 특정 모델을 언로드."""
    success = registry.unload_transformers(body.model_id)
    from providers.transformers_provider import TransformersProvider
    return {
        "ok": success,
        "model_id": body.model_id,
        "message": "Unloaded" if success else "Model not in cache",
        "vram_allocated_gb": TransformersProvider.get_vram_allocated_gb(),
    }


@app.post("/api/models/unload_all")
def unload_all_endpoint():
    """GPU VRAM에서 모든 Transformers 모델을 언로드."""
    unloaded = registry.unload_all_transformers()
    from providers.transformers_provider import TransformersProvider
    return {
        "ok": True,
        "unloaded": unloaded,
        "count": len(unloaded),
        "vram_allocated_gb": TransformersProvider.get_vram_allocated_gb(),
    }


# ─── Conversations (Phase 13) ─────────────────────────────────────────────────

@app.get("/api/conversations")
def list_conversations():
    """저장된 대화 세션 목록 + 각 세션의 턴 수 반환."""
    sessions = crud.list_sessions()
    for s in sessions:
        s["turn_count"] = crud.get_session_turn_count(s["id"])
    return {"sessions": sessions}


@app.get("/api/conversations/{session_id}")
def get_conversation(session_id: str):
    """특정 세션의 모든 턴 + 에이전트 출력 반환 (단일 JOIN 쿼리)."""
    session = crud.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    turns = crud.list_turns_with_outputs(session_id)  # N+1 → 단일 쿼리
    return {"session": session, "turns": turns}


@app.delete("/api/conversations/{session_id}")
def delete_conversation(session_id: str):
    """대화 세션 삭제 (CASCADE: turns + agent_outputs 포함)."""
    if not crud.get_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    crud.delete_session(session_id)
    return {"ok": True}


# ─── Run History (Phase 15) ───────────────────────────────────────────────────

@app.get("/api/runs")
def list_runs(limit: int = 50, offset: int = 0):
    """파이프라인 실행 히스토리 목록 (최신순)."""
    return {
        "runs": crud.list_runs(limit=limit, offset=offset),
        "total": crud.count_runs(),
    }


@app.get("/api/runs/{run_id}")
def get_run(run_id: int):
    """특정 실행 히스토리 상세 (에이전트별 출력 포함)."""
    row = crud.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Run #{run_id} not found")
    return row


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: int):
    """실행 히스토리 삭제."""
    if not crud.get_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run #{run_id} not found")
    crud.delete_run(run_id)
    return {"ok": True}


# ─── MCP (Phase 20) ───────────────────────────────────────────────────────────

class McpServerCreate(BaseModel):
    id: str
    name: str
    transport: str           # stdio | sse
    command: Optional[str] = None
    url: Optional[str] = None


@app.get("/api/mcp/servers")
def list_mcp_servers():
    """등록된 MCP 서버 목록."""
    from mcp.registry import list_servers
    return {"servers": list_servers()}


@app.post("/api/mcp/servers", status_code=201)
def create_mcp_server(body: McpServerCreate):
    """MCP 서버 등록."""
    from mcp.registry import create_server, get_server
    if get_server(body.id):
        raise HTTPException(status_code=409, detail=f"Server '{body.id}' already exists")
    server = create_server(body.id, body.name, body.transport, body.command, body.url)
    return {"ok": True, "server": server}


@app.delete("/api/mcp/servers/{server_id}")
def delete_mcp_server(server_id: str):
    """MCP 서버 제거."""
    from mcp.registry import delete_server
    if server_id == "duckduckgo-builtin":
        raise HTTPException(status_code=400, detail="Cannot delete built-in server")
    ok = delete_server(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    return {"ok": True}


@app.post("/api/mcp/servers/{server_id}/test")
async def test_mcp_server(server_id: str):
    """MCP 서버 연결 테스트 + 도구 목록 조회."""
    from mcp.registry import test_server
    result = await test_server(server_id)
    return result


@app.get("/api/mcp/tools")
async def list_mcp_tools():
    """모든 활성 MCP 서버의 통합 도구 목록."""
    from mcp.registry import list_all_tools
    tools = await list_all_tools()
    # builtin 항상 포함
    builtin = [{"name": "web_search", "description": "DuckDuckGo 웹 검색 (내장)", "server_id": "duckduckgo-builtin"}]
    return {
        "tools": builtin + [{"name": t.name, "description": t.description, "server_id": t.server_id} for t in tools]
    }


# ─── RAG (Phase 22) ───────────────────────────────────────────────────────────

@app.get("/api/rag/collections")
def list_rag_collections():
    """ChromaDB 컬렉션 목록 + 청크 수 반환."""
    from rag.store import list_collections
    return {"collections": list_collections()}


@app.delete("/api/rag/collections/{collection_name}")
def delete_rag_collection(collection_name: str):
    """RAG 컬렉션 삭제."""
    from rag.store import delete_collection
    ok = delete_collection(collection_name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    return {"ok": True}


class RagQueryRequest(BaseModel):
    collection: str
    query: str
    top_k: int = 5
    min_score: float = 0.3


@app.post("/api/rag/query")
def rag_query(body: RagQueryRequest):
    """RAG 검색: 쿼리와 유사한 청크 반환."""
    from rag.retriever import retrieve
    chunks = retrieve(body.collection, body.query, top_k=body.top_k, min_score=body.min_score)
    return {"chunks": chunks, "count": len(chunks)}


@app.post("/api/upload/image")
async def upload_image(file: UploadFile):
    """비전 멀티모달용 이미지 업로드 (10MB 제한 로직은 프론트/Nginx 위임이라 가정)"""
    import shutil
    import uuid
    
    # 확장자 추출
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    # 고유 파일명 생성
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = UPLOADS_DIR / filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # /uploads/ 경로의 상대 경로 리턴 (프론트 통신 및 컨텍스트 주입용)
    return {"url": f"/uploads/{filename}", "local_path": str(file_path)}

@app.post("/api/rag/upload")
async def rag_upload(
    req: Request,
    collection: str,
    file: UploadFile,
):
    """문서 파일을 파싱 → 청크 → 임베딩 → ChromaDB 저장. 진행률을 SSE로 스트리밍."""
    import tempfile
    import shutil
    from pathlib import Path as _Path
    from rag.ingest import ingest_file

    def sse_r(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    # 임시 파일에 저장
    suffix = _Path(file.filename or "upload").suffix or ".txt"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp.flush()
        tmp_path = _Path(tmp.name)
    finally:
        tmp.close()

    async def generate():
        try:
            async for event in ingest_file(collection, tmp_path, file.filename or "upload"):
                yield sse_r(event)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── Agent Evals (Phase 23) ───────────────────────────────────────────────────

class EvalSetCreate(BaseModel):
    name: str


class EvalCaseCreate(BaseModel):
    question: str
    expected: str = ""
    metrics: list[str] = ["answer_relevance", "completeness", "conciseness"]


class EvalRunRequest(BaseModel):
    eval_set_id: str
    run_label: str = ""
    provider: str = "simulation"


@app.get("/api/evals/sets")
def list_eval_sets():
    """평가 세트 목록 반환."""
    from evals.runner import list_eval_sets as _list
    return {"eval_sets": _list()}


@app.post("/api/evals/sets", status_code=201)
def create_eval_set_endpoint(body: EvalSetCreate):
    """평가 세트 생성."""
    from evals.runner import create_eval_set
    result = create_eval_set(body.name)
    return result


@app.get("/api/evals/sets/{eval_set_id}/cases")
def list_eval_cases_endpoint(eval_set_id: str):
    """평가 케이스 목록."""
    from evals.runner import list_eval_cases
    return {"cases": list_eval_cases(eval_set_id)}


@app.post("/api/evals/sets/{eval_set_id}/cases", status_code=201)
def add_eval_case_endpoint(eval_set_id: str, body: EvalCaseCreate):
    """평가 케이스 추가."""
    from evals.runner import add_eval_case
    case_id = add_eval_case(eval_set_id, body.question, body.expected, body.metrics)
    return {"id": case_id}


@app.delete("/api/evals/cases/{case_id}")
def delete_eval_case_endpoint(case_id: int):
    """평가 케이스 삭제."""
    from evals.runner import delete_eval_case
    delete_eval_case(case_id)
    return {"ok": True}


@app.get("/api/evals/results")
def list_eval_results_endpoint(eval_set_id: Optional[str] = None, limit: int = 20):
    """평가 결과 목록."""
    from evals.runner import list_eval_results
    return {"results": list_eval_results(eval_set_id, limit)}


@app.get("/api/evals/compare")
def compare_eval_runs(run_a: int, run_b: int):
    """두 평가 실행 비교."""
    from evals.runner import compare_runs
    return compare_runs(run_a, run_b)


@app.post("/api/evals/run")
async def run_eval_endpoint(body: EvalRunRequest, req: Request):
    """평가 세트를 실행하고 SSE로 진행률 스트리밍."""
    from evals.runner import run_eval

    def sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async def generate():
        try:
            async for event in run_eval(body.eval_set_id, body.run_label, body.provider):
                if await req.is_disconnected():
                    break
                yield sse(event)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── A2A Protocol (Phase 24) ──────────────────────────────────────────────────

# ── 셀프 A2A 서버 엔드포인트 ────────────────────────────────────────────────

@app.get("/a2a/.well-known/agent.json")
def a2a_agent_card(req: Request):
    """A2A Agent Card — 이 에이전트의 기능을 외부에 노출."""
    from a2a.card import build_agent_card
    base_url = str(req.base_url).rstrip("/")
    return build_agent_card(base_url)


@app.post("/a2a/tasks/send")
async def a2a_tasks_send(payload: dict, req: Request):
    """A2A 태스크 수신 및 실행 (SSE 스트리밍)."""
    from a2a.server import handle_task_send

    async def generate():
        async for event in handle_task_send(payload):
            if await req.is_disconnected():
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/a2a/tasks/{task_id}")
def a2a_get_task(task_id: str):
    """A2A 태스크 상태 조회."""
    from a2a.server import get_task
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@app.get("/a2a/tasks")
def a2a_list_tasks():
    """실행된 A2A 태스크 목록."""
    from a2a.server import list_tasks
    return {"tasks": list_tasks()}


@app.post("/a2a/tasks/{task_id}/cancel")
def a2a_cancel_task(task_id: str):
    """A2A 태스크 취소."""
    from a2a.server import cancel_task
    ok = cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"ok": True}


# ── 외부 A2A 에이전트 관리 ──────────────────────────────────────────────────

class A2AAgentCreate(BaseModel):
    id: str
    name: str
    url: str
    description: str = ""


@app.get("/api/a2a/agents")
def list_external_agents():
    """등록된 외부 A2A 에이전트 목록."""
    from a2a.registry import list_a2a_agents
    return {"agents": list_a2a_agents()}


@app.post("/api/a2a/agents", status_code=201)
def create_external_agent(body: A2AAgentCreate):
    """외부 A2A 에이전트 등록."""
    from a2a.registry import create_a2a_agent, get_a2a_agent
    if get_a2a_agent(body.id):
        raise HTTPException(status_code=409, detail=f"Agent '{body.id}' already exists")
    agent = create_a2a_agent(body.id, body.name, body.url, body.description)
    return {"ok": True, "agent": agent}


@app.delete("/api/a2a/agents/{agent_id}")
def delete_external_agent(agent_id: str):
    """외부 A2A 에이전트 제거."""
    from a2a.registry import delete_a2a_agent
    ok = delete_a2a_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {"ok": True}


@app.post("/api/a2a/agents/{agent_id}/test")
async def test_external_agent(agent_id: str):
    """외부 A2A 에이전트 연결 테스트 + Agent Card 조회."""
    from a2a.registry import get_a2a_agent, update_a2a_agent_skills
    from a2a.client import test_agent_connection
    agent = get_a2a_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    result = await test_agent_connection(agent["url"])
    if result.get("ok"):
        update_a2a_agent_skills(agent_id, result.get("skills", []))
    return result


@app.post("/api/a2a/agents/{agent_id}/send")
async def send_to_external_agent(agent_id: str, payload: dict, req: Request):
    """외부 A2A 에이전트에게 태스크 전송 (SSE 스트리밍)."""
    from a2a.registry import get_a2a_agent
    from a2a.client import send_task
    agent = get_a2a_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    prompt = payload.get("prompt", "")
    skill_id = payload.get("skill_id", "run_pipeline")
    session_id = payload.get("session_id")

    async def generate():
        async for event in send_task(agent["url"], prompt, skill_id, session_id):
            if await req.is_disconnected():
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.post("/api/run")
async def run(request: RunRequest, req: Request):
    """Stream pipeline execution as Server-Sent Events."""

    async def generate():
        try:
            async for chunk in run_pipeline(request.prompt, request):
                if await req.is_disconnected():
                    break
                yield chunk
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
