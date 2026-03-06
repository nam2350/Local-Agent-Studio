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


# ─── 모델 레지스트리 ────────────────────────────────────────────────────────────
# 각 모델의 개발사 정보, 공식 링크, 권장 파라미터를 한 곳에서 관리한다.
# 개발사 권장값 확인: hf_url / github_url 방문
MODEL_REGISTRY: dict = {

    # ── Qwen3.5-4B ───────────────────────────────────────────────────────────────
    # 역할: router-1 (라우팅), analyzer-1 (분석)
    # 두 에이전트가 같은 모델을 공유 → VRAM 8GB 고정
    "Qwen/Qwen3.5-4B": {
        "hf_url":         "https://huggingface.co/Qwen/Qwen3.5-4B",
        "github_url":     "https://github.com/QwenLM/Qwen3.5",
        "paper_url":      "https://qwenlm.github.io/blog/qwen3.5/",
        "developer":      "Alibaba Cloud / Qwen Team",
        "params":         "4B",
        "context_length": 131072,           # 128K tokens
        "vram_fp16_gb":   8.0,
        # 개발사 권장값 (https://huggingface.co/Qwen/Qwen3.5-4B 참고)
        "recommended": {
            "temperature":          0.7,    # 범용; 정밀 작업(코드/수학)은 0.0 권장
            "top_p":                0.8,
            "top_k":                20,
            "repetition_penalty":   1.05,
            "max_new_tokens":       8192,
            "thinking_mode":        True,   # /think 태그로 활성화 가능, 기본은 비활성
        },
        "notes": (
            "Thinking Mode: system prompt에 'Do NOT output <think>' 추가로 비활성화. "
            "IFEval 89.8 SOTA. router/analyzer 역할에 동일 모델 공유로 VRAM 절약."
        ),
    },

    # ── Qwen3.5-2B ───────────────────────────────────────────────────────────────
    # 역할: synthesizer-1 (최종 통합/요약)
    "Qwen/Qwen3.5-2B": {
        "hf_url":         "https://huggingface.co/Qwen/Qwen3.5-2B",
        "github_url":     "https://github.com/QwenLM/Qwen3.5",
        "paper_url":      "https://qwenlm.github.io/blog/qwen3.5/",
        "developer":      "Alibaba Cloud / Qwen Team",
        "params":         "2B",
        "context_length": 262144,           # 262K tokens (시리즈 최대)
        "vram_fp16_gb":   4.0,
        "recommended": {
            "temperature":          0.7,
            "top_p":                0.8,
            "top_k":                20,
            "repetition_penalty":   1.05,
            "max_new_tokens":       4096,
        },
        "notes": (
            "262K 컨텍스트로 긴 멀티에이전트 출력 통합에 최적. "
            "synthesizer 역할: 다른 에이전트 출력 전체를 입력으로 받을 수 있음."
        ),
    },

    # ── Qwen3.5-0.8B ─────────────────────────────────────────────────────────────
    # 역할: vision-1 (이미지/멀티모달 분석)
    "Qwen/Qwen3.5-0.8B": {
        "hf_url":         "https://huggingface.co/Qwen/Qwen3.5-0.8B",
        "github_url":     "https://github.com/QwenLM/Qwen3.5",
        "paper_url":      "https://qwenlm.github.io/blog/qwen3.5/",
        "developer":      "Alibaba Cloud / Qwen Team",
        "params":         "0.8B",
        "context_length": 131072,           # 128K tokens
        "vram_fp16_gb":   1.6,
        "recommended": {
            "temperature":          0.7,
            "top_p":                0.8,
            "top_k":                20,
            "repetition_penalty":   1.05,
            "max_new_tokens":       2048,
        },
        "notes": (
            "VL(Vision-Language) 기능 내장. 초경량 1.6GB. "
            "vision 역할 전용; 이미지 입력 처리 가능."
        ),
    },

    # ── LocoOperator-4B ──────────────────────────────────────────────────────────
    # 역할: coder-1 (코드 생성, Tool Calling)
    "LocoreMind/LocoOperator-4B": {
        "hf_url":         "https://huggingface.co/LocoreMind/LocoOperator-4B",
        "github_url":     "https://github.com/LocoreMind/LocoOperator",
        "paper_url":      "",               # 논문 없음 (공개 파인튜닝 모델)
        "developer":      "LocoreMind",
        "params":         "4B",
        "context_length": 32768,            # 32K tokens
        "vram_fp16_gb":   7.5,
        "recommended": {
            "temperature":          0.1,    # 코드 생성: 낮은 온도 권장
            "top_p":                0.95,
            "repetition_penalty":   1.0,
            "max_new_tokens":       2048,
        },
        "notes": (
            "Tool Calling / Function Calling 특화 파인튜닝 모델. "
            "Qwen2.5 기반. coder 역할: 낮은 temperature(0.0~0.2) 권장."
        ),
    },

    # ── Phi-4-mini-instruct ───────────────────────────────────────────────────────
    # 역할: validator-1 (코드 품질 검증)
    "microsoft/Phi-4-mini-instruct": {
        "hf_url":         "https://huggingface.co/microsoft/Phi-4-mini-instruct",
        "github_url":     "https://github.com/microsoft/Phi-4-mini",
        "paper_url":      "https://arxiv.org/abs/2503.01743",
        "developer":      "Microsoft Research",
        "params":         "3.8B",
        "context_length": 16384,            # 16K tokens
        "vram_fp16_gb":   7.15,
        "recommended": {
            "temperature":          0.0,    # 검증/평가 태스크: 결정론적 출력 권장
            "top_p":                1.0,
            "repetition_penalty":   1.0,
            "max_new_tokens":       1024,
            "do_sample":            False,  # greedy decoding 권장
        },
        "notes": (
            "transformers 내장 phi3 구현 사용 (config.json의 auto_map 제거 필수). "
            "수학/코드 검증에 강점. validator 역할: do_sample=False + temperature=0.0 권장. "
            "패치 적용됨: backend/models/validator/microsoft--Phi-4-mini-instruct/config.json"
        ),
    },
}


def get_model_info(model_id: str) -> dict:
    """model_id에 해당하는 레지스트리 정보 반환. 없으면 빈 dict."""
    return MODEL_REGISTRY.get(model_id, {})


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
    if MODELS_DIR.exists():
        flat = MODELS_DIR / folder_name
        if _is_valid(flat):
            return str(flat)

    # 2) role 하위 폴더 구조 (models/<role>/<org>--<name>/)
    if MODELS_DIR.exists():
        for role_dir in MODELS_DIR.iterdir():
            if not role_dir.is_dir():
                continue
            candidate = role_dir / folder_name
            if _is_valid(candidate):
                return str(candidate)

    return model_id
