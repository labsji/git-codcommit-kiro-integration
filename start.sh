#!/bin/bash
# start.sh — Kiro-administered tutorial for git-codecommit-proxy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check prerequisites
if ! command -v aws &>/dev/null; then
  echo "❌ AWS CLI not found. Run this in AWS CloudShell."
  exit 1
fi
if ! command -v kiro-cli &>/dev/null; then
  echo "❌ kiro-cli not found. Install from: https://kiro.dev/downloads"
  exit 1
fi
if ! command -v sam &>/dev/null; then
  echo "Installing SAM CLI..."
  pip install -q aws-sam-cli
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Tutorial: Connect Kiro Web to AWS CodeCommit               ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Deploy a proxy that lets Kiro Web work autonomously         ║"
echo "║  on your private CodeCommit repos.                           ║"
echo "║                                                              ║"
echo "║  Time: ~30 minutes | Cost: ~\$0/month                        ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

exec kiro-cli chat --trust-all-tools "Read .kiro-instructions.md and follow them. Guide me through deploying the git-codecommit-proxy step by step."
