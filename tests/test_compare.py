"""Tests for mrab compare and the paired statistics, on synthetic run records.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import csv
import itertools
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from toy import run_cli

from mragentbench import client, scoring
from mragentbench.common import MrabError
from mragentbench.compare import compare_configs, compare_lines

BASE, ADDON = "codex-m", "codex-m+x@1"
# (instance, domain, run, base verified, add-on verified, base tokens, add-on tokens)
RUNS = [
    ("a-r1", "seq", 1, False, True, 100, 150),
    ("a-r1", "seq", 2, True, True, 100, 150),
    ("b-r1", "seq", 1, False, True, 200, 200),
    ("c-r1", "mrs", 1, True, False, 100, 50),
    ("c-r1", "mrs", 2, False, True, 100, 300),
    ("d-r1", "diff", 1, False, False, 0, 10),
]
MANIFEST = {
    "name": "x",
    "version": "1",
    "content_sha256": "ab" * 32,
    "exposure": {"public_instances_seen": "partial", "details": "v4 families"},
}


def write_run(
    root: Path, config: str, instance: str, domain: str, run: int, verified: bool | None, tokens: int, **extra: object
) -> Path:
    folder = root / config / instance / f"run{run}"
    folder.mkdir(parents=True)
    record = dict(
        instance=instance,
        family=instance[0] + "-fam",
        domain=domain,
        config=config,
        agent="codex",
        model="m",
        addon=None,
        run=run,
        argv=[],
        cap_s=60,
        timed_out=False,
        returncode=0,
        wall_s=1.0,
        usage={"input_tokens": tokens - tokens // 10, "output_tokens": tokens // 10, "cached_input_tokens": 9},
        verified=verified,
        failed_checks=[],
        argv_template=["codex", "exec"],
        effort="medium",
        agent_version="codex 1.0",
        mrab_version="0.1.0.dev0",
        manifest_sha256="cd" * 32,
        isolation={"mode": "sandbox", "isolated": True},
        instance_check={"before": "ok", "after": {"ok": True, "mismatches": []}},
        pair=f"{instance}/run{run}/t",
        baseline_clean=True,
        contamination={"clean": True},
        interrupted=False,
    )
    if config != BASE:
        record.update(
            addon="/x",
            addon_manifest=MANIFEST,
            addon_pointer=True,
            addon_installed_sha256="ef" * 32,
            addon_check={"intact": True, "changed": []},
        )
    record.update(extra)
    (folder / "run.json").write_text(json.dumps(record))
    return folder


def edit(folder: Path, **changes: object) -> None:
    record = json.loads((folder / "run.json").read_text())
    record.update(changes)
    (folder / "run.json").write_text(json.dumps(record))


class CompareTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="mrab-compare-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        for i, (inst, domain, run, base_ok, addon_ok, base_tok, addon_tok) in enumerate(RUNS):
            write_run(self.root, BASE, inst, domain, run, base_ok, base_tok)
            check = {"intact": i != 1, "changed": [] if i != 1 else ["s/SKILL.md"]}
            write_run(self.root, ADDON, inst, domain, run, addon_ok, addon_tok, addon_check=check)
        write_run(self.root, BASE, "e-r1", "hw", 1, True, 100)

    def compare(self, *extra: str) -> tuple[int, str, str]:
        return run_cli(["compare", str(self.root), "--base", BASE, "--addon", ADDON, *extra])

    def test_statistics(self) -> None:
        result = compare_configs(self.root, BASE, ADDON)
        self.assertEqual(result["pairs"], 6)
        self.assertEqual((result["base"]["verified"], result["addon"]["verified"]), (2, 4))
        self.assertEqual((result["addon_only"], result["base_only"]), (3, 1))
        self.assertEqual(result["mcnemar_p"], scoring.mcnemar(3, 1))
        self.assertEqual(result["difference_pp"], 33.33)
        level = result["instance_level"]
        self.assertEqual((result["n_instances"], level["better"], level["worse"], level["tied"]), (4, 2, 0, 2))
        self.assertAlmostEqual(level["mean_difference"], (0.5 + 1 + 0 + 0) / 4)
        self.assertEqual((level["permutation_p"], level["sign_test_p"]), (0.5, 0.5))
        self.assertEqual(
            result["domains"],
            {
                "diff": {"pairs": 1, "base_verified": 0, "addon_verified": 0},
                "mrs": {"pairs": 2, "base_verified": 1, "addon_verified": 1},
                "seq": {"pairs": 3, "base_verified": 1, "addon_verified": 3},
            },
        )
        self.assertEqual((result["tokens"]["base_total"], result["tokens"]["addon_total"]), (600, 860))
        self.assertAlmostEqual(result["tokens"]["median_pair_ratio"], 1.5)
        self.assertEqual(result["unmatched"], {"base_only": ["e-r1/run1"], "addon_only": []})
        self.assertEqual(result["started_together"], 6)
        self.assertEqual(result["addon_modified"], ["a-r1/run2"])

    def test_command(self) -> None:
        out_json, out_csv = self.root / "c.json", self.root / "pairs.csv"
        code, out, err = self.compare("--json", str(out_json), "--csv", str(out_csv))
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertEqual(lines[0], "base   codex-m      verified 2/6 (33.3%, 95% CI 9.7-70.0)")
        self.assertEqual(lines[1], "add-on codex-m+x@1  verified 4/6 (66.7%, 95% CI 30.0-90.3)")
        self.assertTrue(lines[2].startswith("instances 4 (families 4): add-on better on 2, worse on 0, tied on 2; "))
        self.assertIn("mean difference +37.5 pp, 95% CI", lines[2])
        self.assertIn("(cluster bootstrap over instance clusters, 10000 resamples, seed 0)", lines[2])
        self.assertEqual(
            lines[3], "primary test, instance level: exact sign-flip permutation P 0.5; exact sign test P 0.5"
        )
        run_level = "pairs 6: base 2 (33.3%), with add-on 4 (66.7%), add-on only 3, base only 1, exact McNemar P 0.62"
        self.assertEqual(
            lines[4], "secondary, run level (treats repeated runs of an instance as independent): " + run_level
        )
        self.assertIn("unmatched runs left out: 1 base only, 0 add-on only", out)
        self.assertIn("public instances seen: partly", out)
        self.assertIn("warning: the installed add-on changed during 1 run(s): a-r1/run2", out)
        self.assertEqual(json.loads(out_json.read_text())["pairs"], 6)
        with open(out_csv) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(
            list(rows[0]),
            [
                "family",
                "instance",
                "run",
                "domain",
                "model",
                "base_passed",
                "addon_passed",
                "base_tokens",
                "addon_tokens",
            ],
        )
        paired = run_cli(["score", "--paired", str(out_csv)])[1].splitlines()
        self.assertEqual(paired[1], lines[3])
        self.assertEqual(paired[2], lines[4])
        code, out, _ = self.compare("--cluster", "family")
        self.assertIn("(cluster bootstrap over family clusters", out)

    def test_refuses_pairs_with_different_settings(self) -> None:
        changes = {
            "model": "m2",
            "cap_s": 30,
            "argv_template": ["codex", "exec", "-c", "model_reasoning_effort=high"],
            "effort": "high",
            "agent_version": "codex 2.0",
            "mrab_version": "0.0.9",
            "manifest_sha256": "00" * 32,
        }
        folder = self.root / ADDON / "b-r1" / "run1"
        original = json.loads((folder / "run.json").read_text())
        for name, value in changes.items():
            with self.subTest(name):
                edit(folder, **{name: value})
                code, _, err = self.compare("--allow-unpaired", "--allow-unisolated")
                self.assertEqual(code, 1)
                self.assertIn("were not run with the same settings", err)
                self.assertIn(f"b-r1/run1: {name} {original[name]!r} vs {value!r}", err)
                edit(folder, **{name: original[name]})
        self.assertIn(
            "the same configuration", run_cli(["compare", str(self.root), "--base", BASE, "--addon", BASE])[2]
        )

    def test_refuses_unpaired_runs_unless_allowed(self) -> None:
        edit(self.root / ADDON / "d-r1" / "run1", pair=None)
        code, _, err = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("pairs not started together by mrab pair", err)
        self.assertIn("d-r1/run1", err)
        code, out, _ = self.compare("--allow-unpaired")
        self.assertEqual(code, 0)
        self.assertIn("warning: 1 pair(s) not started together or not fully checked (--allow-unpaired): d-r1/run1", out)
        record = json.loads((self.root / BASE / "c-r1" / "run1" / "run.json").read_text())
        del record["agent_version"]
        (self.root / BASE / "c-r1" / "run1" / "run.json").write_text(json.dumps(record))
        self.assertIn("c-r1/run1: agent_version not recorded", self.compare()[2])

    def test_refuses_unisolated_or_unclean_pairs_unless_allowed(self) -> None:
        edit(self.root / BASE / "a-r1" / "run1", isolation={"mode": "none", "isolated": False})
        edit(
            self.root / BASE / "b-r1" / "run1",
            baseline_clean=False,
            contamination={"base_trace_mentions": ["add-on name 'x'"], "clean": False},
        )
        code, _, err = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("a-r1/run1: base arm not isolated", err)
        self.assertIn("b-r1/run1: baseline not clean (base_trace_mentions)", err)
        code, out, _ = self.compare("--allow-unisolated")
        self.assertEqual(code, 0)
        self.assertIn("warning: 2 problem(s) with isolation or baseline cleanliness", out)

    def test_refuses_mixed_addon_settings(self) -> None:
        folder = self.root / ADDON / "c-r1" / "run1"
        for name, value in (
            ("addon_pointer", False),
            ("addon_installed_sha256", "11" * 32),
            ("addon_manifest", dict(MANIFEST, content_sha256="cd" * 32)),
        ):
            with self.subTest(name):
                original = json.loads((folder / "run.json").read_text())[name]
                edit(folder, **{name: value})
                code, _, err = self.compare()
                self.assertEqual(code, 1)
                self.assertIn(f"the runs of {ADDON} used 2 different", err)
                edit(folder, **{name: original})
        edit(self.root / BASE / "a-r1" / "run1", addon="/skills")
        self.assertIn("base runs of codex-m record an add-on", self.compare()[2])

    def test_incomplete_and_interrupted_runs(self) -> None:
        started = self.root / ADDON / "d-r1" / "run2"
        started.mkdir(parents=True)
        (started / "started.json").write_text("{}")
        write_run(self.root, BASE, "d-r1", "diff", 2, True, 10)
        code, _, err = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("started runs without run.json", err)
        self.assertIn(f"{ADDON}/d-r1/run2", err)
        result = compare_configs(self.root, BASE, ADDON, allow_incomplete=True)
        self.assertEqual(result["pairs"], 7)
        self.assertEqual((result["base_only"], result["incomplete"]), (2, [f"{ADDON}/d-r1/run2"]))
        edit(self.root / ADDON / "b-r1" / "run1", verified=False, interrupted=True)
        result = compare_configs(self.root, BASE, ADDON, allow_incomplete=True)
        self.assertEqual(result["interrupted"], [f"{ADDON}/b-r1/run1"])
        self.assertEqual(result["addon"]["verified"], 3)
        self.assertIn("warning: 1 interrupted run(s) counted as failures", "\n".join(compare_lines(result)))

    def test_ungraded_pairs_are_left_out(self) -> None:
        edit(self.root / ADDON / "b-r1" / "run1", verified=None)
        result = compare_configs(self.root, BASE, ADDON)
        self.assertEqual((result["pairs"], result["ungraded"]), (5, ["b-r1/run1"]))

    def test_run_folders_are_matched_exactly(self) -> None:
        source = self.root / BASE / "a-r1" / "run1"
        backup = self.root / BASE / "a-r1" / "run1.bak"  # review finding: a copied folder replaced run1
        shutil.copytree(source, backup)
        edit(backup, verified=True)
        code, _, err = self.compare()
        self.assertEqual(code, 1)
        self.assertIn(f"{BASE}/a-r1/run1.bak holds a run.json but is not named run<k>", err)
        (backup / "run.json").unlink()
        code, out, _ = self.compare()
        self.assertEqual(code, 0)
        self.assertIn(f"warning: 1 folder(s) not named run<k> ignored: {BASE}/a-r1/run1.bak", out)
        self.assertEqual(compare_configs(self.root, BASE, ADDON)["base"]["verified"], 2)
        shutil.rmtree(backup)
        moved = self.root / BASE / "a-r1" / "run7"
        shutil.copytree(source, moved)  # a run.json whose (instance, run) disagrees with its folder
        self.assertIn(
            f"{BASE}/a-r1/run7/run.json records instance a-r1 run 1, not those of its folder", self.compare()[2]
        )
        shutil.rmtree(moved)
        shutil.copytree(source, self.root / BASE / "a-r1" / "run01")
        self.assertIn("run01 holds a run.json but is not named run<k>", self.compare()[2])
        shutil.rmtree(self.root / BASE / "a-r1" / "run01")
        shutil.copytree(source, self.root / "other" / "a-r1" / "run1")  # copied from another configuration
        edit(self.root / "other" / "a-r1" / "run1", config=BASE)
        self.assertIn(
            "records configuration codex-m, not other",
            run_cli(["compare", str(self.root), "--base", "other", "--addon", ADDON])[2],
        )

    def test_collect_and_bundle_skip_misnamed_folders(self) -> None:
        shutil.copytree(self.root / BASE / "a-r1" / "run1", self.root / BASE / "a-r1" / "run1.bak")
        code, out, err = run_cli(["collect", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("run1.bak is not named run<k>; left out", err)
        self.assertNotIn("run1.bak", out)
        self.assertEqual(len(out.splitlines()), 1 + 7 + 6)
        (self.root / BASE / "a-r1" / "run1.bak" / "work").mkdir()
        with self.assertRaises(SystemExit) as ctx:
            client.find_runs(self.root, BASE)
        self.assertIn("run1.bak is not named run<k>", str(ctx.exception.code))

    def test_errors(self) -> None:
        self.assertEqual(
            run_cli(["compare", str(self.root), "--base", "nope", "--addon", ADDON])[2],
            f"no runs of configuration nope in {self.root}\n",
        )
        write_run(self.root, "other", "z-r1", "hw", 1, True, 1)
        self.assertIn(
            "no (instance, run) pairs in common",
            run_cli(["compare", str(self.root), "--base", BASE, "--addon", "other"])[2],
        )


class InstanceLevelTest(unittest.TestCase):
    """Review finding 2: repeated runs of an instance are not independent pairs."""

    @staticmethod
    def rows(spec: list[tuple[int, int]], runs: int) -> list[dict]:
        return [
            dict(instance=f"i{i}", family=f"f{i}", domain="d", base_passed=b, addon_passed=a)
            for i, (b, a) in enumerate(spec)
            for _ in range(runs)
        ]

    def test_six_instances_five_runs(self) -> None:
        rows = self.rows([(0, 1), (0, 1), (1, 1), (1, 1), (0, 0), (0, 0)], runs=5)
        run_level = scoring.paired_stats(rows)
        self.assertLess(run_level["mcnemar_p"], 0.002)  # ten discordant runs look decisive at the run level
        level = scoring.instance_stats(rows)
        self.assertEqual((level["permutation_p"], level["sign_test_p"]), (0.5, 0.5))
        self.assertEqual((level["n_instances"], level["better"], level["tied"]), (6, 2, 4))
        self.assertEqual(level["ci95"], (0.0, 2 / 3))

    def test_sign_flip_matches_brute_force(self) -> None:
        rng = random.Random(1)
        for _ in range(30):
            diffs = []
            for _ in range(rng.randint(1, 7)):
                n = rng.randint(1, 4)
                diffs.append((rng.randint(0, n), rng.randint(0, n), n))
            values = [(a - b) / n for a, b, n in diffs]
            observed = abs(sum(values))
            flips = list(itertools.product((1, -1), repeat=len(values)))
            extreme = sum(
                abs(sum(s * v for s, v in zip(signs, values, strict=True))) >= observed - 1e-12 for signs in flips
            )
            self.assertAlmostEqual(scoring.sign_flip_p(diffs), extreme / len(flips))

    def test_false_positive_rate_with_heterogeneous_instances(self) -> None:
        # 30 instances x 5 runs, the add-on helps some instances and hurts others by the same amount: no mean effect.
        rng = random.Random(0)
        trials, instance_rejects, run_rejects = 300, 0, 0
        for _ in range(trials):
            rows = []
            for inst in range(30):
                p = rng.random()
                pa = min(max(p + rng.choice((-0.3, 0.3)), 0.0), 1.0)
                for _ in range(5):
                    rows.append(
                        dict(instance=f"i{inst}", family="f", domain="d", base_passed=int(rng.random() < p),
                             addon_passed=int(rng.random() < pa))
                    )  # fmt: skip
            instance_rejects += scoring.instance_stats(rows, resamples=10)["permutation_p"] < 0.05
            run_rejects += scoring.paired_stats(rows)["mcnemar_p"] < 0.05
        self.assertLessEqual(instance_rejects / trials, 0.08)
        self.assertGreater(run_rejects, instance_rejects)

    def test_score_paired_without_instance_column_is_run_level_only(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="mrab-score-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "pairs.csv").write_text("family,domain,model,base_passed,addon_passed\nf,d,m,0,1\n")
        code, out, err = run_cli(["score", "--paired", str(root / "pairs.csv")])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("pairs 1: "))
        self.assertIn("no instance column", err)

    def test_compare_error_type(self) -> None:
        with self.assertRaises(MrabError):
            compare_configs(Path(tempfile.gettempdir()) / "mrab-no-such-folder", BASE, ADDON)


if __name__ == "__main__":
    unittest.main()
