# Historical local supervisor skeleton

`historical_supervisor.py` is the real local experimental skeleton, copied and modified to disable live dispatch at the command-line entry point. Its unused live path guessed OpenClaw arguments, has insufficient path containment and profile checks, and retries `UNKNOWN` after timeout. It must not be imported and called as a live dispatcher. Its dry run is historical planning code, not evidence of safe operation. The acceptance contract in `templates/` lists work required before implementation.
