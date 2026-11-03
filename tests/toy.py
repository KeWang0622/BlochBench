"""A toy instance, a fake agent and helpers shared by the command-line tests (standard library only)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import textwrap
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mragentbench import catalog, cli  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

TOY_GRADER = textwrap.dedent("""
    import json, subprocess, sys
    from pathlib import Path
    work, out = Path(sys.argv[1]), Path(sys.argv[2])
    answer = work / "answer.txt"
    checks = {"answer_present": {"pass": answer.exists()},
              "answer_correct": {"pass": answer.exists() and answer.read_text().strip() == "42"}}
    entry = work / "solve.py"
    rerun = entry.exists() and subprocess.run([sys.executable, str(entry)], capture_output=True, text=True,
                                              timeout=30).stdout.strip() == "42"
    checks["entrypoint_reruns"] = {"pass": rerun}
    (out / "grade.json").write_text(json.dumps({"all_automated_checks_pass": all(c["pass"] for c in checks.values()),
                                                "checks": checks}))
""")

# Answers 42 only when skills are installed in its workspace (or FAKE_ALWAYS is set), reports token usage like Codex,
# and with FAKE_TAMPER set edits an installed SKILL.md. Started as python -c, so it needs no file outside the workspace
# (inside the sandbox, the temporary folders are empty).
FAKE_AGENT = textwrap.dedent("""
    import json, os, sys, time
    from pathlib import Path
    work = Path.cwd()
    task = sys.stdin.read()
    started = time.time()
    skills = sorted(str(p.relative_to(work)) for pattern in (".agents/skills/*/SKILL.md", ".claude/skills/*/SKILL.md")
                    for p in work.glob(pattern))
    if os.environ.get("FAKE_SLEEP"):
        time.sleep(float(os.environ["FAKE_SLEEP"]))
    (work / "answer.txt").write_text("42\\n" if skills or os.environ.get("FAKE_ALWAYS") else "41\\n")
    (work / "solve.py").write_text("print(42)\\n")
    if os.environ.get("FAKE_TAMPER") and skills:
        with open(work / skills[0], "a") as f:
            f.write("tampered\\n")
    print(json.dumps({"type": "start", "argv": sys.argv[1:], "skills": skills, "task_chars": len(task),
                      "started": started, "pointer": [p for p in ("AGENTS.md", "CLAUDE.md") if (work / p).exists()],
                      "cwd": str(work), "mrab_env": sorted(k for k in os.environ if k.startswith("MRAB_"))}))
    usage = {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50 + 10 * len(skills)}
    print(json.dumps({"type": "turn.completed", "usage": usage}))
    print("not json")
""")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Toy:
    """A temporary repository with one family (z-toy, domain toy) and one instance (toy-r1)."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="mrab-toy-")).resolve()
        self.src = self.root / "src"
        inst = self.src / "toy-r1"
        (inst / "private").mkdir(parents=True)
        (inst / "public" / "sub").mkdir(parents=True)
        (inst / "prompt.txt").write_text("Write 42 to answer.txt and a solve.py that prints it.\n")
        (inst / "public" / "task.json").write_text('{"task": "toy"}\n')
        (inst / "public" / "input.txt").write_text("input data\n")
        (inst / "public" / "sub" / "n.txt").write_text("nested\n")
        (inst / "private" / "grade_toy.py").write_text(TOY_GRADER)
        files = sorted(p for p in inst.rglob("*") if p.is_file())
        manifest = "# sha256 of every task file\n" + "".join(f"{sha(p)}  {p.relative_to(inst)}\n" for p in files)
        (inst / "FROZEN-SHA256.txt").write_text(manifest)
        self.packages = self.root / "packages"
        self.packages.mkdir()
        with tarfile.open(self.packages / "toy-r1.tar", "w") as t:
            t.add(inst, arcname="toy-r1")
        self.entry = dict(
            instance="toy-r1",
            source="toy-r1",
            manifest_sha256=sha(inst / "FROZEN-SHA256.txt"),
            grader="grade_toy.py",
            package="toy-r1.tar",
            cap_s=120,
            domain="toy",
            package_sha256=sha(self.packages / "toy-r1.tar"),
        )
        self.families = self.root / "families"
        (self.families / "z-toy").mkdir(parents=True)
        (self.families / "z-toy" / "instances.json").write_text(json.dumps([self.entry]))
        self.data = self.root / "data"
        self.runs = self.root / "runs"
        self.home = self.root / "home"
        self.home.mkdir()
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.agent = self.root / "fake_agent.py"
        self.agent.write_text(FAKE_AGENT)

    def agent_cmd(self, *extra: str) -> str:
        return json.dumps([sys.executable, "-c", FAKE_AGENT, *extra])

    @contextlib.contextmanager
    def active(self, **env: str) -> Iterator[None]:
        """Point mrab at the toy catalog, data, runs and an empty home folder."""
        clean = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "MRAB_DATA_URL", "FAKE_ALWAYS", "FAKE_TAMPER", "FAKE_SLEEP")
            and (not k.startswith("MRAB_") or k == "MRAB_SANDBOX")
        }
        clean.update(
            {
                "MRAB_DATA": str(self.data),
                "MRAB_RUNS": str(self.runs),
                "MRAB_WORK": str(self.stage),
                "HOME": str(self.home),
                **env,
            }
        )
        with mock.patch.dict(os.environ, clean, clear=True), mock.patch.object(catalog, "FAMILIES_DIR", self.families):
            yield

    def fetch(self) -> None:
        with self.active():
            code, out, err = run_cli(["fetch", "toy-r1", "--from-dir", str(self.src)])
        assert code == 0, err


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    """Run mrab in-process; returns (exit status, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main(argv)
        except SystemExit as e:
            if isinstance(e.code, str):
                err.write(e.code + "\n")
                code = 1
            else:
                code = e.code or 0
    return code, out.getvalue(), err.getvalue()


_SANDBOX: list[bool] = []


def sandbox_available() -> bool:
    """True when the per-arm sandbox works on this machine (checked once, with a throwaway toy)."""
    if not _SANDBOX:
        from mragentbench import isolation

        toy = Toy()
        with toy.active():
            hidden = isolation.hidden_paths(toy.runs, toy.data, toy.stage)
            _SANDBOX.append(not isolation.probe_sandbox(toy.stage, hidden))
    return _SANDBOX[0]


def isolation_mode() -> str:
    """The isolation that the pair tests use: the sandbox where available, otherwise none."""
    return "sandbox" if sandbox_available() else "none"
