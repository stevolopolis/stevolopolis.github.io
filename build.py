#!/usr/bin/env python3
"""Regenerate everything on the site: the News list and the blog pages.

    python3 build.py           regenerate in place
    python3 build.py --check   exit 1 if anything is stale (for a pre-commit hook)

Run this after editing news.md or anything under blogs/.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["build_news.py", "build_blog.py"]


def main() -> int:
    args = sys.argv[1:]
    failed = 0
    for step in STEPS:
        result = subprocess.run([sys.executable, str(ROOT / step), *args])
        failed = failed or result.returncode
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
