Policy Compare POC - Quick Run 
 
1. Set environment variables: 
   - SECRET_KEY, OPENAI_API_KEY (optional) 
 
2. Build and run locally: 
   docker-compose up --build 
 
3. Access backend: 
   http://localhost:8000/docs 
 
4. Demo users: 
   - alice / alicepass (admin) 
   - bob / bobpass (auditor) 
   - carol / carolpass (viewer) 
 
Notes: 
- PII is masked at ingestion. PII summary stored in metadata. 
- Audit trail recorded for uploads and compares in SQLite. 
- For production, replace in-memory USERS with corporate IAM and rotate SECRET_KEY. 
- To deploy cheaply on AWS: push image to ECR and run on ECS Fargate with a small task size. 
 