#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025-2026 Refaqt (BE 0804.145.539) and contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# Fill .agents/ at the start of every session.
#
# .agents/scripts/sync_root.py writes this file to .claude/hooks/session-start.sh.
# Do not edit that copy: change this template. The file on its own does nothing:
# .claude/settings.json is what starts it. .cursor/environment.json can run the same file, so Cursor
# cloud agents get the same result from one copy.
#
# Use this file only in a repository that does NOT have a doqs submodule. doqs
# installs its own hook at this exact path and overwrites whatever is there.
#
# Why this exists: a cloud session copies a repository without the contents of
# its submodules, so .agents/ arrives empty. The agent then reads no rules and
# no skills. The folder is there, so nothing looks wrong: the failure is silent,
# which is the worst kind.
#
# What this hook cannot do is start itself. Claude Code reads
# .claude/settings.json from the session's own project folder only. A session
# that opens a parent folder, or that attaches several repositories at once,
# never reads that file, so this hook never runs and prints nothing at all.
# CLAUDE.md carries the check that works in every session. See INSTALL.md,
# step 4.
#
# The two git calls must stay in this order:
#
#   1. --init -- .agents checks the kit out at the commit this repository
#      records. Naming .agents keeps every other submodule untouched.
#   2. --remote -- .agents moves the kit to the latest main.
#
# This hook never stops a session. With no network it says so and exits 0.

set -uo pipefail

# Find the repository root from this script's own place on disk.
#
# The file always sits at <root>/.claude/hooks/session-start.sh, so its own
# folder gives the answer. $CLAUDE_PROJECT_DIR does not: a session that attaches
# more than one repository opens their shared parent folder and sets the
# variable to it. That folder is not a git repository, so every git call below
# would fail and nothing would say why.
start_dir="$PWD"
self="${BASH_SOURCE[0]:-$0}"
here="$(cd "$(dirname "$self")" 2>/dev/null && pwd -P)"

# Print the top folder of the git work tree that holds "$1", or print nothing.
work_tree() {
  [ -n "${1:-}" ] || return 1
  git -C "$1" rev-parse --show-toplevel 2>/dev/null
}

# Take the folder next to this script only when it really is .claude/hooks, so
# a stray copy somewhere else cannot guess two levels up.
root=""
case "$here" in
  */.claude/hooks) root="$(work_tree "$here/../..")" ;;
esac
[ -n "$root" ] || root="$(work_tree "${CLAUDE_PROJECT_DIR:-}")"
[ -n "$root" ] || root="$(work_tree "$start_dir")"

if [ -z "$root" ]; then
  echo "The session hook found no git repository, so it checked nothing out."
  echo "It looked next to itself (${here:-unknown}), at CLAUDE_PROJECT_DIR"
  echo "(${CLAUDE_PROJECT_DIR:-not set}), and at ${start_dir}."
  echo "The session continues, but the shared rules are missing."
  echo "Write every reply and every file in B2 English anyway: short sentences, common words."
  exit 0
fi

cd "$root" || exit 0

# Say it only when it is worth saying. In a normal session these are the same.
[ "$root" = "$start_dir" ] || echo "Session hook: the repository root is ${root}, not ${start_dir}."

# A session start has no keyboard, so git must never wait for a password.
export GIT_TERMINAL_PROMPT=0

# timeout keeps a dead network from holding the session open.
run_git() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$1" git "${@:2}" 2>&1
  else
    git "${@:2}" 2>&1
  fi
}

output="$(run_git 180 submodule update --init -- .agents)"
status=$?

output="${output}
$(run_git 120 submodule update --remote -- .agents)"
remote_status=$?

# The marker file is the real test. Both commands above can exit 0 and still
# leave the folder empty: git prints "Skipping submodule" and succeeds. An exit
# code on its own proves nothing.
if [ -f ".agents/rules/core.md" ]; then
  kit="$(git -C .agents rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "The agent kit is ready in ${root}: .agents/ (${kit}). CLAUDE.md and AGENTS.md hold the rules."
  # The folder is usable even when only the first call worked, but then it holds
  # the recorded commit rather than the latest main. Say so, rather than let an
  # old kit pass for a fresh one.
  if [ $remote_status -ne 0 ]; then
    echo "Could not reach the remote: the kit is at its recorded commit. Later, run: bash setup-agents.sh"
  fi
  # Make the skills visible to Claude Code. Prints one line, never fails.
  [ -f .agents/scripts/link_skills.sh ] && bash .agents/scripts/link_skills.sh "$root"
  exit 0
fi

echo "Could not check out .agents in ${root} (git exit codes ${status} and ${remote_status})."

# A failing clone repeats itself once per retry, so the raw output runs to dozens
# of lines. A session start is not the place for that: keep the lines that name
# the cause, and cap them.
reason="$(printf '%s\n' "$output" | grep -E '^(fatal|error):' | sort -u | head -4)"
if [ -n "$reason" ]; then
  echo "git said:"
  printf '%s\n' "$reason" | sed 's/^/  /'
fi
echo "The session continues, but the shared rules and skills are missing."
echo "Write every reply and every file in B2 English anyway: short sentences, common words."
echo "Once you have a network again, run this from ${root}:"
echo "  bash setup-agents.sh"
exit 0
