# BGE encoding adaptation

The earlier experiment used BAAI/bge-small-en-v1.5 at revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, locally on CPU, with Transformers and 384-dimensional vectors. The original encoded `context + two newlines + hypothesis`; it used CLS pooling, normalised each 510-token chunk, computed a token-count-weighted average and normalised again. The script here adapts that method for supplied text. It is not the original audit/checkpoint worker and does not claim exact reproducibility without model-file hashes and the original audit inputs. Model weights are not included.

Install the optional requirements and obtain model files separately under their own license. For a verified local directory:

```sh
python embedding/encode.py --model-dir ./models/bge-small-en-v1.5 --text "example research question"
```

Offline loading is enforced. Record the actual revision and file hashes yourself; a directory name alone does not establish provenance. Empty inputs are rejected. Routing requires a fixed shared model, revision and text template, index rebuilds when any change, access constraints, and independent multilingual evaluation. Those parts remain design work.
