"""Phi-4-mini 동기 방식 간단 추론 테스트"""
import sys, os, time
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

print("=== Phi-4-mini 동기 추론 테스트 ===", flush=True)

path = "models/validator/microsoft--Phi-4-mini-instruct"
print(f"모델 경로: {path}", flush=True)
print(f"CUDA 가용: {torch.cuda.is_available()}", flush=True)
if torch.cuda.is_available():
    print(f"VRAM: {torch.cuda.memory_allocated()/1e9:.2f}GB allocated", flush=True)

t0 = time.time()
print("Tokenizer 로딩...", flush=True)
tokenizer = AutoTokenizer.from_pretrained(path)
print(f"Tokenizer 완료 ({time.time()-t0:.1f}s)", flush=True)

t1 = time.time()
print("Model 로딩...", flush=True)
model = AutoModelForCausalLM.from_pretrained(
    path,
    device_map="auto",
    dtype=torch.float16,
    attn_implementation="sdpa",
)
print(f"Model 완료 ({time.time()-t1:.1f}s) | VRAM: {torch.cuda.memory_allocated()/1e9:.2f}GB", flush=True)

# 간단한 추론
messages = [
    {"role": "system", "content": "You are a code validator. Be very brief."},
    {"role": "user", "content": "Is this correct? def add(a,b): return a+b"},
]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to(model.device)

print(f"Input tokens: {inputs['input_ids'].shape[1]}", flush=True)
print("추론 중...", flush=True)

t2 = time.time()
with torch.no_grad():
    out = model.generate(
        **inputs,
        max_new_tokens=50,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
elapsed = time.time() - t2

new_tokens = out[0][inputs['input_ids'].shape[1]:]
result = tokenizer.decode(new_tokens, skip_special_tokens=True)
print(f"추론 결과: {result}", flush=True)
print(f"생성 시간: {elapsed:.1f}s | {len(new_tokens)/elapsed:.1f} T/s", flush=True)
print("SUCCESS!", flush=True)
