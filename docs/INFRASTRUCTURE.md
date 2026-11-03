# Optional hosted grading infrastructure

Public users run and grade locally, then [submit a result bundle](SUBMITTING.md) through a results issue. No hosted API token
is required for that workflow. This directory also includes an optional maintainer-operated AWS grading service;
its source code is not a promise of a public endpoint or service-level guarantee.

## Components

[`infra/foundation.yaml`](../infra/foundation.yaml) defines foundational resources. [`infra/grading.yaml`](../infra/grading.yaml)
defines an API Gateway/Lambda API, DynamoDB submission records, S3 bundles and an AWS Batch/Fargate grading queue.
The [API reference](API.md) documents the CLI contract.

A client uploads a bundle through an expiring presigned URL. The service validates its catalog entries and hash,
queues grading jobs, then collects per-run grades. A job downloads packages, verifies their frozen manifests and
runs graders as an unprivileged user. Jobs receive expiring URLs and a one-time callback token rather than an IAM role.
See [`mragentbench/service/`](../mragentbench/service/) for implementation details and tests.

The public Core grader includes reference answers. Hosted regrading can check the environment and reported outputs;
it does not restore secrecy to a publicly available task. Hard evaluation uses separately held private task material.

## Grader image CI

Pull requests build and check the grading image when relevant code changes. Ordinary pushes do not publish to any
cloud account. A maintainer can explicitly dispatch `build-grader-image` with `publish_ecr=true` after configuring:

| Repository variable | Purpose |
|---|---|
| `AWS_ROLE_ARN` | OIDC role scoped to the repository and main branch |
| `AWS_REGION` | Deployment region |
| `ECR_REGISTRY` | Destination registry |
| `ECR_REPOSITORY` | Destination image repository |

No personal AWS account is hardcoded in the workflow. Operating this service incurs storage, request, transfer and
compute charges; budget and capacity settings must be chosen by its operator. The public website is deployed
separately with GitHub Pages, and Core packages are distributed through GitHub Releases.
