"""Qwen3.5-4B + 2B 다운로드 스크립트 (role 폴더 구조)."""
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download, list_repo_files

MODELS_DIR = Path(__file__).parent / "models"
SKIP_EXTS = {".msgpack", ".h5", ".ot", ".onnx", ".onnx_data"}

TARGETS = [
    ("Qwen/Qwen3.5-4B", "router"),    # router-1 + analyzer-1 공용
    ("Qwen/Qwen3.5-2B", "synthesizer"),
]


def download(model_id: str, role: str) -> None:
    folder_name = model_id.replace("/", "--")
    local_dir = MODELS_DIR / role / folder_name
    local_dir.mkdir(parents=True, exist_ok=True)

    # 이미 config.json 있으면 스킵
    if (local_dir / "config.json").exists():
        print(f"[SKIP] {model_id} already exists at {local_dir}")
        return

    print(f"\n[DOWNLOAD] {model_id} -> {local_dir}")
    files = [f for f in list_repo_files(model_id)
             if not any(f.endswith(ext) for ext in SKIP_EXTS)]
    total = len(files)
    print(f"  Files to download: {total}")

    for i, filename in enumerate(files, 1):
        dest = local_dir / filename
        if dest.exists():
            print(f"  [{i:2d}/{total}] SKIP {filename}")
            continue
        print(f"  [{i:2d}/{total}] {filename} ...", end=" ", flush=True)
        try:
            hf_hub_download(
                repo_id=model_id,
                filename=filename,
                local_dir=str(local_dir),
                local_dir_use_symlinks=False,
            )
            size = (local_dir / filename).stat().st_size / 1024**2
            print(f"OK ({size:.0f} MB)")
        except Exception as e:
            print(f"ERROR: {e}")

    total_gb = sum(f.stat().st_size for f in local_dir.rglob("*") if f.is_file()) / 1024**3
    print(f"\n[DONE] {model_id} - {total_gb:.2f} GB total")


if __name__ == "__main__":
    for mid, role in TARGETS:
        download(mid, role)
    print("\n=== All downloads complete ===")
