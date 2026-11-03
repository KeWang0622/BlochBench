#!/usr/bin/env python3
"""BlochBench scoring (standard library only); kept for compatibility, the code lives in mragentbench.scoring.

python3 score.py runs.csv            -> completion, pass^k, cost per verified result, by domain and config
python3 score.py --paired pairs.csv  -> completion with and without the add-on, discordant pairs, exact McNemar P
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

if __package__:
    from .scoring import mcnemar, paired, single
else:  # run as a script: python3 mragentbench/score.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mragentbench.scoring import mcnemar, paired, single

__all__ = ["mcnemar", "paired", "single"]


def main(argv: list[str]) -> None:
    if argv[0] == "--paired":
        with open(argv[1]) as f:
            paired(list(csv.DictReader(f)))
    else:
        with open(argv[0]) as f:
            single(list(csv.DictReader(f)))


if __name__ == "__main__":
    main(sys.argv[1:])
