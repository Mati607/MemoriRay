from typing import List, Dict
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0" 

def choose_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

def load(model_id: str):
    device = choose_device()
    dtype = torch.float16 if device.type in ("cuda", "mps") else torch.float32

    tok = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    mdl = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=dtype,
        device_map="auto" if device.type in ("cuda", "mps") else None,
    )
    if device.type == "cpu":
        mdl = mdl.to(device)
    return mdl, tok, device

def generate_reply(model, tok, messages: List[Dict[str, str]], max_new_tokens: int = 256) -> str:
    """
    messages: [{"role":"system|user|assistant", "content":"..."}]
    Returns assistant text.
    """
    prompt = tok.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True, 
    )
    inputs = tok(prompt, return_tensors="pt").to(model.device)

    out = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        eos_token_id=tok.eos_token_id,
        pad_token_id=tok.eos_token_id,
    )
    text = tok.decode(out[0], skip_special_tokens=True)
    # Extract only the assistant's final part by removing the prompt prefix:
    return text[len(prompt):].strip()

def main():
    print("=" * 60)
    print(f"Loading model: {MODEL_ID}")
    model, tok, device = load(MODEL_ID)
    print(f"Ready. Using device: {device}")
    print("=" * 60)
    print("Type your message. Use /exit to quit.\n")

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "You are a helpful, concise assistant."}
    ]

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user:
            continue
        if user.lower() in {"/exit", "exit", "quit", "/quit"}:
            print("Bye!")
            break

        messages.append({"role": "user", "content": user})
        reply = generate_reply(model, tok, messages)
        print(f"Assistant: {reply}\n")
        messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
