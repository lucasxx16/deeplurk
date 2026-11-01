# Supervisor acceptance contract — design only

This is a contract for a future reviewed implementation, not an executable supervisor. SciencePal can propose tasks and code; real OpenClaw commands, browser profile handling, stop mechanisms, model entry points, and export interfaces remain `NEEDS_PROBE`. Never guess an interface or move browser credentials into a cloud task.

- Before operation, constrain output to an approved working directory; verify the selected agent/profile identity and that it is idle.
- Record per-task identity, budget, states and receipts. Preserve successful, failed, blocked and unknown outcomes; an unknown dispatch must not be automatically retried.
- Keep tasks independent; one agent failure must not automatically stop unrelated tasks. Stop dispatch on an explicit stop and write checkpoint and exit status.
- Inspect generated code; run an offline dry run with no network, model or OpenClaw launch. Then conduct one authorized, read-only agent smoke test before scaling.
- Track attempted versus observed separately; an inaccessible source is not an empty source. Do not bypass login, rate limits or access restrictions. Do not post or message.
- Preserve raw model scores and versioned rules; uncertainty remains explicit. Human review handles conflicts and consequential decisions.
