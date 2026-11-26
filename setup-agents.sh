#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025-2026 Refaqt (BE 0804.145.539) and contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# Fill and update the shared agent kit at .agents/.
#
# Copy this file to your repository root and run it from there:
#   bash setup-agents.sh
#
# Use this file only in a repository that does NOT have a doqs submodule.
# A repository with doqs uses setup-tooling.sh instead, which does the same
# work for both submodules and then installs the doqs launchers. Running both
# in one repository makes them fight over .claude/hooks/session-start.sh.
#
# Every command below names .agents on purpose. Other submodules stay at the
# commit your repository records, so this file can never move them.
set -euo pipefail
cd "$(dirname "$0")"

# Pick up a changed URL in .gitmodules before anything tries to fetch.
git submodule sync -- .agents
# Check the kit out at the commit this repository records.
git submodule update --init -- .agents
# Then move it to the latest main. This needs branch = main in .gitmodules.
git submodule update --remote -- .agents

# The marker file is the real test. The commands above can exit 0 and still
# leave the folder empty: git prints "Skipping submodule" and succeeds.
if [ -f ".agents/rules/core.md" ]; then
  kit="$(git -C .agents rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "The agent kit is ready: .agents/ (${kit})."
  # Only say this when it is true. The kit shows as modified when it moved on
  # since this repository last recorded it, and not when it was already current.
  if [ -n "$(git status --porcelain -- .agents 2>/dev/null)" ]; then
    echo "git status now shows .agents as modified. That is the update step doing"
    echo "its job. Leave it uncommitted unless you mean to fix a new version."
  fi
else
  echo "The agent kit is missing. The folder .agents/ is empty."
  echo "Check that .gitmodules has a .agents entry with branch = main, then run"
  echo "this file again: bash setup-agents.sh"
  exit 1
fi
