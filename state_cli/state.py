#!/usr/bin/env python3
"""
State CLI — used by phase agents to report outcomes back to the pipeline.

Usage:
  state.py advance <project-id>
  state.py fail <project-id> [--reason TEXT]
  state.py reject <project-id> [--reason TEXT]
  state.py attention <project-id> --message TEXT
  state.py reset <project-id>
  state.py show <project-id>
  state.py list

Configuration:
  PIPELINE_ROOT — path to pipeline root (default: parent of this script's directory)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_ROOT = Path(os.environ.get("PIPELINE_ROOT", Path(__file__).parent.parent))
PROJECTS_DIR = PIPELINE_ROOT / "projects"

PHASES_BY_TYPE = {
    "production": ["research", "validate", "build", "review", "qa", "monetize", "package", "deploy", "notify"],
    "private":    ["build", "review", "qa", "package", "deploy", "notify"],
    "testing":    ["build", "review", "qa", "notify"],
}


def get_phases(app_type: str) -> list:
    return PHASES_BY_TYPE.get(app_type, PHASES_BY_TYPE["production"])


def find_state_file(project_id: str) -> Path:
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        print(f"ERROR: No state file found for project '{project_id}'", file=sys.stderr)
        print(f"       Expected: {path}", file=sys.stderr)
        sys.exit(1)
    return path


def load_state(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save_state(path: Path, state: dict) -> None:
    """Write atomically — write to temp file, then rename."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.rename(path)


def cmd_advance(project_id: str) -> None:
    path = find_state_file(project_id)
    state = load_state(path)

    if state["status"] == "rejected":
        print(f"ERROR: Project '{project_id}' is rejected — cannot advance.", file=sys.stderr)
        sys.exit(1)

    app_type = state.get("app_type", "production")
    phases = get_phases(app_type)
    current_phase = state["phase"]

    if current_phase not in phases:
        state["phase"] = "done"
        state["status"] = "complete"
        save_state(path, state)
        print(f"✅ Project '{project_id}' ({state['name']}) — COMPLETE (phase '{current_phase}' not in {app_type} sequence)")
        return

    idx = phases.index(current_phase)

    if current_phase not in state.get("phases_completed", []):
        state.setdefault("phases_completed", []).append(current_phase)

    if idx + 1 >= len(phases):
        state["phase"] = "done"
        state["status"] = "complete"
        save_state(path, state)
        print(f"✅ Project '{project_id}' ({state['name']}) — ALL PHASES COMPLETE. Status: complete")
    else:
        next_phase = phases[idx + 1]
        state["phase"] = next_phase
        state["status"] = "pending"
        state["error"] = None
        state["attention_message"] = None
        save_state(path, state)
        print(f"✅ Advanced '{project_id}' ({state['name']}): {current_phase} → {next_phase} [pending]")


def cmd_fail(project_id: str, reason: str) -> None:
    path = find_state_file(project_id)
    state = load_state(path)
    state["status"] = "failed"
    state["error"] = reason or "No reason given"
    save_state(path, state)
    print(f"❌ Failed '{project_id}' ({state['name']}) at phase '{state['phase']}': {state['error']}")


def cmd_reject(project_id: str, reason: str) -> None:
    path = find_state_file(project_id)
    state = load_state(path)
    state["status"] = "rejected"
    state["error"] = reason or "No reason given"
    save_state(path, state)
    print(f"🚫 Rejected '{project_id}' ({state['name']}): {state['error']}")


def cmd_attention(project_id: str, message: str) -> None:
    path = find_state_file(project_id)
    state = load_state(path)
    state["status"] = "attention"
    state["attention_message"] = message
    save_state(path, state)
    print(f"👀 Attention needed for '{project_id}' ({state['name']}) at phase '{state['phase']}': {message}")


def cmd_reset(project_id: str) -> None:
    """Reset a failed/attention project back to pending so the orchestrator retries."""
    path = find_state_file(project_id)
    state = load_state(path)
    if state["status"] not in ("failed", "attention", "in_progress"):
        print(f"ERROR: Can only reset projects with status 'failed', 'attention', or 'in_progress'. "
              f"Current status: '{state['status']}'", file=sys.stderr)
        sys.exit(1)
    state["status"] = "pending"
    state["error"] = None
    state["attention_message"] = None
    save_state(path, state)
    print(f"🔄 Reset '{project_id}' ({state['name']}) to pending at phase '{state['phase']}'")


def cmd_show(project_id: str) -> None:
    path = find_state_file(project_id)
    state = load_state(path)
    print(json.dumps(state, indent=2))


def cmd_list() -> None:
    files = sorted(PROJECTS_DIR.glob("*.json"))
    if not files:
        print("No projects found.")
        return

    print(f"{'ID':<40} {'NAME':<25} {'TYPE':<12} {'PHASE':<12} {'STATUS':<12} {'UPDATED'}")
    print("-" * 120)
    for f in files:
        try:
            state = load_state(f)
            updated = state.get("updated_at", "")[:16]
            name = state.get("name", "")[:23]
            pid = state.get("id", f.stem)[:38]
            app_type = state.get("app_type", "?")[:10]
            phase = state.get("phase", "")[:10]
            status = state.get("status", "")[:10]
            print(f"{pid:<40} {name:<25} {app_type:<12} {phase:<12} {status:<12} {updated}")
        except Exception as e:
            print(f"{f.stem:<40} [ERROR reading file: {e}]")


def main():
    parser = argparse.ArgumentParser(
        description="Agent Pipeline State CLI — used by phase agents to update project state."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_advance = subparsers.add_parser("advance", help="Mark current phase done, move to next")
    p_advance.add_argument("project_id")

    p_fail = subparsers.add_parser("fail", help="Mark project as failed at current phase")
    p_fail.add_argument("project_id")
    p_fail.add_argument("--reason", default="", help="Reason for failure")

    p_reject = subparsers.add_parser("reject", help="Permanently reject a project")
    p_reject.add_argument("project_id")
    p_reject.add_argument("--reason", default="", help="Reason for rejection")

    p_attention = subparsers.add_parser("attention", help="Flag project as needing human decision")
    p_attention.add_argument("project_id")
    p_attention.add_argument("--message", required=True, help="Message for the operator")

    p_reset = subparsers.add_parser("reset", help="Reset failed/attention/in_progress project back to pending")
    p_reset.add_argument("project_id")

    p_show = subparsers.add_parser("show", help="Print project state as JSON")
    p_show.add_argument("project_id")

    subparsers.add_parser("list", help="List all projects")

    args = parser.parse_args()

    if args.command == "advance":
        cmd_advance(args.project_id)
    elif args.command == "fail":
        cmd_fail(args.project_id, args.reason)
    elif args.command == "reject":
        cmd_reject(args.project_id, args.reason)
    elif args.command == "attention":
        cmd_attention(args.project_id, args.message)
    elif args.command == "reset":
        cmd_reset(args.project_id)
    elif args.command == "show":
        cmd_show(args.project_id)
    elif args.command == "list":
        cmd_list()


if __name__ == "__main__":
    main()
