"""Centralized configuration for Local Agent Studio backend."""

from pathlib import Path

# Project root: D:/Workspace/Local-Agent-Studio/
PROJECT_ROOT = Path(__file__).parent.parent

# Local model storage (HF 캐시 미사용)
# 구조: backend/models/<org>--<model-name>/
# 예:  backend/models/katanemo--Plano-Orchestrator-4B/
MODELS_DIR = Path(__file__).parent / "models"

# SQLite DB
DB_PATH = Path(__file__).parent / "studio.db"


def resolve_model_path(model_id: str) -> str:
    """
    HF model_id를 받아 로컬 경로가 있으면 로컬 경로를 반환,
    없으면 원래 model_id를 반환 (HF 캐시 폴백).

    탐색 순서:
      1) backend/models/<org>--<name>/          (레거시 flat 구조)
      2) backend/models/<role>/<org>--<name>/   (역할별 분류 구조)

    로컬 경로 조건: config.json + .safetensors 또는 .bin 파일 존재.
    """
    folder_name = model_id.replace("/", "--")

    def _is_valid(path: Path) -> bool:
        return (
            path.is_dir()
            and (path / "config.json").exists()
            and (any(path.glob("*.safetensors")) or any(path.glob("*.bin")))
        )

    # 1) flat 구조
    flat = MODELS_DIR / folder_name
    if _is_valid(flat):
        return str(flat)

    # 2) role 하위 폴더 구조 (models/<role>/<org>--<name>/)
    for role_dir in MODELS_DIR.iterdir():
        if not role_dir.is_dir():
            continue
        candidate = role_dir / folder_name
        if _is_valid(candidate):
            return str(candidate)

    return model_id
