"""
download_models.py - Local SOTA Model Batch Download Script

Usage:
    python download_models.py                    # DB 등록된 전체 모델 다운로드
    python download_models.py --model katanemo/Plano-Orchestrator-4B   # 특정 모델만
    python download_models.py --list             # 등록 모델 조회만

HF 캐시를 사용하지 않고 backend/models/<org--name>/ 에 직접 저장합니다.
"""

import argparse
import sys
import io
from pathlib import Path

# Windows 콘솔 UTF-8 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트에서 실행해도 import 가능하도록 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from db.database import init_db
from db.crud import list_agents

MODELS_DIR = Path(__file__).parent / "models"

# 불필요한 대용량 파일 확장자 (다운로드 스킵)
SKIP_EXTENSIONS = {".msgpack", ".h5", ".ot", ".onnx", ".onnx_data"}


def download_single_model(model_id: str) -> None:
    """단일 모델을 backend/models/<org--name>/ 에 다운로드."""
    from huggingface_hub import snapshot_download

    local_dir = MODELS_DIR / model_id.replace("/", "--")
    local_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"[DOWNLOAD] {model_id}")
    print(f"  -> {local_dir}")
    print(f"{'='*60}")

    try:
        snapshot_download(
            repo_id=model_id,
            local_dir=str(local_dir),
            ignore_patterns=[f"*{ext}" for ext in SKIP_EXTENSIONS],
        )
        print(f"[OK] {model_id}")
    except Exception as e:
        print(f"[FAIL] {model_id} -- {e}")


def main():
    parser = argparse.ArgumentParser(description="Local SOTA Model Downloader")
    parser.add_argument("--model", type=str, help="Download specific HF model_id only")
    parser.add_argument("--list", action="store_true", help="List registered models only")
    args = parser.parse_args()

    # DB 초기화 (테이블 및 시드 보장)
    init_db()

    if args.model:
        download_single_model(args.model)
        return

    # DB에서 등록된 모든 에이전트의 model_id 수집
    agents = list_agents()
    model_ids = list(dict.fromkeys(a["model_id"] for a in agents))  # 중복 제거, 순서 유지

    if args.list:
        print("\n[Registered SOTA Models]")
        for i, mid in enumerate(model_ids, 1):
            local_path = MODELS_DIR / mid.replace("/", "--")
            downloaded = local_path.exists() and any(local_path.iterdir())
            status = "DOWNLOADED" if downloaded else "NOT YET"
            print(f"  {i}. {mid}  [{status}]")
        return

    # 전체 모델 다운로드
    print(f"\n[START] Downloading {len(model_ids)} models to backend/models/")
    print(f"  Models: {', '.join(model_ids)}")
    print(f"  WARNING: Requires ~20-40GB disk space\n")

    for mid in model_ids:
        download_single_model(mid)

    print(f"\n{'='*60}")
    print(f"[DONE] All models saved to: {MODELS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
