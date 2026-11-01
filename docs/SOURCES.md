# Sources and rights

- `routing/` schema, fictional examples, validator and negative tests: copied from the Deeplurk platform evidence and semantic-routing design dated 2026-10-30; project-authored materials, no license grant inferred.
- `templates/browse-task.md`: adapted from Deeplurk task template v3; project-authored, no license grant inferred.
- `embedding/encode.py`: portable adaptation of the project BGE worker. It depends on separately obtained BAAI/bge-small-en-v1.5, PyTorch and Transformers; their own model and software licenses apply. No third-party weights or source code are redistributed here.
- `scoring/`: project calibration adapter, selected canonical runtime functions, and unchanged frozen RINo fit; wrapper newly adapted. SRM prompt template and weights are separately obtained upstream assets and are not bundled.
- `supervisor/`: historical project skeleton with live CLI disabled. `experiments/p0370/`: local analysis code and aggregate result. Original dataset and selection inputs are not distributed.
- `templates/supervisor-contract.md` and remaining documentation summarize project design and evidence. No license is assigned without the owner's decision.
- The package excludes upstream issue text, datasets, papers and outputs whose redistribution permissions have not been established.
