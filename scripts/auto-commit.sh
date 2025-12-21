#!/bin/bash
# Auto-commit script for Context Lake workspaces
# Runs via cron every 5 minutes on VM
# Commits and pushes any changes in workspaces

WORKSPACES_ROOT="${WORKSPACES_ROOT:-/opt/workspaces}"
LOG_FILE="/var/log/motoko-autocommit.log"

log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") $1" >> "$LOG_FILE"
}

# Find all git repos in workspaces
find "$WORKSPACES_ROOT" -name ".git" -type d 2>/dev/null | while read git_dir; do
    workspace_dir=$(dirname "$git_dir")
    cd "$workspace_dir" || continue

    # Check for uncommitted changes
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        git add -A
        timestamp=$(date +"%Y-%m-%d %H:%M:%S")
        git commit -m "Auto-commit: $timestamp" --no-gpg-sign 2>/dev/null
        log "Committed changes in $workspace_dir"
    fi

    # Push if remote exists and we have unpushed commits
    if git remote get-url origin &>/dev/null; then
        if [ -n "$(git log origin/main..HEAD 2>/dev/null)" ]; then
            git push origin main 2>/dev/null && log "Pushed $workspace_dir" || log "Push failed: $workspace_dir"
        fi
    fi
done
