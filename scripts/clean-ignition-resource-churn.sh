#!/bin/bash
# Restore tracked resource.json files when only volatile Designer metadata changed.

set -euo pipefail

APPLY=0
if [ "${1:-}" = "--apply" ]; then
    APPLY=1
elif [ "${1:-}" = "--dry-run" ] || [ "${1:-}" = "" ]; then
    APPLY=0
else
    echo "usage: $0 [--dry-run|--apply]" >&2
    exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

NORMALIZER="$REPO_ROOT/scripts/git-diff/normalize-ignition-resource-json.py"

volatile_only_count=0
skipped_count=0

PATHSPECS=(
    'services/config/resources/**/resource.json'
    'projects/**/resource.json'
)

# Candidates are manifests modified in the worktree, in the index, or both.
# The index half matters: `git add .` stages the churn, and without looking at
# staged entries this script (and the pre-commit hook that calls it) would be a
# no-op for everyone who does not use `git commit -a`.
# Newline-separated is safe here; Ignition resource paths contain spaces but
# never newlines.
candidates="$(
    {
        git diff --name-only --diff-filter=M -- "${PATHSPECS[@]}"
        git diff --cached --name-only --diff-filter=M -- "${PATHSPECS[@]}"
    } | sort -u
)"

while IFS= read -r path; do
    [ -n "$path" ] || continue

    # Newly added manifests have no HEAD version to compare against.
    git cat-file -e "HEAD:$path" 2>/dev/null || continue

    # --no-textconv is essential here. Without it the normalizer runs first,
    # a junk-only staged change compares equal, and git reports the file as
    # not staged at all: the exact case this check exists to catch.
    staged=0
    if ! git diff --cached --quiet --no-textconv -- "$path"; then
        staged=1
    fi

    # Compare the working-tree content against HEAD with the volatile metadata
    # stripped from both sides. The worktree copy also covers the staged case:
    # a real change that is staged is present here, so the file is left alone.
    if cmp -s \
        <("$NORMALIZER" "$path") \
        <(git show "HEAD:$path" | "$NORMALIZER" -); then
        volatile_only_count=$((volatile_only_count + 1))
        if [ "$APPLY" -eq 1 ]; then
            if [ "$staged" -eq 1 ]; then
                git restore --staged --worktree -- "$path"
                echo "restored (was staged): $path"
            else
                git restore --worktree -- "$path"
                echo "restored: $path"
            fi
        elif [ "$staged" -eq 1 ]; then
            echo "volatile-only (staged): $path"
        else
            echo "volatile-only: $path"
        fi
    elif [ "$staged" -eq 1 ]; then
        echo "skip staged, has real changes: $path"
        skipped_count=$((skipped_count + 1))
    fi
done <<< "$candidates"

if [ "$volatile_only_count" -eq 0 ]; then
    echo "No volatile-only resource.json changes found."
elif [ "$APPLY" -eq 0 ]; then
    echo "Run $0 --apply to restore these files."
fi

if [ "$skipped_count" -gt 0 ]; then
    echo "Skipped $skipped_count staged file(s)."
fi
