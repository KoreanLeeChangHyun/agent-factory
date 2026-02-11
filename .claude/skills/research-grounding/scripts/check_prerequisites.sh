#!/usr/bin/env bash
# research-grounding prerequisites check script
# Checks: Gemini CLI installation, Google API Key environment variable
# Exit code: 0 = all prerequisites met, 1 = one or more missing

set -euo pipefail

PASS=0
FAIL=0
ERRORS=()

echo "=== research-grounding Prerequisites Check ==="
echo ""

# Check 1: Gemini CLI
echo -n "[1/2] Gemini CLI ... "
if command -v gemini &>/dev/null; then
    VERSION=$(gemini --version 2>/dev/null || echo "unknown")
    echo "OK (version: ${VERSION})"
    PASS=$((PASS + 1))
else
    echo "NOT FOUND"
    ERRORS+=("Gemini CLI is not installed. Install: https://github.com/google-gemini/gemini-cli")
    FAIL=$((FAIL + 1))
fi

# Check 2: Google API Key
echo -n "[2/2] GOOGLE_API_KEY ... "
if [ -n "${GOOGLE_API_KEY:-}" ]; then
    # Show only first 8 chars for security
    MASKED="${GOOGLE_API_KEY:0:8}..."
    echo "OK (${MASKED})"
    PASS=$((PASS + 1))
else
    echo "NOT SET"
    ERRORS+=("GOOGLE_API_KEY environment variable is not set. Export it in your shell profile.")
    FAIL=$((FAIL + 1))
fi

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ ${FAIL} -gt 0 ]; then
    echo ""
    echo "Missing prerequisites:"
    for err in "${ERRORS[@]}"; do
        echo "  - ${err}"
    done
    echo ""
    echo "Without these prerequisites, research-grounding will operate in manual"
    echo "verification mode using WebSearch/WebFetch instead of Gemini CLI automation."
    echo "The skill remains functional but without Google Search grounding features."
    exit 1
fi

echo ""
echo "All prerequisites met. research-grounding is ready for full automation."
exit 0
