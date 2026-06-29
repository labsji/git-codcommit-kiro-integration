#!/bin/bash
# deploy.sh — Deploy git-proxy to ap-south-1
set -euo pipefail

STACK_NAME="git-proxy"
REGION="ap-south-1"
S3_BUCKET="ikuku-releases"
DOMAIN="git.next.skith.in"

# Generate a PAT for Kiro Web to use
TOKEN="${GIT_PROXY_TOKEN:-$(openssl rand -hex 16)}"
echo "PAT for Kiro Web: $TOKEN"

# Check/create ACM cert
CERT_ARN=$(aws acm list-certificates --region "$REGION" \
  --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn" --output text)
if [ -z "$CERT_ARN" ] || [ "$CERT_ARN" = "None" ]; then
  echo "Requesting ACM certificate for $DOMAIN..."
  CERT_ARN=$(aws acm request-certificate --region "$REGION" \
    --domain-name "$DOMAIN" --validation-method DNS \
    --query 'CertificateArn' --output text)
  echo "Certificate requested: $CERT_ARN"
  echo "Validate via DNS, then re-run this script."
  exit 0
fi

echo "Using cert: $CERT_ARN"

# Build and deploy
sam build --region "$REGION"
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --s3-bucket "$S3_BUCKET" \
  --s3-prefix "sam/git-proxy" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    "ValidTokens=$TOKEN" \
    "CertificateArn=$CERT_ARN" \
  --no-confirm-changeset

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  git-proxy deployed!                     ║"
echo "╠══════════════════════════════════════════╣"
echo "  URL: https://$DOMAIN"
echo "  PAT: $TOKEN"
echo ""
echo "  In Kiro Web → Settings → Agent → GitLab:"
echo "    Instance URL: https://$DOMAIN"
echo "    Token: $TOKEN"
echo "╚══════════════════════════════════════════╝"
