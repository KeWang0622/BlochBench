# Grading environment

The supported image is built by [`Dockerfile.grader`](Dockerfile.grader), with Python dependency pins in
[`grader-env/requirements.txt`](grader-env/requirements.txt) and Julia/KomaMRI pins in
[`grader-env/julia_env/`](grader-env/julia_env/).

```bash
docker build --platform linux/amd64 -f harness/Dockerfile.grader -t mriagentbench-grader:0.1.0 .
```

The runner supports Codex CLI, Claude Code and a generic command adapter. See [Getting started](../docs/GETTING-STARTED.md)
for the actual command interface. The agent works in a fresh workspace containing only the prompt and public inputs;
the grader runs after it stops. Deliverables and time caps are defined by each task, not by a universal output folder.

A grading image is not an agent sandbox. Agent isolation and access to model endpoints are configured separately;
see [isolation](../docs/EVALUATE-YOUR-SKILLS.md#isolation). Frozen Core scripts retain some original path defaults;
`mrab` passes task and workspace paths explicitly, and does not launch reference solutions as the evaluated agent.
