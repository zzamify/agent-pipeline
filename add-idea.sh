#!/usr/bin/env bash
# add-idea.sh — Queue a new project into the pipeline
#
# Usage:
#   bash add-idea.sh "Project Name" "Description"
#   bash add-idea.sh "Project Name" "Description" --type private
#   bash add-idea.sh "Project Name" "Description" --type testing
#
# --type production  Full pipeline: research → validate → build → review → qa → monetize → package → deploy → notify
# --type private     Internal tool: build → review → qa → package → deploy → notify
# --type testing     Experiment:    build → review → qa → notify (no deploy)
#
# Type defaults to production.
# Starting phase is automatically derived from type. Use --phase to override.

set -e

PIPELINE_ROOT="${PIPELINE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
PROJECTS_DIR="$PIPELINE_ROOT/projects"
PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"

if [ "$#" -lt 2 ]; then
    echo "Usage: bash add-idea.sh \"Project Name\" \"Description\" [--type production|private|testing]"
    exit 1
fi

TITLE="$1"
DESCRIPTION="$2"
APP_TYPE="production"
START_PHASE=""

shift 2
while [ "$#" -gt 0 ]; do
    case "$1" in
        --type)
            shift
            APP_TYPE="$1"
            shift
            ;;
        --phase)
            shift
            START_PHASE="$1"
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: bash add-idea.sh \"Name\" \"Desc\" [--type production|private|testing] [--phase PHASE]"
            exit 1
            ;;
    esac
done

if ! echo "production private testing" | grep -qw "$APP_TYPE"; then
    echo "ERROR: Invalid type '$APP_TYPE'. Valid: production private testing"
    exit 1
fi

if [ -z "$START_PHASE" ]; then
    case "$APP_TYPE" in
        production) START_PHASE="research" ;;
        private)    START_PHASE="build" ;;
        testing)    START_PHASE="build" ;;
    esac
fi

VALID_PHASES="research validate build review qa monetize package deploy notify"
if ! echo "$VALID_PHASES" | grep -qw "$START_PHASE"; then
    echo "ERROR: Invalid phase '$START_PHASE'. Valid: $VALID_PHASES"
    exit 1
fi

DATE=$(date +%Y%m%d)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
PROJECT_ID="${SLUG}-${DATE}"

STATE_FILE="$PROJECTS_DIR/${PROJECT_ID}.json"
PROJECT_DIR="$PROJECTS_ROOT/$SLUG"

if [ -f "$STATE_FILE" ]; then
    echo "ERROR: Project '$PROJECT_ID' already exists: $STATE_FILE"
    exit 1
fi

mkdir -p "$PROJECT_DIR"
if [ ! -d "$PROJECT_DIR/.git" ]; then
    git -C "$PROJECT_DIR" init -q
    git -C "$PROJECT_DIR" commit --allow-empty -m "chore: init project repo" -q
    echo "  ✅ Git repo initialized at: $PROJECT_DIR"
else
    echo "  ℹ️  Git repo already exists at: $PROJECT_DIR"
fi

# Build phases_completed list — everything before start phase is pre-marked
PRODUCTION_PHASES="research validate build review qa monetize package deploy notify"
PHASES_COMPLETED="[]"
if [ "$START_PHASE" != "research" ]; then
    COMPLETED=""
    for phase in $PRODUCTION_PHASES; do
        [ "$phase" = "$START_PHASE" ] && break
        COMPLETED="$COMPLETED\"$phase\","
    done
    COMPLETED="${COMPLETED%,}"
    PHASES_COMPLETED="[$COMPLETED]"
fi

cat > "$STATE_FILE" << EOF
{
  "id": "$PROJECT_ID",
  "name": "$TITLE",
  "description": "$DESCRIPTION",
  "app_type": "$APP_TYPE",
  "phase": "$START_PHASE",
  "status": "pending",
  "created_at": "$NOW",
  "updated_at": "$NOW",
  "phases_completed": $PHASES_COMPLETED,
  "project_dir": "$PROJECT_DIR",
  "notes": "",
  "error": null,
  "attention_message": null,
  "artifacts": {}
}
EOF

echo ""
echo "✅ Project queued!"
echo ""
echo "  ID:          $PROJECT_ID"
echo "  Name:        $TITLE"
echo "  Type:        $APP_TYPE"
echo "  Start phase: $START_PHASE (pending)"
echo "  State file:  $STATE_FILE"
echo "  Project dir: $PROJECT_DIR"
echo ""
echo "The pipeline will pick this up on its next run."
echo "Watch progress: bash \"$PIPELINE_ROOT/status.sh\""
