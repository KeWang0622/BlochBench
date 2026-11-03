#!/usr/bin/env python3
"""Compatibility entry point for the completed offline preview.

Use tools/build_offline_leaderboard.py directly for new workflows. Historical
runner-directory aggregation is retired so a rebuild cannot restore old results.
"""

from build_offline_leaderboard import main

if __name__ == "__main__":
    raise SystemExit(main())
