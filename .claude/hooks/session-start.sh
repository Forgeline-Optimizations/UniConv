#!/usr/bin/env bash
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG="$ROOT/.claude/memory/session-log.md"
MODE="${1:-full}"

if [ "$MODE" = "full" ]; then
cat <<'EOF'
## Session orientation (injected by the SessionStart hook)
New session in UniConv. CLAUDE.md and .claude/SOUL.md are already loaded.
Key files: docs/implementation-plan.md (full plan, steps 1-37, read per step),
.claude/memory/session-log.md (history), .claude/decisions/ (ADRs),
src/uniconv/<module>/CLAUDE.md and tests/CLAUDE.md (module detail, load on demand),
/onboard (re-orient).
Open your first reply with a short orientation as described in CLAUDE.md
"Session start", using the latest session-log entry below and the Current Sprint
section of CLAUDE.md.
EOF
fi

echo
echo "### Latest session-log entry"
awk '/^## Sprint/ {n++} n==1 {print} n==1 && /^---$/ {exit}' "$LOG" 2>/dev/null
exit 0
