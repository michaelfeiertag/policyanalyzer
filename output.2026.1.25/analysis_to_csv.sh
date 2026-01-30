#!/bin/bash
# Reads an analysis file and outputs a CSV line by extracting fields via Claude API.
# Usage: ./analysis_to_csv.sh <analysis_file>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

if [ $# -ne 1 ]; then
  echo "Usage: $0 <analysis_file>" >&2
  exit 1
fi

INPUT_FILE="$1"

if [ ! -f "$INPUT_FILE" ]; then
  echo "Error: File not found: $INPUT_FILE" >&2
  exit 1
fi

CONTENT=$(cat "$INPUT_FILE")

PROMPT="You are a structured data extractor. Given the following policy compliance analysis, extract exactly these fields and output ONLY a single CSV line (no header, no explanation, no markdown):

Agent Name, Agent Function, Policy, Applicable Y/N, Compliant?

Rules:
- Agent Name: The human-readable name of the agent (e.g. \"Agent Lister\")
- Agent Function: A summary of what the agent does in 8 words or fewer
- Policy: The regulation/policy analyzed (e.g. \"GDPR\")
- Applicable Y/N: \"Y\" if the policy is applicable, \"N\" if not
- Compliant?: One of \"Compliant\", \"Non-Compliant\", or \"Partially Compliant\"
- Properly quote any field containing commas with double quotes
- Do NOT output a header row, only the data line

Analysis content:
${CONTENT}"

RESPONSE=$(curl -s https://api.anthropic.com/v1/messages \
  -H "x-api-key: ${ANTHROPIC_API_KEY}" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "$(jq -n --arg prompt "$PROMPT" '{
    model: "claude-sonnet-4-20250514",
    max_tokens: 256,
    messages: [{role: "user", content: $prompt}]
  }')")

echo "$RESPONSE" | jq -r '.content[0].text'
