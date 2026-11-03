# infra

CloudFormation templates and the deployment script for the hosted parts of BlochBench.

| File | Contents |
|---|---|
| foundation.yaml | budget alerts, ECR repository for the grader image, GitHub OIDC role for CI, artifacts bucket |
| grading.yaml | hosted grading: HTTP API, Lambda, DynamoDB, submissions bucket, AWS Batch on Fargate, EventBridge |
| deploy.py | deploy either stack, create submitter tokens, print outputs (AWS CLI only) |

Architecture, security model and cost: docs/INFRASTRUCTURE.md. API: docs/API.md.
