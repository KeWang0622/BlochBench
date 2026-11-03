#!/usr/bin/env python3
"""Grade one arm of heldout-v7-mrsquant: python grade_mrsquant_arm.py <workspace_dir> <eval_dir> -> <eval_dir>/grade.json"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v7common as C
from grade_mrsquant import grade

if __name__ == '__main__':
    C.arm_main(grade)

