from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pipeline.models import RunRequest
from pipeline.orchestrator import run_pipeline
from providers.registry import registry
from pydantic import BaseModel
import asyncio
import json

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


class DownloadRequest(BaseModel):
    model_id: str


@app.get("/api/models/local")
async def get_local_models():
    """List locally cached HuggingFace models."""
    try:
        from huggingface_hub import scan_cache_dir
        cache_info = scan_cache_dir()
        models = [
            {
                "model_id": repo.repo_id,
                "size":     repo.size_on_disk,
                "size_str": repo.size_on_disk_str,
                "nb_files": repo.nb_files,
            }
            for repo in sorted(cache_info.repos, key=lambda r: r.repo_id)
        ]
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


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
            try:
                await loop.run_in_executor(
                    None, lambda f=filename: hf_hub_download(model_id, f)
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
