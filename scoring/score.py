"""Experimental portable adaptation of the canonical SRM batch worker.

The exact model and upstream prompt template must be provided locally. Run an
independent numerical comparison before relying on results in a new environment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')


def rino_probs(raw, model):
    import numpy as np
    from scipy.special import expit
    z = (np.asarray(raw, dtype=float) - model['mean']) / model['sd']
    cdf = expit(np.asarray(model['thresholds'])[None, :] - model['beta'] * z[:, None])
    probs = np.diff(np.column_stack([np.zeros(len(z)), cdf, np.ones(len(z))]), axis=1)
    probs = np.maximum(probs, 1e-12)
    return probs / probs.sum(axis=1, keepdims=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--template', required=True, help='upstream inference.py, obtained separately')
    parser.add_argument('--input', required=True, help='JSON with context and hypothesis')
    args = parser.parse_args()
    template = Path(args.template)
    if hashlib.sha256(template.read_bytes()).hexdigest() != '4bc1e541b1f978eda8642c42372558b080cf321bdff3a2b811bb28eaf1d6de2a':
        raise ValueError('Template differs from the original experiment; inspect and compare before proceeding')
    os.environ['SRM_TEMPLATE'] = str(template)
    import torch
    from accelerate.hooks import remove_hook_from_module, add_hook_to_module, AlignDevicesHook
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, BitsAndBytesConfig
    import transformers.modeling_utils as mu
    from calibration_adapter import prepare
    from runtime import raw, blocked_math, install_gpu_leaves

    if not torch.cuda.is_available():
        raise RuntimeError('This historical NF4 hybrid protocol requires a compatible CUDA GPU')
    item = json.loads(Path(args.input).read_text(encoding='utf-8'))
    tok = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True, trust_remote_code=False)
    tok.padding_side = 'left'
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    _, ids, report = prepare(tok, 'candidate', item['context'], item['hypothesis'])
    torch.manual_seed(42); torch.set_num_threads(4)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.allow_fp16_bf16_reduction_math_sdp(False)
    device_map = {'model.embed_tokens': 'cpu', 'model.layers.0': 'cpu', 'model.layers.1': 'cpu', 'model.norm': 0, 'score': 0}
    device_map.update({f'model.layers.{i}': 0 for i in range(2, 40)})
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16, llm_int8_enable_fp32_cpu_offload=True)
    warmup, safe = mu.caching_allocator_warmup, mu.safe_open
    def read_on_demand(*a, **kw):
        kw['backend'] = 'pread'
        return safe(*a, **kw)
    mu.caching_allocator_warmup = lambda *a, **kw: None
    mu.safe_open = read_on_demand
    try:
        model = AutoModelForSequenceClassification.from_pretrained(args.model_dir, local_files_only=True, trust_remote_code=False, quantization_config=quant, device_map=device_map, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True, attn_implementation='sdpa')
    finally:
        mu.caching_allocator_warmup, mu.safe_open = warmup, safe
    for name in ('model.embed_tokens', 'model.layers.0', 'model.layers.1'):
        module = model.get_submodule(name)
        remove_hook_from_module(module, recurse=True)
        add_hook_to_module(module, AlignDevicesHook(execution_device='cpu', offload=False, io_same_device=True, place_submodules=True))
    model.eval(); model.config.use_cache = False
    if model.config.num_labels != 3:
        raise ValueError('Expected three SRM axes')
    handles = install_gpu_leaves(model)
    values, seconds = raw(model, ids, blocked_math)
    if any(r['counts']['pre'] != r['counts']['post'] for r in handles):
        raise RuntimeError('Unbalanced staged weight hooks')
    fit = json.loads((Path(__file__).parent / 'rino-fit-frozen.json').read_text(encoding='utf-8'))['fit']['model']
    probs = rino_probs([values[0]], fit)[0]
    expectation = sum((i + 1) * float(p) for i, p in enumerate(probs))
    print(json.dumps({'raw': dict(zip(('novelty', 'feasibility', 'probability'), values)), 'rino_probabilities': probs.tolist(), 'rino_expectation': expectation, 'rino_q': 2 * expectation - 1, 'adapter': report, 'seconds': seconds}))


if __name__ == '__main__':
    main()
