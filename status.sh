#!/usr/bin/env bash
# status.sh — Show pipeline project status
#
# Usage:
#   bash status.sh           — show all projects
#   bash status.sh <id>      — detailed state for one project

PIPELINE_ROOT="${PIPELINE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
PROJECTS_DIR="$PIPELINE_ROOT/projects"

if [ "$#" -eq 1 ]; then
    STATE_FILE="$PROJECTS_DIR/$1.json"
    if [ ! -f "$STATE_FILE" ]; then
        echo "ERROR: No state file for project '$1'"
        exit 1
    fi
    python3 -m json.tool "$STATE_FILE"
    exit 0
fi

FILES=$(ls "$PROJECTS_DIR"/*.json 2>/dev/null)
if [ -z "$FILES" ]; then
    echo "No projects in the pipeline."
    exit 0
fi

echo ""
echo "Agent Pipeline — Project Status"
echo "$(date)"
echo ""
printf "%-42s %-28s %-12s %-12s\n" "ID" "NAME" "PHASE" "STATUS"
printf "%s\n" "$(python3 -c "print('─' * 100)")"

for f in $FILES; do
    ID=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('id','')[:40])" 2>/dev/null)
    NAME=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('name','')[:26])" 2>/dev/null)
    PHASE=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('phase','')[:10])" 2>/dev/null)
    STATUS=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('status','')[:10])" 2>/dev/null)
    printf "%-42s %-28s %-12s %-12s\n" "$ID" "$NAME" "$PHASE" "$STATUS"
done

echo ""

python3 << PYEOF
import json, glob, os

projects_dir = os.environ.get("PROJECTS_DIR", "$PROJECTS_DIR")
files = glob.glob(f"{projects_dir}/*.json")
counts = {}
attention = []
failed = []
for f in files:
    try:
        d = json.load(open(f))
        s = d.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
        if s == "attention":
            attention.append(f"  👀 {d.get('name','?')} [{d.get('phase','?')}]: {d.get('attention_message','')[:80]}")
        elif s == "failed":
            failed.append(f"  ❌ {d.get('name','?')} [{d.get('phase','?')}]: {d.get('error','')[:80]}")
    except:
        pass

print("Summary:", " | ".join(f"{k}: {v}" for k, v in sorted(counts.items())))

if attention:
    print("\n⚠️  NEEDS ATTENTION:")
    print("\n".join(attention))

if failed:
    print("\n🔴 FAILED (use state.py reset to retry):")
    print("\n".join(failed))
PYEOF
echo ""
