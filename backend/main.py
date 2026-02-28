from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pipeline.models import RunRequest
from pipeline.orchestrator import run_pipeline
from providers.registry import registry
from db import crud, database
from pydantic import BaseModel
from typing import Any
from pathlib import Path
import asyncio
import json

# 로컬 모델 저장 경로 (HF 캐시 미사용)
MODELS_DIR = Path(__file__).parent / "models"

# Ensure SQLite tables exist and default agents are seeded on startup
database.init_db()

app = FastAPI(title="Local Agent Studio API", version="0.2.0")

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        local_dir = MODELS_DIR / model_id.replace("/", "--")
        local_dir.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()

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
