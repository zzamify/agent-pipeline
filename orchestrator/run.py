#!/usr/bin/env python3
"""
Agent Pipeline Orchestrator — pure state machine, no LLM.

Reads all project state files, decides what needs to happen next,
and outputs a JSON action plan for the active agent to act on.

Output (stdout): JSON action plan
Errors (stderr): Human-readable diagnostics

Exit codes:
  0 — success (even if no work to do)
  1 — fatal error (e.g., projects directory not found)

Configuration:
  PIPELINE_ROOT — path to pipeline root (default: parent of this script's directory)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PIPELINE_ROOT = Path(os.environ.get("PIPELINE_ROOT", Path(__file__).parent.parent))
PROJECTS_DIR = PIPELINE_ROOT / "projects"
PROMPTS_DIR = PIPELINE_ROOT / "prompts"

# Phase sequences per project type.
PHASES_BY_TYPE = {
    "production": ["research", "validate", "build", "review", "qa", "monetize", "package", "deploy", "notify"],
    "private":    ["build", "review", "qa", "package", "deploy", "notify"],
    "testing":    ["build", "review", "qa", "notify"],
}

# Phases that pause the pipeline and surface as attention items.
# The operator must manually advance after reviewing.
ATTENTION_PHASES = {"monetize"}


def get_phases(app_type: str) -> list:
    return PHASES_BY_TYPE.get(app_type, PHASES_BY_TYPE["production"])


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_project(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"WARNING: Could not read {path}: {e}", file=sys.stderr)
        return None


def save_project(path: Path, state: dict) -> None:
    state["updated_at"] = now_iso()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.rename(path)


def prompt_path(phase: str) -> Path:
    return PROMPTS_DIR / f"{phase}.md"


def mark_in_progress(path: Path, state: dict) -> None:
    state["status"] = "in_progress"
    save_project(path, state)


def next_phase(current: str, app_type: str) -> str | None:
    phases = get_phases(app_type)
    if current not in phases:
        return None
    idx = phases.index(current)
    return phases[idx + 1] if idx + 1 < len(phases) else None


def advance_phase(path: Path, state: dict) -> str:
    """Advance a 'done' project to next phase, returns new phase."""
    current = state["phase"]
    app_type = state.get("app_type", "production")

    if current not in state.get("phases_completed", []):
        state.setdefault("phases_completed", []).append(current)

    nxt = next_phase(current, app_type)
    if nxt is None:
        state["phase"] = "done"
        state["status"] = "complete"
        save_project(path, state)
        return "done"

    state["phase"] = nxt
    state["status"] = "pending"
    state["error"] = None
    state["attention_message"] = None
    save_project(path, state)
    return nxt


def main():
    if not PROJECTS_DIR.exists():
        print(json.dumps({
            "timestamp": now_iso(),
            "error": f"Projects directory not found: {PROJECTS_DIR}",
            "dispatches": [],
            "attention": [],
            "summary": "ERROR: projects directory missing"
        }, indent=2))
        sys.exit(1)

    project_files = sorted(PROJECTS_DIR.glob("*.json"))

    dispatches = []
    attention_items = []
    skipped = []

    for pf in project_files:
        state = load_project(pf)
        if state is None:
            continue

        project_id = state.get("id", pf.stem)
        project_name = state.get("name", project_id)
        app_type = state.get("app_type", "production")
        status = state.get("status", "")
        phase = state.get("phase", "")

        # Terminal / skip states
        if status in ("rejected", "complete"):
            skipped.append({"id": project_id, "reason": status})
            continue

        if status == "failed":
            attention_items.append({
                "project_id": project_id,
                "project_name": project_name,
                "phase": phase,
                "app_type": app_type,
                "status": "failed",
                "message": f"FAILED at phase '{phase}': {state.get('error', 'No error recorded')}",
            })
            continue

        if status == "in_progress":
            # Stall detection: if in_progress > 75 min, reset to pending for auto-retry
            updated_at_str = state.get("updated_at", "")
            stalled = False
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - updated_at > timedelta(minutes=75):
                    stalled = True
            except Exception:
                pass

            if stalled:
                print(f"INFO: Project '{project_id}' stalled in_progress — resetting to pending", file=sys.stderr)
                state["status"] = "pending"
                state["notes"] = state.get("notes", "") + f"\n[{now_iso()}] Auto-reset from stalled in_progress"
                save_project(pf, state)
                # Fall through to dispatch below
            else:
                skipped.append({"id": project_id, "reason": "in_progress"})
                continue

        if status == "attention":
            attention_items.append({
                "project_id": project_id,
                "project_name": project_name,
                "phase": phase,
                "app_type": app_type,
                "status": "attention",
                "message": state.get("attention_message", "No message provided"),
            })
            continue

        # Handle "done" status: advance to next phase
        if status == "done":
            new_phase = advance_phase(pf, state)
            if new_phase == "done":
                skipped.append({"id": project_id, "reason": "complete"})
                continue
            phase = new_phase
            status = "pending"

        # Dispatch pending projects
        if status == "pending":
            prompt_file = prompt_path(phase)
            if not prompt_file.exists():
                print(f"WARNING: No prompt file for phase '{phase}' at {prompt_file}", file=sys.stderr)
                attention_items.append({
                    "project_id": project_id,
                    "project_name": project_name,
                    "phase": phase,
                    "app_type": app_type,
                    "status": "error",
                    "message": f"Missing prompt file for phase '{phase}'. Cannot dispatch.",
                })
                continue

            mark_in_progress(pf, state)

            dispatches.append({
                "project_id": project_id,
                "project_name": project_name,
                "app_type": app_type,
                "phase": phase,
                "state_file": str(pf),
                "project_dir": state.get("project_dir", ""),
                "description": state.get("description", ""),
                "prompt_file": str(prompt_file),
            })

    parts = []
    if dispatches:
        parts.append(f"{len(dispatches)} dispatch(es)")
    if attention_items:
        parts.append(f"{len(attention_items)} attention item(s)")
    if not dispatches and not attention_items:
        parts.append("nothing to do")

    result = {
        "timestamp": now_iso(),
        "dispatches": dispatches,
        "attention": attention_items,
        "skipped_count": len(skipped),
        "summary": ", ".join(parts),
        "state_cli": f"python3 '{PIPELINE_ROOT}/state_cli/state.py'",
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
