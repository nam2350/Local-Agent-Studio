"""Phase 16 E2E GPU 추론 검증 스크립트.

coder-1 (LocoOperator-4B) + validator-1 (Phi-4-mini) 로컬 모델만 실 GPU 추론.
router/analyzer/synthesizer는 시뮬레이션으로 건너뜀.
"""
import asyncio
import time
import sys

sys.path.insert(0, ".")

from providers.transformers_provider import TransformersProvider, unload_model, _vram_allocated_gb

PROMPT = "Write a Python function that returns the nth Fibonacci number using memoization."

TESTS = [
    {
        "agent_id": "coder-1",
        "model_id": "LocoreMind/LocoOperator-4B",
        "system_prompt": "You are an expert programmer. Generate clean, working code.",
        "max_tokens": 256,
        "temperature": 0.1,
    },
    {
        "agent_id": "validator-1",
        "model_id": "microsoft/Phi-4-mini-instruct",
        "system_prompt": "You are a code quality expert. Score the code out of 100. Give a final verdict: APPROVED or NEEDS_REVISION.",
        "max_tokens": 128,
        "temperature": 0.2,
    },
]


async def run_test(cfg: dict) -> None:
    print(f"\n{'='*60}")
    print(f"[{cfg['agent_id']}] model={cfg['model_id']}")
    print(f"{'='*60}")

    provider = TransformersProvider(cfg["model_id"])
    vram_before = _vram_allocated_gb()
    print(f"  VRAM before load : {vram_before:.2f} GB")

    start = time.time()
    tokens: list[str] = []
    token_count = 0

    print(f"  Generating... (max_tokens={cfg['max_tokens']})")
    print("  Output: ", end="", flush=True)

    try:
        async for token in provider.generate(
            prompt=PROMPT,
            system_prompt=cfg["system_prompt"],
            max_tokens=cfg["max_tokens"],
            temperature=cfg["temperature"],
        ):
            tokens.append(token)
            token_count += len(token.split())
            print(token, end="", flush=True)
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        return

    elapsed = time.time() - start
    vram_after = _vram_allocated_gb()
    full_output = "".join(tokens)

    print(f"\n\n  --- Summary ---")
    print(f"  VRAM after load  : {vram_after:.2f} GB  (+{vram_after - vram_before:.2f} GB)")
    print(f"  Latency          : {elapsed:.2f}s")
    print(f"  Output chars     : {len(full_output)}")
    print(f"  Tokens/sec (est) : {len(full_output.split()) / elapsed:.1f}")

    # 메모리 해제
    print(f"  Unloading model...")
    unload_model(cfg["model_id"])
    vram_free = _vram_allocated_gb()
    print(f"  VRAM after unload: {vram_free:.2f} GB")


async def main() -> None:
    print("=== Phase 16 GPU Inference E2E Test ===")

    import torch
    if not torch.cuda.is_available():
        print("[FAIL] CUDA not available")
        return
    props = torch.cuda.get_device_properties(0)
    total_gb = props.total_memory / 1024**3
    print(f"GPU: {props.name}  VRAM: {total_gb:.1f} GB")

    for cfg in TESTS:
        await run_test(cfg)

    print(f"\n{'='*60}")
    print("=== E2E Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
