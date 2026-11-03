# Security

Please report vulnerabilities in the mrab tool, the graders or the hosted grading service privately, through GitHub's
"Report a vulnerability" button on the Security tab of this repository. Do not open a public issue.

Useful reports include ways to:

- make a submission pass checks it should fail, or change another submitter's results;
- read hidden-set material or another submitter's bundle;
- obtain AWS credentials or run work outside the grading container;
- exceed quotas or cause cost without a valid token.

The design and its limits are described in docs/INFRASTRUCTURE.md (Security model). Please do not test against the
hosted service with heavy load; ask for a test token and we will help.
