#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deeplurk local supervisor (skeleton, dry-run first).

状态机
  运行级: CREATED → VALIDATING → DRY_RUN_PASSED → READY → RUNNING → DRAINING → COMPLETED/PARTIAL/FAILED/CANCELLED
  任务级: PENDING → CLAIMED → RUNNING → DONE/EMPTY/BLOCKED/FAILED/UNKNOWN

只读浏览；不写帖子、不登录新账号。所有外部动作都通过 openclaw CLI，sup 自身不联网。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # PyYAML 缺失时退化为简易 YAML：只支持本项目 config.example.yaml 的 flat 结构
    yaml = None


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def jl_append(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_simple_yaml(path):
    """极简 YAML 读取：支持 key: value、二级 key、list of dict（- key: v）。"""
    root, cur, stack = {}, None, []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if line.startswith("- "):
            item = {}
            k, _, v = line[2:].partition(":")
            item[k.strip()] = v.strip().strip('"')
            if isinstance(cur, list):
                cur.append(item)
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip().strip('"')
        if v == "":
            # 可能是 dict 或 list
            nxt = {"@pending": True}
            root[k] = nxt
            cur = nxt
            stack.append(k)
        else:
            if isinstance(cur, dict):
                cur[k] = v
            else:
                root[k] = v
    # 把带列表的 section 修成 list
    for k, v in list(root.items()):
        if isinstance(v, dict) and "@pending" in v:
            root[k] = {kk: vv for kk, vv in v.items() if kk != "@pending"}
    return root


def read_config(path):
    text = Path(path).read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text)
    return load_simple_yaml(path)


class Supervisor:
    def __init__(self, pkg, cfg, dry_run=False, smoke=0):
        self.pkg = Path(pkg)
        self.cfg = cfg
        self.dry = dry_run
        self.smoke = smoke
        run_rel = cfg.get("run_dir", "runs/UNSET")
        self.run_dir = self.pkg / run_rel
        for sub in ("checkpoints", "raw"):
            (self.run_dir / sub).mkdir(parents=True, exist_ok=True)
        self.events = self.run_dir / "events.jsonl"
        self.receipts = self.run_dir / "receipts.jsonl"
        self.state = "CREATED"

    # ---------- 基础设施 ----------
    def stop_requested(self):
        return (self.pkg / "STOP").exists() or (self.run_dir / "STOP").exists()

    def emit(self, kind, **kw):
        jl_append(self.events, {"ts": now(), "kind": kind, **kw})

    def set_state(self, new, reason=""):
        self.emit("run_state", frm=self.state, to=new, reason=reason)
        self.state = new

    # ---------- 校验 ----------
    def validate(self):
        self.set_state("VALIDATING")
        tasks = [json.loads(l) for l in (self.pkg / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        assert tasks, "tasks.jsonl 为空"
        ids = [t["task_id"] for t in tasks]
        assert len(ids) == len(set(ids)), "task_id 重复"
        src = (self.pkg / "sources.csv").read_text(encoding="utf-8")
        for t in tasks:
            assert t["source_id"] in src, f'{t["task_id"]} 的 source_id 不在 sources.csv'
        self.emit("validated", tasks=len(tasks))
        return tasks

    # ---------- 任务派发 ----------
    def prompt_for(self, task, agent):
        return f"""You are agent {agent['agent_id']} in run {self.cfg.get('run_id','?')}, task {task['task_id']}.
Read-only browsing. Do not post, reply, register, or bypass any paywall/captcha.

SOURCE: {task['source_id']} — open the entry URL from sources.csv for this source.
DISCIPLINE: {task['discipline_id']} ({task['discipline_name']})
SEARCH TERMS: {', '.join(task['query_terms'])}
GOAL: {task['goal']}
EXPECTED EVIDENCE: {task['expected_evidence']}

Rules:
- only record what you actually saw; if nothing, return status EMPTY with the exact queries you tried;
- if login/captcha/rate-limit stops you, return status BLOCKED with the exact page text;
- keep at most 5 candidates; close every tab you opened.

Return ONE JSON object:
{{"status":"DONE|EMPTY|BLOCKED|FAILED","candidates":[{{"title":"","problem_statement":"","problem_type":"research_method|technical|teaching|career|other|UNKNOWN","url":"","excerpt":"","observed_at":"","access_status":"readable|login|captcha|rate_limited|unavailable"}}],"queries":[],"tabs_closed":true,"notes":""}}
"""

    def dispatch(self, task, agent):
        o = self.cfg["openclaw"]
        turn_id = f"{task['task_id']}-{uuid.uuid4().hex[:8]}"
        prompt_file = self.run_dir / "raw" / f"{turn_id}.prompt.md"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(self.prompt_for(task, agent), encoding="utf-8")

        cmd = [o["node"], o["entry"], "agent", "exec",
               "--config", o["config_path"],
               "--cwd", str(self.run_dir),
               "--state-dir", agent["state_dir"],
               "--message-file", str(prompt_file),
               "--timeout", str(int(self.cfg["limits"]["turn_timeout_s"])),
               "--json"]
        if o.get("model") and o["model"] != "NEEDS_PROBE":
            cmd += ["--model", o["model"]]

        started = time.time()
        rec = {"turn_id": turn_id, "task_id": task["task_id"], "agent_id": agent["agent_id"],
               "source_id": task["source_id"], "started_at": now(), "argv_len": len(" ".join(cmd))}
        if self.dry:
            rec.update(dry_run=True, status="DRY_RUN", receipt="unavailable")
            jl_append(self.receipts, rec)
            return {"ok": True, "dry_run": True}

        env = dict(os.environ)
        env["OPENCLAW_STATE_DIR"] = agent["state_dir"]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=float(self.cfg["limits"]["turn_timeout_s"]) + 60,
                               env=env)
            out = p.stdout or ""
            (self.run_dir / "raw" / f"{turn_id}.stdout.json").write_text(out, encoding="utf-8")
            payload = {}
            try:
                payload = json.loads(out[out.index("{"):]) if "{" in out else {}
            except Exception:
                payload = {}
            rec.update(finished_at=now(), elapsed_s=round(time.time() - started, 1),
                       exit_code=p.returncode, ok=bool(payload.get("ok", p.returncode == 0)),
                       receipt="stdout" if out else "unavailable",
                       error=(p.stderr or "")[:400])
            jl_append(self.receipts, rec)
            return payload or {"ok": p.returncode == 0}
        except subprocess.TimeoutExpired:
            rec.update(finished_at=now(), elapsed_s=round(time.time() - started, 1),
                       status="TIMEOUT", ok=False, receipt="unknown")
            jl_append(self.receipts, rec)
            return {"ok": False, "timeout": True}

    def run_task(self, task, agent):
        self.emit("task_state", task_id=task["task_id"], frm="PENDING", to="CLAIMED")
        self.emit("task_state", task_id=task["task_id"], frm="CLAIMED", to="RUNNING")
        res = self.dispatch(task, agent)
        status = "UNKNOWN"
        if res.get("dry_run"):
            status = "DRY_RUN"
        elif res.get("timeout"):
            status = "UNKNOWN"
        elif res.get("ok"):
            body = res.get("result") or res.get("output") or res
            text = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body
            for s in ("BLOCKED", "EMPTY", "DONE"):
                if f'"status": "{s}"' in text or f'"status":"{s}"' in text:
                    status = s
                    break
        else:
            status = "FAILED"
        self.emit("task_state", task_id=task["task_id"], frm="RUNNING", to=status)
        cp = self.run_dir / "checkpoints" / f'{task["task_id"]}.json'
        cp.write_text(json.dumps({"task_id": task["task_id"], "agent_id": agent["agent_id"],
                                  "status": status, "at": now()}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
        return status

    # ---------- 主流程 ----------
    def run(self):
        tasks = self.validate()
        self.set_state("DRY_RUN_PASSED" if self.dry else "READY", "validation ok")
        if self.dry:
            assigned = {}
            for t in tasks:
                a = self.cfg["agents"][hash(t["source_id"]) % len(self.cfg["agents"])]
                assigned.setdefault(a["agent_id"], []).append(t["task_id"])
            self.emit("dry_run_plan", assignment=assigned, tasks=len(tasks))
            self.set_state("COMPLETED", "dry run only")
            print(json.dumps({"dry_run": True, "tasks": len(tasks), "assignment": assigned},
                             ensure_ascii=False, indent=1))
            return 0

        self.set_state("RUNNING")
        todo = tasks[: self.smoke] if self.smoke else tasks
        results = {}
        for i, t in enumerate(todo):
            if self.stop_requested():
                self.set_state("DRAINING", "STOP file")
                break
            agent = self.cfg["agents"][i % len(self.cfg["agents"])]
            for attempt in range(int(self.cfg["limits"]["max_retries"]) + 1):
                st = self.run_task(t, agent)
                if st in ("DONE", "EMPTY", "BLOCKED", "DRY_RUN"):
                    break
                self.emit("retry", task_id=t["task_id"], attempt=attempt + 1, status=st)
            results[t["task_id"]] = st
        self.set_state("DRAINING" if self.stop_requested() else "COMPLETED", "loop end")
        done = sum(1 for v in results.values() if v in ("DONE", "EMPTY"))
        self.emit("summary", results=results, done=done, total=len(todo))
        print(json.dumps({"state": self.state, "results": results}, ensure_ascii=False, indent=1))
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--config", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smoke", type=int, default=0, help="只跑前 N 个任务")
    a = ap.parse_args()
    pkg = Path(a.package)
    cfg_path = Path(a.config) if a.config else pkg / "config.yaml"
    if not cfg_path.exists():
        print(f"缺少 {cfg_path}（先复制 config.example.yaml）", file=sys.stderr)
        return 2
    if not a.dry_run:
        raise SystemExit("Historical skeleton: live dispatch disabled pending interface and safety review")
    cfg = read_config(cfg_path)
    return Supervisor(pkg, cfg, dry_run=a.dry_run, smoke=a.smoke).run()


if __name__ == "__main__":
    sys.exit(main())
