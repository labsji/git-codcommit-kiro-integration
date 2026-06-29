# git-codecommit-proxy

GitLab API proxy over AWS CodeCommit — use Kiro Web (or any GitLab-compatible tool) with your CodeCommit repos.

## What it does

Exposes your CodeCommit repositories as a GitLab-compatible API at a custom domain. Kiro Web connects to it as a "self-managed GitLab instance" and can clone, read, commit, branch, and create pull requests.

## Architecture

```
Kiro Web → git.yourdomain.com (this proxy) → AWS CodeCommit
         GitLab API v4                        Native API
```

Single Lambda + API Gateway. No servers. ~$0/month at low usage.

## Supported operations

| Operation | GitLab API endpoint | Status |
|-----------|-------------------|--------|
| List repos | `GET /api/v4/projects` | ✅ |
| Browse files | `GET /projects/:id/repository/tree` | ✅ |
| Read file | `GET /projects/:id/repository/files/:path` | ✅ |
| Create commit | `POST /projects/:id/repository/commits` | ✅ |
| List branches | `GET /projects/:id/repository/branches` | ✅ |
| Create branch | via commit API | ✅ |
| List PRs | `GET /projects/:id/merge_requests` | ✅ |
| Create PR | `POST /projects/:id/merge_requests` | ✅ |
| Git clone (HTTPS) | `git-upload-pack` | ✅ (repos < 6MB pack) |
| Git push | `git-receive-pack` | 🔜 |

## Deploy

### Prerequisites
- AWS account with CodeCommit repos (ap-south-1)
- SAM CLI installed
- A domain with Route53 hosted zone

### Quick start

```bash
git clone https://github.com/labsji/git-codecommit-proxy.git
cd git-codecommit-proxy

# Edit deploy.sh: set your domain, hosted zone ID
bash deploy.sh
```

First run creates an ACM certificate (validates via DNS automatically). Second run deploys the stack.

### Connect Kiro Web

1. Go to Settings → Agent → GitLab → Connect
2. Instance URL: `https://your-domain.com`
3. Token: (printed by deploy.sh)

## Configuration

| Env var | Description |
|---------|-------------|
| `VALID_TOKENS` | Comma-separated PATs accepted by the proxy |

Edit `deploy.sh` to customize:
- `DOMAIN` — your custom domain
- `REGION` — CodeCommit region
- `HOSTED_ZONE_ID` — Route53 zone

## Limitations

- Git clone works for repos with pack size < 6MB (Lambda payload limit). Code-only repos are typically well under this.
- Git push not yet implemented (use the commit API instead).
- Single-region (connects to one CodeCommit region).

## How git clone works

The proxy implements git's smart HTTP protocol:
1. `GET /repo.git/info/refs?service=git-upload-pack` — returns refs (branches/tags)
2. `POST /repo.git/git-upload-pack` — returns pack data

Authentication to CodeCommit uses the [GRC signing method](https://github.com/aws/git-remote-codecommit) (SigV4-based basic auth), handled transparently by the Lambda.

## Also included: CodeCommit MCP Power

The `power-codecommit/` folder contains a Kiro Power (MCP server) for Kiro CLI/IDE. It provides tools to list repos, read/write files, create branches, and open PRs directly — no git clone needed.

Install: Kiro → Powers → Add Custom Power → Import from folder → `power-codecommit/`

## License

MIT
