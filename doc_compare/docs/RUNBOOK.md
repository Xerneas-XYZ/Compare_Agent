# Runbook

## Prerequisites
- AWS CLI configured with deploy permissions
- Docker 24+
- ECR repos created: `doc-compare-backend`, `doc-compare-frontend`
- Secrets in AWS Secrets Manager:
  - `doc-compare/openai-key`
  - `doc-compare/secret-key`

## Local Dev

```bash
cp .env.example .env        # fill in OPENAI_API_KEY
cd infra/docker
docker compose up --build
```

- Frontend: http://localhost:8501
- API docs: http://localhost:8000/api/docs

## AWS Deployment

### 1. Create ECS Cluster
```bash
aws ecs create-cluster --cluster-name doc-compare-cluster --capacity-providers FARGATE
```

### 2. Deploy ALB Stack
```bash
aws cloudformation deploy \
  --template-file infra/alb/alb-stack.yaml \
  --stack-name doc-compare-alb \
  --parameter-overrides \
    VpcId=vpc-XXXX \
    PublicSubnets=subnet-A,subnet-B \
    CertificateArn=arn:aws:acm:... \
  --capabilities CAPABILITY_IAM
```

### 3. Register Task Definition
```bash
# Replace ACCOUNT_ID and REGION in task-definition.json first
aws ecs register-task-definition \
  --cli-input-json file://infra/ecs/task-definition.json
```

### 4. Create ECS Service
```bash
aws ecs create-service \
  --cluster doc-compare-cluster \
  --service-name doc-compare-service \
  --task-definition doc-compare-agent \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-A,subnet-B],securityGroups=[sg-XXX],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=ARN_FROM_CFN_OUTPUT,containerName=frontend,containerPort=8501"
```

### 5. Push images via CI
Push to `main` branch — CI pipeline handles ECR push + ECS rolling update.

## Health Checks
```bash
# Backend
curl https://your-domain.com/api/v1/health
curl https://your-domain.com/api/v1/ready

# Frontend
curl https://your-domain.com/_stcore/health
```

## Rollback
```bash
# Roll back to previous ECS task revision
aws ecs update-service \
  --cluster doc-compare-cluster \
  --service doc-compare-service \
  --task-definition doc-compare-agent:PREVIOUS_REVISION
```

## Scaling
```bash
# Scale out
aws ecs update-service \
  --cluster doc-compare-cluster \
  --service doc-compare-service \
  --desired-count 4
```

## Logs
```bash
# Backend logs
aws logs tail /ecs/doc-compare-backend --follow

# Frontend logs
aws logs tail /ecs/doc-compare-frontend --follow
```

## Production Checklist
- [ ] OPENAI_API_KEY in Secrets Manager (not env var)
- [ ] SECRET_KEY set to 32+ char random string
- [ ] HTTPS certificate attached to ALB
- [ ] ALLOWED_ORIGINS set to production domain
- [ ] APP_ENV=production
- [ ] LangSmith tracing configured (optional but recommended)
- [ ] CloudWatch alarms on ECS CPU/memory
- [ ] ALB access logs enabled to S3