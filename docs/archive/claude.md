cat << 'EOF' > CLAUDE.md
# CLAUDE CODE RULES FOR THIS REPO

## CRITICAL: NO WORKTREES

1. NEVER create git worktrees. Work only in the main folder.
2. NEVER use `git worktree add` for any reason.
3. If you need to test something, use a branch, not a worktree.

## WORKING DIRECTORY

4. Before ANY file edit, run `pwd` and confirm you are in:
   `C:\Users\mthar\projects\enterprise_bot`
5. If you find yourself in a different path, STOP and ask.

## WHY THIS EXISTS

Worktrees have caused data loss in this repo. Claude Code edited files in a worktree while the user pushed from main, causing a desync that corrupted the codebase. Worktrees are permanently banned.

## FIRST ACTION EVERY SESSION

Run this before doing anything else:
```
pwd && git worktree list && git status
```

Confirm only one worktree exists (the main repo).
EOF