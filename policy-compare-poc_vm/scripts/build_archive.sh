#!/usr/bin/env bash set -euo pipefail 

scripts/build_archive.sh 

Usage: ./scripts/build_archive.sh [--no-docker] [--output-dir ./dist] 

Produces: dist/--.tar.gz and .zip 

Runs pytest before packaging. Exits non-zero on test failure. 

NO_DOCKER=0 OUT_DIR="./dist" while [[ $# -gt 0 ]]; do case "$1" in --no-docker) NO_DOCKER=1; shift ;; --output-dir) OUT_DIR="$2"; shift 2 ;; *) echo "Unknown arg: $1"; exit 1 ;; esac done 

REPO_NAME="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo .)")" GIT_REF="$(git rev-parse --short HEAD 2>/dev/null || echo local)" DATE="$(date -u +%Y%m%dT%H%M%SZ)" ARCHIVE_BASE="${REPO_NAME}-${GIT_REF}-${DATE}" mkdir -p "$OUT_DIR" 

echo "1/5 Running tests (pytest)..." if ! pytest -q; then echo "Tests failed — aborting archive build." exit 2 fi 

if [[ "$NO_DOCKER" -eq 0 ]]; then echo "2/5 Building Docker image (local) as ${REPO_NAME}:${GIT_REF}..." docker build -t "${REPO_NAME}:${GIT_REF}" . else echo "2/5 Skipping Docker build (--no-docker)." fi 

echo "3/5 Preparing temporary export directory..." TMPDIR="$(mktemp -d)" trap 'rm -rf "$TMPDIR"' EXIT rsync -a --exclude '.git' --exclude 'data' --exclude 'dist' --exclude 'pycache' . "$TMPDIR/$REPO_NAME" 

echo "4/5 Creating archives..." tar -C "$TMPDIR" -czf "${OUT_DIR}/${ARCHIVE_BASE}.tar.gz" "$REPO_NAME" ( cd "$TMPDIR" && zip -r "${OUT_DIR}/${ARCHIVE_BASE}.zip" "$REPO_NAME" >/dev/null ) 

echo "5/5 Artifacts created:" ls -lh "${OUT_DIR}/${ARCHIVE_BASE}.tar.gz" "${OUT_DIR}/${ARCHIVE_BASE}.zip" 

echo "Done." 
