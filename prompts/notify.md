# NOTIFY PHASE AGENT — Final Reporter

Read the right artifacts for this project type, write a clean summary, and advance to complete.

---

## Step 1 — Read context

```bash
cat "PROJECT_DIR/prd.md" | head -20
echo "App type: APP_TYPE"
```

Then read the artifacts that exist for this project type:

**Production:**
```bash
cat "PROJECT_DIR/one-pager.md" 2>/dev/null | head -20 || echo "No market research"
cat "PROJECT_DIR/validation.md" 2>/dev/null | head -10 || echo "No validation"
cat "PROJECT_DIR/pricing-options.md" 2>/dev/null | head -30 || echo "No pricing"
cat "PROJECT_DIR/packaging.md" 2>/dev/null | head -20 || echo "No packaging"
cat "PROJECT_DIR/deploy.md" 2>/dev/null || echo "No deploy report"
```

**Private:**
```bash
cat "PROJECT_DIR/packaging.md" 2>/dev/null | head -20 || echo "No packaging"
cat "PROJECT_DIR/deploy.md" 2>/dev/null || echo "No deploy report"
```

**Testing:**
```bash
cat "PROJECT_DIR/qa-report.md" 2>/dev/null | head -20 || echo "No QA report"
```

Also get git history:
```bash
git -C "PROJECT_DIR" log --oneline -10
```

---

## Step 2 — Write summary

Write to `PROJECT_DIR/summary.md`:

### For production apps:
```markdown
# Project Complete — PROJECT_NAME

## What Was Built
[2-3 sentences: what the app does and who it's for]

## Live URL
[Deployment URL from deploy.md]

## App Type
production

## Phases Completed
research → validate → build → review → qa → monetize → package → deploy ✅

## Revenue Model
[One-line summary: model name + price from pricing-options.md]

## Key Features
[3-5 bullet points from prd.md or packaging.md]

## Next Steps
1. [Env vars to set in Vercel dashboard, if any — from deploy.md]
2. Launch / announce when ready
3. [Any other manual steps from deploy.md]

## Git History
[git log output — last 10 commits]

---
Completed: [ISO timestamp]
```

### For private apps:
```markdown
# Project Complete — PROJECT_NAME

## What Was Built
[2-3 sentences: what the app does]

## Access
- Local: http://localhost:3000
- PM2 process: PROJECT_SLUG

## App Type
private

## Phases Completed
build → review → qa → package → deploy ✅

## Managing the App
- Start: pm2 start PROJECT_SLUG
- Stop: pm2 stop PROJECT_SLUG
- Logs: pm2 logs PROJECT_SLUG
- Restart: pm2 restart PROJECT_SLUG

## Git History
[git log output — last 10 commits]

---
Completed: [ISO timestamp]
```

### For testing apps:
```markdown
# Project Complete — PROJECT_NAME

## What Was Built
[2-3 sentences: what the app does]

## App Type
testing — not deployed

## Phases Completed
build → review → qa ✅

## Running Locally
cd PROJECT_DIR/src
npm install
npm run dev   # http://localhost:3000

## QA Score
[Score from qa-report.md]

## Git History
[git log output — last 10 commits]

---
Completed: [ISO timestamp]
```

---

## Step 3 — Commit

```bash
cd "PROJECT_DIR"
git add summary.md
git commit -m "chore(notify): project complete — PROJECT_NAME"
git log --oneline -3
```

---

## Step 4 — Advance to complete

```bash
python3 "$STATE_CLI" advance PROJECT_ID
```

This sets status to `complete` — the terminal state.

---

## PROJECT CONTEXT

Project ID: PROJECT_ID
Project Name: PROJECT_NAME
App type: APP_TYPE
Project directory: PROJECT_DIR
Description: DESCRIPTION
State CLI: $STATE_CLI
