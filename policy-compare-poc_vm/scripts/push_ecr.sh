#!/usr/bin/env bash 

set -euo pipefail 

# scripts/push_ecr.sh <aws-account-id> <region> <repo-name> [tag] 

AWS_ACCOUNT=${1:?aws-account-id required} 

AWS_REGION=${2:?region required} 

REPO_NAME=${3:?repo-name required} 

TAG=${4:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)} 

ECR_URI="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}" 

aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 || \ 
aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" 
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com" 

docker build -t "${REPO_NAME}:${TAG}" . 
docker tag "${REPO_NAME}:${TAG}" "${ECR_URI}:${TAG}" 
docker push "${ECR_URI}:${TAG}" 

echo "Pushed ${ECR_URI}:${TAG}" 