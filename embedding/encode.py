"""Portable CPU adaptation of the project's chunked CLS pooling experiment."""
import argparse
import json
import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def encode(text, model_dir):
    if not text.strip():
        raise ValueError("text must not be empty")
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    model = AutoModel.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False, use_safetensors=True).to("cpu").eval()
    ids = tokenizer.encode(text, add_special_tokens=False, truncation=False)
    if not ids:
        raise ValueError("text produced no tokens")
    chunks = [ids[i:i + 510] for i in range(0, len(ids), 510)]
    vectors = []
    for chunk in chunks:
        inputs = tokenizer.prepare_for_model(chunk, add_special_tokens=True, truncation=False, return_tensors="pt")
        inputs = {k: (v.unsqueeze(0) if v.ndim == 1 else v) for k, v in inputs.items()}
        with torch.inference_mode():
            vector = model(**inputs).last_hidden_state[:, 0, :].squeeze(0).float()
        if not torch.isfinite(vector).all():
            raise ValueError("model returned a non-finite vector")
        vectors.append(torch.nn.functional.normalize(vector, dim=0))
    pooled = sum(v * len(c) for v, c in zip(vectors, chunks)) / len(ids)
    return torch.nn.functional.normalize(pooled, dim=0).tolist()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    print(json.dumps(encode(args.text, args.model_dir)))
