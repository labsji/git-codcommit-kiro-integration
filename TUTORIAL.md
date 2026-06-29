# Tutorial: Connect Kiro Web to Your Private AWS CodeCommit Repos

**Time:** 30 minutes | **Level:** Intermediate | **Cost:** ~$0/month (Lambda free tier)

## What you'll build

A GitLab-compatible API proxy that lets Kiro Web's autonomous agent clone, edit, push, and create pull requests on your private AWS CodeCommit repositories — as if they were GitLab projects.

```
Kiro Web (autonomous mode)
    ↓ GitLab API v4
git.yourdomain.com (your proxy on Lambda)
    ↓ AWS SDK / git smart HTTP
AWS CodeCommit (your private repos)
```

## Prerequisites

- AWS account with CodeCommit repositories
- AWS CloudShell (or CLI configured)
- SAM CLI installed (`pip install aws-sam-cli`)
- A domain managed in Route53
- Kiro Web account (app.kiro.dev)

---

## Step 1: Clone the proxy

```bash
cd ~
git clone https://github.com/labsji/git-codcommit-kiro-integration.git
cd git-codcommit-kiro-integration
```

## Step 2: Configure your domain

Edit `deploy.sh` — set these three values:

```bash
DOMAIN="git.yourdomain.com"        # your custom domain
HOSTED_ZONE_ID="Z0XXXXXXXX"        # Route53 hosted zone ID
REGION="ap-south-1"                 # where your CodeCommit repos live
```

Find your hosted zone ID:
```bash
aws route53 list-hosted-zones --query 'HostedZones[].{Name:Name,Id:Id}' --output table
```

## Step 3: Deploy (first run — creates certificate)

```bash
bash deploy.sh
```

First run:
- Generates a personal access token (PAT) for Kiro Web
- Requests an ACM certificate for your domain
- Creates the DNS validation record automatically
- Exits with: "Validate via DNS, then re-run this script."

Wait 1-3 minutes for certificate validation, then:

```bash
bash deploy.sh
```

Second run deploys the full stack. You'll see:

```
╔══════════════════════════════════════════╗
║  git-proxy deployed!                     ║
╠══════════════════════════════════════════╣
  URL: https://git.yourdomain.com
  PAT: <your-token>
╚══════════════════════════════════════════╝
```

**Save the PAT** — you'll need it in the next step.

## Step 4: Connect Kiro Web

1. Go to [app.kiro.dev](https://app.kiro.dev)
2. Open **Settings** → **Agent** tab
3. Under **GitLab**, click **Connect GitLab**
4. Fill in:
   - **Instance URL:** `https://git.yourdomain.com`
   - **Personal access token:** paste the PAT from Step 3
5. Click **Connect**

You should see "Connected" with a disconnect option.

## Step 5: Use your repos in a session

1. Create a new session in Kiro Web
2. Click **Add repository**
3. Your CodeCommit repos appear under the GitLab section
4. Select a repo (e.g., `bind`, `ikuku`)
5. The agent clones it and can now work on it autonomously

## Step 6: Test the full cycle

Ask the agent:

> "Create a feature branch, add a README improvement, and open a pull request."

The agent will:
1. Clone from CodeCommit ✅
2. Create a branch ✅
3. Make changes and push ✅
4. Open a PR (visible in AWS Console) ✅

PR links go to: `https://ap-south-1.console.aws.amazon.com/codesuite/codecommit/repositories/<repo>/pull-requests/<id>`

---

## How it works

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│ Kiro Web Sandbox                                            │
│                                                            │
│  Agent → GitLab REST API → git.yourdomain.com              │
│  Agent → git clone/push  → git.yourdomain.com              │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│ Your AWS Account                                            │
│                                                            │
│  API Gateway (HTTP API) + Lambda                           │
│  ├── /api/v4/projects      → codecommit:ListRepositories   │
│  ├── /api/v4/projects/:id  → codecommit:GetRepository      │
│  ├── /repo.git/info/refs   → git smart HTTP (SigV4 auth)  │
│  ├── /repo.git/git-upload-pack  → clone                   │
│  ├── /repo.git/git-receive-pack → push                    │
│  └── /merge_requests       → codecommit:CreatePullRequest  │
│                                                            │
│  Route53 → Custom domain + ACM cert                        │
└────────────────────────────────────────────────────────────┘
```

### API translation layer

| Kiro Web calls (GitLab API) | Proxy translates to (CodeCommit) |
|---|---|
| `GET /api/v4/projects` | `ListRepositories` |
| `GET /projects/:id/repository/tree` | `GetFolder` |
| `GET /projects/:id/repository/files/:path` | `GetFile` |
| `POST /projects/:id/repository/commits` | `CreateCommit` |
| `GET /projects/:id/repository/branches` | `ListBranches` |
| `POST /projects/:id/merge_requests` | `CreatePullRequest` |
| `GET /:repo.git/info/refs` | Git smart HTTP (GRC signing) |
| `POST /:repo.git/git-upload-pack` | Git pack transfer |
| `POST /:repo.git/git-receive-pack` | Git push |

### Authentication

- **Kiro Web → Proxy:** Personal Access Token (PAT) via `PRIVATE-TOKEN` header
- **Proxy → CodeCommit:** Lambda IAM role (automatic, no credentials to manage)
- **Proxy → CodeCommit (git):** GRC SigV4 signing (same as `git-remote-codecommit`)

---

## Managing access

### Multiple users

Generate separate PATs for different users or teams:

```bash
# In deploy.sh, set VALID_TOKENS to comma-separated list
export GIT_PROXY_TOKEN="token1,token2,token3"
bash deploy.sh
```

### Restrict repos

To limit which repos are visible, modify `handle_list_projects` in `handler.py`:

```python
# Filter to specific repos
ALLOWED_REPOS = {"bind", "ikuku", "next-sale"}
repos = [r for r in repos if r["repositoryName"] in ALLOWED_REPOS]
```

### Revoke access

Remove a token from `VALID_TOKENS` and redeploy:
```bash
bash deploy.sh
```

---

## Limitations

| Limitation | Workaround |
|---|---|
| Repos > 6MB pack size | Keep code repos lean; large binary assets belong in S3 |
| Single region | Deploy multiple stacks for multi-region |
| No webhook events | PRs visible in CodeCommit console |
| No CI/CD triggers | Use CodeCommit triggers → SNS → Lambda for automation |

---

## Bonus: CodeCommit MCP Power (for Kiro CLI/IDE)

The `power-codecommit/` folder includes a Kiro Power with MCP tools for direct CodeCommit access from Kiro CLI or IDE — no git clone needed.

Install:
```
Kiro → Powers → Add Custom Power → Import from folder → power-codecommit/
```

Tools available: `list_repos`, `list_files`, `get_file`, `create_commit`, `create_branch`, `list_branches`, `create_pr`, `list_prs`

---

## Cleanup

```bash
aws cloudformation delete-stack --stack-name git-proxy --region ap-south-1
```

This removes the Lambda, API Gateway, and custom domain mapping. Your CodeCommit repos are untouched.

---

## What's next

- **Autonomous feature development:** Kiro Web works on CodeCommit branches, creates PRs for review
- **Private → Public maturity:** Features mature in private CodeCommit, then get pushed to public GitHub when ready
- **Multi-user tutorials:** Delegates work via CloudShell + CodeCommit, coordinator reviews PRs

The proxy enables the workflow where **private development happens in CodeCommit** (cheap, native AWS, multi-user via IAM) and **Kiro Web provides autonomous coding assistance** without exposing code to third-party git hosting.
