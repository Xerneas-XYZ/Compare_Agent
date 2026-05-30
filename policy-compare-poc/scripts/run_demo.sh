#!/usr/bin/env bash 

set -euo pipefail 

# scripts/run_demo.sh 

# Usage: ./scripts/run_demo.sh [username] [password] [BACKEND_URL] 

# Defaults: username=alice password=alicepass BACKEND_URL=http://localhost:8000 

# Requires: curl, jq (jq optional but recommended) 

BACKEND=${3:-http://localhost:8000} 
USERNAME=${1:-alice} 
PASSWORD=${2:-alicepass} 

echo "1) Request token for ${USERNAME}" 
TOKEN=$(curl -s -X POST "${BACKEND}/token" -d "username=${USERNAME}" -d "password=${PASSWORD}" | jq -r .access_token) 
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then 
  echo "Failed to get token. Ensure backend is running and credentials are correct." 
  exit 1 
fi 
AUTH="Authorization: Bearer ${TOKEN}" 
echo "Token acquired." 
TMPDIR=$(mktemp -d) 
trap 'rm -rf "$TMPDIR"' EXIT 
cat > "${TMPDIR}/legacy.txt" <<'EOF' 

Policy A 
Contact: alice@example.com 
Clause 1: Data retention 7 years. 
Clause 2: Use of personal data for analytics. 
EOF 
cat > "${TMPDIR}/modern.txt" <<'EOF' 

Policy B 
Contact: bob@example.com 
Clause 1: Data retention 5 years. 
Clause 2: Use of personal data for analytics and profiling. 
EOF 

echo "2) Upload legacy document..." 
R1=$(curl -s -X POST "${BACKEND}/upload/" -H "${AUTH}" -F "file=@${TMPDIR}/legacy.txt") 
echo "Upload response (legacy):" 
echo "$R1" | jq . 
echo "3) Upload modern document..." 
R2=$(curl -s -X POST "${BACKEND}/upload/" -H "${AUTH}" -F "file=@${TMPDIR}/modern.txt") 
echo "Upload response (modern):" 
echo "$R2" | jq . 
A_ID=$(echo "$R1" | jq -r .doc_id) 
B_ID=$(echo "$R2" | jq -r .doc_id) 
echo "4) Run compare (a_id=${A_ID}, b_id=${B_ID})..." 
COMPARE=$(curl -s -X POST "${BACKEND}/compare/?a_id=${A_ID}&b_id=${B_ID}" -H "${AUTH}") 
echo "Compare result (trimmed):" 
echo "$COMPARE" | jq '{diffs: .diffs, semantic_summary: .semantic.summary}' 
echo "5) Fetch recent audit entries..." 
AUDIT=$(curl -s -X GET "${BACKEND}/audit/?limit=10" -H "${AUTH}") 
echo "$AUDIT" | jq . 
echo "6) List indexed documents..." 
DOCS=$(curl -s -X GET "${BACKEND}/documents/" -H "${AUTH}") 
echo "$DOCS" | jq . 
echo "Demo complete." 