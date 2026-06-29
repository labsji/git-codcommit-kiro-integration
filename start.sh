#!/bin/bash
# start.sh — Kiro-administered tutorial for git-codecommit-proxy
# This launches a guided Kiro session that walks you through deployment and testing.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check prerequisites
if ! command -v aws &>/dev/null; then
  echo "❌ AWS CLI not found. Run this in AWS CloudShell."
  exit 1
fi
if ! command -v sam &>/dev/null; then
  echo "Installing SAM CLI..."
  pip install -q aws-sam-cli
fi
if ! command -v kiro-cli &>/dev/null; then
  echo "❌ kiro-cli not found. Install from: https://kiro.dev/downloads"
  exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Tutorial: Connect Kiro Web to AWS CodeCommit               ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  You'll deploy a GitLab API proxy that lets Kiro Web         ║"
echo "║  autonomously work on your private CodeCommit repos.         ║"
echo "║                                                              ║"
echo "║  Steps:                                                      ║"
echo "║    1. Deploy the proxy (Lambda + API Gateway)                ║"
echo "║    2. Connect Kiro Web to your domain                        ║"
echo "║    3. Test clone, push, and PR creation                      ║"
echo "║    4. Use autonomous mode on a real repo                     ║"
echo "║                                                              ║"
echo "║  Time: ~30 minutes                                           ║"
echo "║  Cost: ~\$0/month (Lambda free tier)                          ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Launch Kiro with tutorial context
exec kiro-cli chat --trust-all-tools \
  --system-prompt "You are a tutorial instructor guiding the user through deploying the git-codecommit-proxy.

## Context
The user is in the git-codcommit-kiro-integration repo directory. They need to:
1. Deploy the proxy to their AWS account
2. Connect Kiro Web to it
3. Verify clone/push/PR works

## Key files
- deploy.sh — one-command deployment script
- handler.py — the Lambda proxy code
- template.yaml — SAM infrastructure
- TUTORIAL.md — full written tutorial

## Steps to guide them through:

### Step 1: Configure
Ask them for their domain name and Route53 hosted zone ID. Help them find the zone ID if needed.
Edit deploy.sh with their values.

### Step 2: Deploy
Run: bash deploy.sh
First run creates the ACM cert. Wait for validation. Second run deploys.
Save the PAT that gets printed.

### Step 3: Connect Kiro Web
Guide them to app.kiro.dev → Settings → Agent → GitLab → Connect.
Instance URL: https://their-domain
Token: the PAT from step 2

### Step 4: Test
Have them create a session with a CodeCommit repo.
Ask the agent to make a change and create a PR.
Verify the PR appears in the CodeCommit console.

### Step 5: Understand
Explain the architecture if they ask.
The proxy translates GitLab API → CodeCommit API.
Git clone/push use smart HTTP with GRC SigV4 signing.

Be concise. Let them drive. Only explain when asked."
