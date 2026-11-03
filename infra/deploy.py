#!/usr/bin/env python3
"""Deploy and operate the BlochBench AWS stacks with the AWS CLI (no other dependencies).

  python infra/deploy.py foundation --budget-email ADDRESS [--budget-usd 10]
  python infra/deploy.py grading [--image URI@sha256:DIGEST] [--max-vcpus 16]
  python infra/deploy.py submitter NAME [--quota 5]      create a submitter; prints the token once
  python infra/deploy.py outputs                          show stack outputs

Uses AWS_PROFILE (or --profile) and region us-west-2 unless --region is given. See infra/README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import secrets
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INFRA = REPO / "infra"


class Aws:
    def __init__(self, profile: str | None, region: str):
        self.base = ["aws", "--region", region, "--output", "json"] + (["--profile", profile] if profile else [])

    def __call__(self, *args: str, parse: bool = True):
        r = subprocess.run(self.base + list(args), capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"aws {' '.join(args[:2])} failed:\n{r.stderr.strip()}")
        return json.loads(r.stdout) if parse and r.stdout.strip() else r.stdout

    def deploy(self, stack: str, template: Path, params: dict[str, str]) -> None:
        overrides = [f"{k}={v}" for k, v in params.items()]
        r = subprocess.run(
            self.base
            + [
                "cloudformation",
                "deploy",
                "--stack-name",
                stack,
                "--template-file",
                str(template),
                "--capabilities",
                "CAPABILITY_NAMED_IAM",
                "--no-fail-on-empty-changeset",
                "--tags",
                "project=BlochBench",
                "--parameter-overrides",
                *overrides,
            ]
        )
        if r.returncode:
            sys.exit(f"deploying {stack} failed; see the stack events in the CloudFormation console")

    def outputs(self, stack: str) -> dict[str, str]:
        st = self("cloudformation", "describe-stacks", "--stack-name", stack)["Stacks"][0]
        return {o["OutputKey"]: o["OutputValue"] for o in st.get("Outputs", [])}


def catalog() -> dict:
    out = {}
    for f in sorted((REPO / "families").glob("*/instances.json")):
        family = json.loads((f.parent / "family.json").read_text())["id"]
        for x in json.loads(f.read_text()):
            out[x["instance"]] = dict(x, family=family)
    return out


def lambda_zip() -> tuple[bytes, str]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in (
            ("api.py", (REPO / "mragentbench/service/api.py").read_bytes()),
            ("catalog.json", json.dumps(catalog(), sort_keys=True).encode()),
        ):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    data = buf.getvalue()
    return data, hashlib.sha256(data).hexdigest()[:16]


def cmd_foundation(aws: Aws, a) -> None:
    aws.deploy(
        "mragentbench-foundation",
        INFRA / "foundation.yaml",
        {"BudgetEmail": a.budget_email, "MonthlyBudgetUsd": str(a.budget_usd)},
    )
    print(json.dumps(aws.outputs("mragentbench-foundation"), indent=1))


def cmd_grading(aws: Aws, a) -> None:
    found = aws.outputs("mragentbench-foundation")
    image = a.image
    if not image:
        repo = found["GraderRepositoryUri"]
        d = aws("ecr", "describe-images", "--repository-name", repo.split("/", 1)[1], "--image-ids", "imageTag=main")
        image = f"{repo}@{d['imageDetails'][0]['imageDigest']}"
    data, digest = lambda_zip()
    key = f"lambda/api-{digest}.zip"
    with tempfile.NamedTemporaryFile(suffix=".zip") as f:
        f.write(data)
        f.flush()
        aws("s3", "cp", f.name, f"s3://{found['ArtifactsBucketName']}/{key}", "--only-show-errors", parse=False)
    vpc = aws("ec2", "describe-vpcs", "--filters", "Name=isDefault,Values=true")["Vpcs"][0]["VpcId"]
    subnets = [
        s["SubnetId"]
        for s in aws(
            "ec2", "describe-subnets", "--filters", f"Name=vpc-id,Values={vpc}", "Name=default-for-az,Values=true"
        )["Subnets"]
    ]
    print(f"image {image}\nlambda code s3://{found['ArtifactsBucketName']}/{key}")
    aws.deploy(
        "mragentbench-grading",
        INFRA / "grading.yaml",
        {
            "GraderImage": image,
            "LambdaCodeKey": key,
            "VpcId": vpc,
            "SubnetIds": ",".join(subnets),
            "MaxVcpus": str(a.max_vcpus),
        },
    )
    print(json.dumps(aws.outputs("mragentbench-grading"), indent=1))


def cmd_submitter(aws: Aws, a) -> None:
    token = "mrab_" + secrets.token_urlsafe(32)
    item = {
        "token_sha256": {"S": hashlib.sha256(token.encode()).hexdigest()},
        "submitter": {"S": a.name},
        "daily_quota": {"N": str(a.quota)},
        "active": {"BOOL": True},
        "created_at": {"S": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    }
    aws("dynamodb", "put-item", "--table-name", "mragentbench-submitters", "--item", json.dumps(item), parse=False)
    print(f"submitter {a.name} (quota {a.quota}/day). Token, shown once:\n{token}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile")
    ap.add_argument("--region", default="us-west-2")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("foundation")
    p.add_argument("--budget-email", required=True)
    p.add_argument("--budget-usd", type=int, default=10)
    p = sp.add_parser("grading")
    p.add_argument("--image")
    p.add_argument("--max-vcpus", type=int, default=16)
    p = sp.add_parser("submitter")
    p.add_argument("name")
    p.add_argument("--quota", type=int, default=5)
    sp.add_parser("outputs")
    a = ap.parse_args()
    aws = Aws(a.profile, a.region)
    if a.cmd == "outputs":
        for s in ("mragentbench-foundation", "mragentbench-grading"):
            print(s, json.dumps(aws.outputs(s), indent=1))
        return
    {"foundation": cmd_foundation, "grading": cmd_grading, "submitter": cmd_submitter}[a.cmd](aws, a)


if __name__ == "__main__":
    main()
