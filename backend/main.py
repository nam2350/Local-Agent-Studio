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
    """List locally downloaded models from backend/models/ directory."""
    models = []
    if MODELS_DIR.exists():
        for child in sorted(MODELS_DIR.iterdir()):
            if child.is_dir() and child.name != "__pycache__" and not child.name.startswith("."):
                # 폴더명: org--model-name → org/model-name
                hf_id = child.name.replace("--", "/", 1)
                total_size = sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
                nb_files = sum(1 for f in child.rglob("*") if f.is_file())
                size_gb = round(total_size / (1024**3), 2)
                models.append({
                    "model_id": hf_id,
                    "local_path": str(child),
                    "size": total_size,
                    "size_str": f"{size_gb} GB",
                    "nb_files": nb_files,
                })
    return {"models": models}


@app.post("/api/models/download")
async def download_model(body: DownloadRequest, req: Request):
    """Stream HuggingFace model download progress as SSE."""
    def sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async def generate():
        model_id = body.model_id.strip()
        loop = asyncio.get_event_loop()

        # ── List files ────────────────────────────────────────────────────────
        yield sse({"type": "download_listing", "modelId": model_id})
        try:
            from huggingface_hub import list_repo_files
            files: list[str] = await loop.run_in_executor(
                None, lambda: list(list_repo_files(model_id))
            )
        except Exception as e:
            yield sse({"type": "download_error", "message": str(e)})
            return

        # Skip non-essential large files (keep weights + config)
        skip_exts = {".msgpack", ".h5", ".ot", ".onnx"}
        essential = [f for f in files if not any(f.endswith(ext) for ext in skip_exts)]

        yield sse({
            "type": "download_start",
            "modelId": model_id,
            "totalFiles": len(essential),
        })

        # ── Download each file ────────────────────────────────────────────────
        from huggingface_hub import hf_hub_download
        downloaded = 0
        errors = 0

        for i, filename in enumerate(essential):
            if await req.is_disconnected():
                break
            yield sse({
                "type": "download_file",
                "filename": filename,
                "fileIndex": i,
                "totalFiles": len(essential),
                "pct": round(i / len(essential) * 100, 1),
            })
            # 모델을 로컬 backend/models/<org--name>/ 에 직접 저장
            local_dir = MODELS_DIR / model_id.replace("/", "--")
            try:
                await loop.run_in_executor(
                    None, lambda f=filename: hf_hub_download(
                        model_id, f, local_dir=str(local_dir)
                    )
                )
                downloaded += 1
            except Exception as e:
                errors += 1
                yield sse({"type": "download_file_error", "filename": filename, "message": str(e)})

        yield sse({
            "type": "download_complete",
            "modelId": model_id,
            "totalFiles": len(essential),
            "downloaded": downloaded,
            "errors": errors,
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
