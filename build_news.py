#!/usr/bin/env python3
"""Regenerate the News list in index.html from news.md.

The News block on the homepage is generated, not hand-written. Edit news.md,
run this script, and it rewrites everything between the NEWS:BEGIN and NEWS:END
markers in index.html. Output is plain static HTML -- no JavaScript.

    python3 build_news.py           rewrite index.html in place
    python3 build_news.py --check   exit 1 if index.html is stale; write nothing

--check is for a pre-commit hook or CI, so news.md and index.html can't silently
drift apart.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NEWS_MD = ROOT / "news.md"
INDEX_HTML = ROOT / "index.html"

#: How many entries reach the page. Older ones stay in news.md unrendered.
MAX_ITEMS = 5

# The generated region of index.html, located by its marker comments. The indent
# of the BEGIN marker sets the indent of everything generated inside it.
REGION_RE = re.compile(
    r"(?P<indent>[ \t]*)(?P<begin><!-- NEWS:BEGIN[^>]*-->)"
    r".*?"
    r"(?P<end><!-- NEWS:END -->)",
    re.DOTALL,
)

ITEM_RE = re.compile(r"^\s*[-*]\s+(?P<rest>.+?)\s*$")
DATE_RE = re.compile(r"^(?P<y>\d{4})[/-](?P<m>\d{1,2})(?:[/-](?P<d>\d{1,2}))?$")

LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<url>[^)\s]+)\)")
CODE_RE = re.compile(r"`(?P<t>[^`]+)`")
BOLD_RE = re.compile(r"\*\*(?P<t>.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?P<t>[^*]+)\*(?!\*)")
UNDERSCORE_RE = re.compile(r"(?<!\w)_(?P<t>[^_]+)_(?!\w)")

SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")
ALLOWED_SCHEMES = {"http", "https", "mailto"}


def warn(lineno: int, message: str, line: str) -> None:
    print(f"news.md:{lineno}: {message}: {line.strip()!r}", file=sys.stderr)


def safe_url(url: str) -> bool:
    """Allow relative links and the usual web schemes; reject javascript:/data:."""
    scheme = SCHEME_RE.match(url)
    return scheme.group(1).lower() in ALLOWED_SCHEMES if scheme else True


def render_inline(text: str) -> str:
    """Escape HTML, then re-introduce a small whitelist of inline markdown.

    Escaping first is what makes this safe: a literal '<' in news.md becomes
    '&lt;' and can never turn into a tag. Only the patterns matched below are
    allowed to produce markup.
    """
    out = html.escape(text)

    def link(match: re.Match) -> str:
        url = match.group("url")
        if not safe_url(html.unescape(url)):
            return match.group(0)  # leave the raw text visible rather than link it
        return f'<a href="{url}">{match.group("text")}</a>'

    out = LINK_RE.sub(link, out)
    out = CODE_RE.sub(lambda m: f'<code>{m.group("t")}</code>', out)
    out = BOLD_RE.sub(lambda m: f'<strong>{m.group("t")}</strong>', out)
    out = ITALIC_RE.sub(lambda m: f'<em>{m.group("t")}</em>', out)
    out = UNDERSCORE_RE.sub(lambda m: f'<em>{m.group("t")}</em>', out)
    return out


def parse_news(path: Path) -> list[dict]:
    """Read news.md into entries sorted newest-first.

    An entry that lacks a parseable 'YYYY/MM:' prefix is kept and sorted to the
    very top rather than dropped -- a typo in a date should be immediately
    visible on the page, not silently pushed below the MAX_ITEMS cut.
    """
    items: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = ITEM_RE.match(raw)
        if not match:
            warn(lineno, "not a '- ' list item, skipped", raw)
            continue

        rest = match.group("rest")
        head, sep, tail = rest.partition(":")
        date = DATE_RE.match(head.strip()) if sep else None
        if date and tail.strip():
            day = int(date.group("d") or 0)
            key = (0, int(date.group("y")), int(date.group("m")), day)
            items.append({"key": key, "date": head.strip(), "body": tail.strip()})
        else:
            warn(lineno, "no 'YYYY/MM:' date prefix, pinned to top so you notice", raw)
            items.append({"key": (1, 0, 0, 0), "date": "", "body": rest})

    # Stable sort: entries sharing a date keep their news.md order.
    items.sort(key=lambda item: item["key"], reverse=True)
    return items


def render_block(items: list[dict], indent: str) -> str:
    lines = [f'{indent}<ul class="news">']
    for item in items[:MAX_ITEMS]:
        body = render_inline(item["body"])
        if item["date"]:
            date = html.escape(item["date"])
            lines.append(
                f'{indent}  <li><span class="news-date">{date}</span>{body}</li>'
            )
        else:
            lines.append(f"{indent}  <li>{body}</li>")
    lines.append(f"{indent}</ul>")
    return "\n".join(lines)


def build() -> tuple[str, list[dict]]:
    items = parse_news(NEWS_MD)
    source = INDEX_HTML.read_text(encoding="utf-8")

    region = REGION_RE.search(source)
    if not region:
        sys.exit(
            "error: could not find the '<!-- NEWS:BEGIN ... -->' and "
            "'<!-- NEWS:END -->' markers in index.html"
        )

    indent = region.group("indent")
    block = render_block(items, indent)
    replacement = (
        f'{indent}{region.group("begin")}\n{block}\n{indent}{region.group("end")}'
    )
    return source[: region.start()] + replacement + source[region.end() :], items


def write_atomically(path: Path, text: str) -> None:
    """Write via a temp file in the same directory so a crash can't truncate.

    mkstemp creates the temp file 0600, so carry the original file's mode over
    to the replacement -- otherwise rewriting a file quietly tightens its
    permissions and git records a spurious mode change.
    """
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if index.html is out of date instead of rewriting it",
    )
    args = parser.parse_args()

    rendered, items = build()
    shown, total = min(len(items), MAX_ITEMS), len(items)

    if args.check:
        if rendered != INDEX_HTML.read_text(encoding="utf-8"):
            print("index.html news block is out of date; run: python3 build.py", file=sys.stderr)
            return 1
        print(f"news: up to date ({shown} of {total} entries shown)")
        return 0

    if rendered == INDEX_HTML.read_text(encoding="utf-8"):
        print(f"news: already up to date ({shown} of {total} entries shown)")
        return 0

    write_atomically(INDEX_HTML, rendered)
    print(f"news: index.html updated ({shown} of {total} entries shown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
