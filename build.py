#!/usr/bin/env python3
"""Regenerate everything on the site: the News list, the blog pages, and the
footer's "Last updated" date.

    python3 build.py           regenerate in place
    python3 build.py --check   exit 1 if anything is stale (for a pre-commit hook)

Run this after editing news.md or anything under blogs/. The footer date is
stamped with today's date on every build, so it always reflects when the site
was last regenerated -- no need to edit index.html by hand.
"""

import datetime
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX_HTML = ROOT / "index.html"
STEPS = ["build_news.py", "build_blog.py"]

# The footer's "Last updated" date is rewritten between these markers, so it
# tracks the build date without anyone editing index.html directly.
UPDATED_RE = re.compile(
    r"(?P<begin><!-- UPDATED:BEGIN -->).*?(?P<end><!-- UPDATED:END -->)",
    re.DOTALL,
)


def write_atomically(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, preserving the original
    file's mode (mkstemp creates 0600, which would otherwise show up as a
    spurious git mode change)."""
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def stamp_footer(check: bool) -> int:
    """Rewrite the footer date to today. Returns 1 in --check mode if stale."""
    today = datetime.date.today().strftime("%d-%b-%Y")
    source = INDEX_HTML.read_text(encoding="utf-8")
    region = UPDATED_RE.search(source)
    if not region:
        print(
            "  footer: UPDATED markers not found in index.html; skipping",
            file=sys.stderr,
        )
        return 0

    updated = (
        source[: region.start()]
        + region.group("begin") + today + region.group("end")
        + source[region.end():]
    )
    if updated == source:
        if not check:
            print(f"  footer: up to date ({today})")
        return 0
    if check:
        print("  footer: out of date; run: python3 build.py", file=sys.stderr)
        return 1
    write_atomically(INDEX_HTML, updated)
    print(f"  footer: stamped {today}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    check = "--check" in args
    failed = 0
    for step in STEPS:
        result = subprocess.run([sys.executable, str(ROOT / step), *args])
        failed = failed or result.returncode
    # Stamp the footer last: the steps above rewrite index.html, so read it
    # only after they have finished.
    failed = failed or stamp_footer(check)
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
