# Commit workflow

1. **Create a branch** — `create_branch` with repo, branch name, and base ref
2. **Make changes** — `create_commit` with the files array (each file has path + content)
3. **Open PR** — `create_pr` with source branch, target branch, and title

## Multiple files in one commit
The `create_commit` tool accepts an array of files. Each entry:
- `{"path": "src/app.py", "content": "..."}` — create or update
- `{"path": "old-file.txt", "delete": true}` — delete

## Important
- Always read existing files before modifying them to avoid data loss
- Always commit to a feature branch, not main directly
