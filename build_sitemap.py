#!/usr/bin/env python3
"""Regenerate sitemap.xml from the homepage and the published blog posts.

The sitemap lists the homepage plus every non-draft post under blogs/, so search
engines can discover each page and see when it last changed. Blog slugs and draft
status come straight from build_blog.load_posts(), so the sitemap can never list
a page build_blog didn't write (or omit one it did).

    python3 build_sitemap.py           rewrite sitemap.xml in place
    python3 build_sitemap.py --check   exit 1 if sitemap.xml is stale; write nothing

The homepage <lastmod> is stamped with today's date, matching index.html's
"Last updated" footer -- both mark when the site was last regenerated. Each
post's <lastmod> is its own date.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import tempfile
from pathlib import Path

# Reuse the exact slug/date/draft logic the blog pages are built with, so the
# sitemap and the actual pages can never disagree.
from build_blog import load_posts

ROOT = Path(__file__).resolve().parent
SITEMAP = ROOT / "sitemap.xml"
SITE = "https://steventsluo.com"


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


def post_lastmod(post: dict) -> str:
    """A post's <lastmod> as YYYY-MM-DD, from its (year, month, day) sort key.
    A post dated only to the month (day == 0) is pinned to the 1st; an undated
    post (year == 0) falls back to today."""
    year, month, day = post["key"]
    if not year:
        return datetime.date.today().isoformat()
    return f"{year:04d}-{month:02d}-{max(day, 1):02d}"


def render_sitemap() -> str:
    today = datetime.date.today().isoformat()
    # (loc, lastmod, changefreq, priority)
    entries = [(f"{SITE}/", today, "weekly", "1.0")]
    for post in load_posts():
        if post["draft"]:
            continue
        entries.append(
            (f"{SITE}/blogs/{post['slug']}.html", post_lastmod(post), "monthly", "0.8")
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, changefreq, priority in entries:
        lines += [
            "  <url>",
            f"    <loc>{loc}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            f"    <changefreq>{changefreq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if sitemap.xml is out of date instead of rewriting it",
    )
    args = parser.parse_args()

    rendered = render_sitemap()
    current = SITEMAP.read_text(encoding="utf-8") if SITEMAP.exists() else None
    count = rendered.count("<url>")

    if rendered == current:
        print(f"sitemap: up to date ({count} URLs)")
        return 0
    if args.check:
        print("sitemap: out of date; run: python3 build.py", file=sys.stderr)
        return 1
    write_atomically(SITEMAP, rendered)
    print(f"sitemap: sitemap.xml updated ({count} URLs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
