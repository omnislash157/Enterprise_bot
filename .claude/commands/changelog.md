---
description: Add entry to project changelog
allowed-tools: Bash, Read, Edit
argument-hint: [summary of changes]
---

Add a changelog entry for: $ARGUMENTS

1. Get current timestamp [YYYY-MM-DD HH:MM]
2. Use `git diff --name-only` to find modified files
3. Create entry with timestamp, files modified, and summary
4. Append to .claude/CHANGELOG.md
