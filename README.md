# agent-pipeline

A minimal, dependency-free pipeline framework for multi-phase AI agent workflows — with human-in-the-loop gates, automatic retry, and stall detection.

The orchestrator has **zero AI in it**. It's a pure Python state machine that reads JSON files, decides what runs next, and outputs a dispatch plan. Your agents handle the intelligence. The pipeline handles the coordination.

---

## The Problem

Running AI agents through multi-step pipelines is messy. Agents stall. Phases fail. You need human sign-off on some decisions but not others. You want retries without infinite loops. You want visibility into what's happening.

Most solutions reach for message queues, databases, or LLM-based orchestrators. This doesn't. It's just files, a state machine, and a CLI. No broker, no database, no framework — just Python stdlib and `jq`-free bash.

---

## How It Works

Each project is a single JSON file in `projects/`. The orchestrator reads all of them on every run, decides what's ready to dispatch, and outputs a JSON action plan:

```json
{
  "dispatches": [
    {
      "project_id": "my-app-20240315",
      "phase": "build",
      "prompt_file": "/path/to/prompts/build.md",
      "project_dir": "/path/to/my-app",
      "state_cli": "python3 /path/to/state_cli/state.py"
    }
  ],
  "attention": [],
  "summary": "1 dispatch(es)"
}
```

Your agent system reads that JSON and runs the phase. When the phase completes, the agent calls `state.py advance` to move to the next phase. On failure, it calls `state.py fail`. On a decision that needs a human, it calls `state.py attention`.

The pipeline never calls an agent directly. Agents never know about the pipeline beyond the state CLI. Clean separation.

---

## Pipeline Types

Three built-in sequences — easily customizable in `orchestrator/run.py` and `state_cli/state.py`:

| Type | Phases |
|------|--------|
| `production` | research → validate → build → review → qa → monetize → package → deploy → notify |
| `private` | build → review → qa → package → deploy → notify |
| `testing` | build → review → qa → notify |

---

## Features

- **No dependencies** — pure Python stdlib + bash
- **Stall detection** — projects stuck `in_progress` > 75 minutes are auto-reset to `pending`
- **Atomic writes** — state files are written via tmp → rename, never partially written
- **Human gates** — `attention` status pauses the pipeline until you manually advance
- **Auto-retry** — failed phases can be reset with `state.py reset` and will re-dispatch
- **Multiple project types** — different phase sequences for different workflows
- **PIPELINE_ROOT** — single env var configures everything; no hardcoded paths

---

## Requirements

- Python 3.10+ (stdlib only)
- bash
- git (used by phase agents, not the orchestrator itself)

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/agent-pipeline.git
cd agent-pipeline
chmod +x add-idea.sh status.sh
```

No install step. No virtualenv. No dependencies to pin.

---

## Quick Start

**1. Queue a project:**
```bash
bash add-idea.sh "My App" "A tool that does X for Y users"
# → creates projects/my-app-20240315.json
```

**2. Run the orchestrator:**
```bash
python3 orchestrator/run.py
```

Output (JSON) tells your agent what to do next:
```json
{
  "dispatches": [{ "phase": "research", "project_id": "my-app-20240315", ... }],
  "summary": "1 dispatch(es)"
}
```

**3. Your agent runs the phase**, reads the prompt from `prompt_file`, does the work, then reports back:
```bash
# Phase succeeded
python3 state_cli/state.py advance my-app-20240315

# Phase failed
python3 state_cli/state.py fail my-app-20240315 --reason "Build error: missing dependency"

# Phase needs human decision
python3 state_cli/state.py attention my-app-20240315 --message "Pricing decision needed. Options: A, B, C."
```

**4. Check status:**
```bash
bash status.sh
```

```
Agent Pipeline — Project Status

ID                                       NAME                      PHASE        STATUS
────────────────────────────────────────────────────────────────────────────────────────────────────────
my-app-20240315                          My App                    build        in_progress

Summary: in_progress: 1
```

---

## State Transitions

```
pending → in_progress → done → [next phase pending]
                      ↘ failed     (resetable)
                      ↘ attention  (resetable, human gate)
                      ↘ rejected   (terminal)
[last phase done] → complete       (terminal)
```

---

## State CLI Reference

```bash
python3 state_cli/state.py advance   <project-id>                    # move to next phase
python3 state_cli/state.py fail      <project-id> --reason "..."    # mark failed
python3 state_cli/state.py reject    <project-id> --reason "..."    # permanently reject
python3 state_cli/state.py attention <project-id> --message "..."   # pause for human
python3 state_cli/state.py reset     <project-id>                   # retry failed/attention
python3 state_cli/state.py show      <project-id>                   # print state as JSON
python3 state_cli/state.py list                                      # list all projects
```

---

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `PIPELINE_ROOT` | parent of script dir | Root of the pipeline installation |
| `PROJECTS_ROOT` | `$HOME/projects` | Where agent projects are created on disk |

Both the orchestrator and state CLI auto-detect `PIPELINE_ROOT` from `__file__` if not set. You typically don't need to set anything.

---

## Prompt Templates

The `prompts/` directory contains phase prompt templates. Each prompt is a markdown file that gets injected with project context (id, name, type, directory, description, state CLI path) and handed to a phase agent.

Included templates cover a full product-build pipeline: research, validate, build, review, QA, monetize, package, deploy, notify. Adapt them to your workflow — the orchestrator doesn't care what's in them, it just passes the file path to your agent.

Key convention in every prompt: the last section is `## PROJECT CONTEXT` with variables like `PROJECT_ID`, `PROJECT_DIR`, `STATE_CLI`. Your agent dispatch layer substitutes these before passing the prompt to the model.

---

## Customizing Phases

Edit the `PHASES_BY_TYPE` dict in both `orchestrator/run.py` and `state_cli/state.py`:

```python
PHASES_BY_TYPE = {
    "production": ["research", "validate", "build", "review", "qa", "monetize", "package", "deploy", "notify"],
    "private":    ["build", "review", "qa", "package", "deploy", "notify"],
    "testing":    ["build", "review", "qa", "notify"],
    # Add your own:
    "data":       ["ingest", "clean", "analyze", "report"],
}
```

Add a matching prompt file in `prompts/` and you're done.

---

## Why Not Use [X]?

- **LangGraph / CrewAI / AutoGen**: Great for complex agent graphs. Overkill when you want a linear pipeline with a few human gates and simple retry logic. Also: Python dependencies, framework churn, debugging inside abstractions.
- **Celery / Redis**: Correct tool for distributed task queues. Wrong tool when one machine and one file system is enough.
- **LLM-based orchestrators**: The orchestrator deciding what to run next is a reliability risk. A pure state machine never hallucinates the next phase.

This exists for the case where you want a durable, debuggable, zero-dependency pipeline that you fully understand and can modify in an afternoon.

---

## Project State Schema

Each project file (`projects/<id>.json`) contains:

```json
{
  "id": "my-app-20240315",
  "name": "My App",
  "description": "A tool that does X",
  "app_type": "production",
  "phase": "build",
  "status": "pending",
  "created_at": "2024-03-15T10:00:00+00:00",
  "updated_at": "2024-03-15T10:05:00+00:00",
  "phases_completed": ["research", "validate"],
  "project_dir": "/home/user/projects/my-app",
  "notes": "",
  "error": null,
  "attention_message": null,
  "artifacts": {}
}
```

It's just a file. Inspect it with `cat`. Edit it with any text editor. No migration scripts, no schema versions.

---

## License

MIT
