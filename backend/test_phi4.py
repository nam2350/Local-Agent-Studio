"""Phi-4-mini E2E GPU 추론 테스트"""
import torch, time, asyncio, sys, os
os.chdir(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

from providers.transformers_provider import TransformersProvider, _vram_allocated_gb, unload_model

print("=== Phi-4-mini E2E 테스트 ===")
print(f"VRAM 초기: {_vram_allocated_gb():.2f} GB")
sys.stdout.flush()

async def test():
    provider = TransformersProvider("microsoft/Phi-4-mini-instruct")
    t0 = time.time()
    result = []
    print("모델 로딩 중...", flush=True)
    async for token in provider.generate(
        prompt="Review: def add(a,b): return a+b. Is it correct?",
        system_prompt="You are a code validator. Be brief.",
        max_tokens=60,
        temperature=0.0,
    ):
        result.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()
    elapsed = time.time() - t0
    full = "".join(result)
    tps = len(full.split()) / elapsed if elapsed > 0 else 0
    print(f"\n--- 완료: {elapsed:.1f}s, ~{tps:.1f} T/s | VRAM: {_vram_allocated_gb():.2f} GB ---")
    unload_model("microsoft/Phi-4-mini-instruct")
    import gc; gc.collect(); torch.cuda.empty_cache()
    print(f"언로드 후 VRAM: {_vram_allocated_gb():.2f} GB")
    print("SUCCESS!")

asyncio.run(test())
