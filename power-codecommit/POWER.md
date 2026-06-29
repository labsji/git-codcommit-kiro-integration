---
name: "codecommit"
displayName: "AWS CodeCommit"
description: "Manage Git repositories on AWS CodeCommit — browse, read, commit, branch, and create pull requests without git clone"
keywords: ["codecommit", "aws", "git", "repository", "commit", "branch", "pull request", "merge", "code review"]
author: "skith.in"
---

# Onboarding

## Step 1: Validate AWS access
Ensure AWS credentials are configured with CodeCommit access:
- Verify with: `aws codecommit list-repositories --region ap-south-1`
- Required IAM permissions: `codecommit:Get*`, `codecommit:List*`, `codecommit:CreateCommit`, `codecommit:CreateBranch`, `codecommit:CreatePullRequest`

## Step 2: Configure region
The MCP server connects to CodeCommit in `ap-south-1` by default. Set `AWS_REGION` env var to override.

# Steering

## Working with CodeCommit repositories

- Use `list_repos` to see available repositories
- Use `get_file` to read file content from any branch
- Use `list_files` to browse directory structure
- Use `create_commit` to write changes (create/update/delete files in a single commit)
- Use `create_branch` before making changes for a feature branch
- Use `create_pr` to open a pull request for code review
- Use `list_branches` to see all branches
- Use `list_prs` to see open pull requests

## Best practices

- Always create a feature branch before committing changes
- Use descriptive commit messages
- Create a PR after pushing changes for review
- Read existing code before making modifications

## When to load steering files
- Browsing repository contents → `steering/browse-repos.md`
- Making code changes → `steering/commit-workflow.md`
- Code review workflow → `steering/pull-requests.md`
