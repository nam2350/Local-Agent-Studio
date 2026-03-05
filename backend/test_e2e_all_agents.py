"""6-에이전트 전체 E2E GPU 추론 테스트 — 순차 실행, 모델별 언로드"""
import sys, os, time, asyncio
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import torch
from providers.transformers_provider import TransformersProvider, _vram_allocated_gb, unload_model
import gc

AGENTS = [
    {
        "id": "router-1",
        "model": "Qwen/Qwen3.5-4B",
        "system": "You are a task routing system. Be very brief.",
        "prompt": "Build a REST API with JWT auth. Which agents are needed?",
        "max_tokens": 80,
    },
    {
        "id": "coder-1",
        "model": "LocoreMind/LocoOperator-4B",
        "system": "You are an expert programmer. Write clean code.",
        "prompt": "Write a simple JWT login endpoint in Python FastAPI. Just the core function.",
        "max_tokens": 120,
    },
    {
        "id": "analyzer-1",
        "model": "Qwen/Qwen3.5-4B",
        "system": "You are a security analyst. Be brief.",
        "prompt": "Review this: POST /auth/login endpoint with JWT. List top 2 security risks.",
        "max_tokens": 80,
    },
    {
        "id": "validator-1",
        "model": "microsoft/Phi-4-mini-instruct",
        "system": "You are a code validator. Be brief.",
        "prompt": "Validate: def add(a,b): return a+b. Score out of 100 and verdict.",
        "max_tokens": 60,
    },
    {
        "id": "synthesizer-1",
        "model": "Qwen/Qwen3.5-2B",
        "system": "You are a technical writer. Be concise.",
        "prompt": "Summarize: JWT API built, security reviewed, code validated. Final status?",
        "max_tokens": 80,
    },
    {
        "id": "vision-1",
        "model": "Qwen/Qwen3.5-0.8B",
        "system": "You are a helpful assistant.",
        "prompt": "Describe a good REST API design in 2 sentences.",
        "max_tokens": 60,
    },
]

SEPARATOR = "=" * 60

async def test_agent(agent: dict) -> dict:
    aid = agent["id"]
    model_id = agent["model"]
    print(f"\n{SEPARATOR}", flush=True)
    print(f"[{aid}] model={model_id}", flush=True)
    print(f"VRAM before: {_vram_allocated_gb():.2f} GB", flush=True)

    provider = TransformersProvider(model_id)
    t0 = time.time()
    tokens = []

    try:
        async for token in provider.generate(
            prompt=agent["prompt"],
            system_prompt=agent["system"],
            max_tokens=agent["max_tokens"],
            temperature=0.0,
        ):
            tokens.append(token)
            sys.stdout.write(token)
            sys.stdout.flush()
    except Exception as e:
        print(f"\n[ERROR] {e}", flush=True)
        return {"id": aid, "ok": False, "error": str(e)}

    elapsed = time.time() - t0
    full = "".join(tokens)
    # 단어 기준 T/s (근사)
    word_count = len(full.split())
    tps = word_count / elapsed if elapsed > 0 else 0
    vram_after = _vram_allocated_gb()

    print(f"\n[{aid}] {elapsed:.1f}s | ~{tps:.1f} W/s | VRAM: {vram_after:.2f} GB", flush=True)

    # 모델 언로드
    unload_model(model_id)
    gc.collect()
    torch.cuda.empty_cache()
    print(f"[{aid}] unloaded | VRAM: {_vram_allocated_gb():.2f} GB", flush=True)

    return {"id": aid, "ok": True, "elapsed": elapsed, "tps": tps, "vram": vram_after, "tokens": word_count}

async def main():
    print(SEPARATOR, flush=True)
    print("6-에이전트 E2E GPU 테스트", flush=True)
    print(f"CUDA: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}", flush=True)
    print(f"VRAM 초기: {_vram_allocated_gb():.2f} GB", flush=True)
    print(SEPARATOR, flush=True)

    results = []
    total_start = time.time()

    for agent in AGENTS:
        result = await test_agent(agent)
        results.append(result)

    total_elapsed = time.time() - total_start

    print(f"\n{SEPARATOR}", flush=True)
    print("결과 요약", flush=True)
    print(SEPARATOR, flush=True)
    ok_count = sum(1 for r in results if r.get("ok"))
    for r in results:
        if r.get("ok"):
            print(f"  {r['id']}: OK | {r['elapsed']:.1f}s | {r['tps']:.1f} W/s | {r['vram']:.2f} GB", flush=True)
        else:
            print(f"  {r['id']}: FAIL — {r.get('error', '?')}", flush=True)
    print(f"\n합계: {ok_count}/{len(AGENTS)} 성공 | 총 {total_elapsed:.1f}s", flush=True)
    print(f"최종 VRAM: {_vram_allocated_gb():.2f} GB", flush=True)

    if ok_count == len(AGENTS):
        print("\nSUCCESS - 전체 6-에이전트 E2E 통과!", flush=True)
    else:
        print(f"\nPARTIAL - {len(AGENTS) - ok_count}개 실패", flush=True)

asyncio.run(main())
