# infra

CloudFormation templates and the deployment script for the hosted parts of MRI Agent Bench.

| File | Contents |
|---|---|
| foundation.yaml | budget alerts, ECR repository for the grader image, GitHub OIDC role for CI, artifacts bucket |
| grading.yaml | hosted grading: HTTP API, Lambda, DynamoDB, submissions bucket, AWS Batch on Fargate, EventBridge |
| deploy.py | deploy either stack, create submitter tokens, print outputs (AWS CLI only) |

Architecture, security model and cost: docs/INFRASTRUCTURE.md. API: docs/API.md.

The repository rename to MRI Agent Bench does not rename deployed infrastructure. Existing `BlochBench`
project tags and stack defaults are retained for compatibility; this branding change performs no cloud deployment.
