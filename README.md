# Deeplurk™ — research problem discovery

Deeplurk explores a workflow for finding specific, evidenced research problems in public technical communities, checking prior work, and supporting bounded experimental decisions. This is a research prototype and design bundle, not a production service.

The proposed workflow is: SciencePal helps plan a task; a local OpenClaw agent browses authorized sources read-only; evidence and candidate problems are recorded; model scores and transparent rules support review. The semantic routing design describes community profiles and retrieval. Its end-to-end integration and comparative benefit have not been established.

## What is here

- `routing/`: actual project JSON Schema, fictional complete bundle, offline validator and negative tests. No real community data is included.
- `templates/`: task template and supervisor acceptance contract; the actual SciencePal-to-OpenClaw supervisor integration is not provided.
- `embedding/`: a small portable adaptation of the earlier CPU BGE encoder; not a production routing service.
- `scoring/`: actual bounded-context adapter, frozen novelty mapping and selected canonical GPU runtime routines, plus a new unverified portable wrapper.
- `supervisor/`: historical experimental supervisor skeleton with live entry point disabled pending review.
- `experiments/p0370/`: a post-hoc experiment script and aggregate results with the original setup's limitations.
- `docs/`: scope, model and experiment boundaries, provenance and sanitization notes.

## Offline validation

Python 3.11 or later; install `requirements.txt`, then run:

```sh
python routing/validate_bundle.py routing/example-fictional.jsonl
python routing/test_validation.py
```

The tests validate record structure and selected consistency rules; they do not establish that a site is accessible, authorized, truthful or scientifically valuable. All sample records are fictional.

Embedding requires separate model weights and optional dependencies; see `embedding/README.md`. No credentials, weights, raw chats, user data, browser profiles, original experiment logs or git history are shipped. Do not treat score model outputs as success probabilities or evidence of novelty.
