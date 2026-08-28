#!/usr/bin/env python3
"""Generate blog pages from blogs/*.md and refresh the homepage Blogs list.

Each post is a markdown file with a '---' fenced frontmatter header:

    ---
    title: Why We Should Do AI Research
    date: 2023/08/26
    abstract: A short TL;DR shown on the homepage and atop the post.
    draft: false
    ---

    Body markdown here, with a footnote.[^1]

    [^1]: Footnotes become margin sidenotes, not endnotes.

Running this writes blogs/<slug>.html for every non-draft post and rewrites the
region between BLOGS:BEGIN and BLOGS:END in index.html.

    python3 build_blog.py           generate pages and update index.html
    python3 build_blog.py --check   exit 1 if anything is stale; write nothing

Footnotes are the reason this doesn't just shell out to a markdown CLI: standard
markdown renders them as endnotes at the bottom of the page, and we want them
beside the paragraph that cites them. See sidenotes() below.
"""

from __future__ import annotations

import argparse
import html
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from html.entities import name2codepoint
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit(
        "error: the 'markdown' package is required.\n"
        "       pip install markdown        (or: conda install markdown)"
    )

ROOT = Path(__file__).resolve().parent
BLOGS_DIR = ROOT / "blogs"
INDEX_HTML = ROOT / "index.html"

MD_EXTENSIONS = ["extra", "sane_lists", "smarty", "attr_list", "md_in_html"]

# <details> only renders its markdown body when tagged for md_in_html, so tag it
# automatically rather than making every post remember the attribute.
DETAILS_RE = re.compile(r"<details(?![^>]*markdown=)")

# $$...$$ and $...$ are pulled out before markdown runs and put back after, so
# markdown can't mangle a formula (an underscore becoming <em>, a backslash
# being eaten). MathJax then renders the \( \) and \[ \] delimiters.
MATH_BLOCK_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
MATH_INLINE_RE = re.compile(r"(?<!\$)\$(?!\s)([^\$\n]+?)(?<!\s)\$(?!\$)")
FENCE_RE = re.compile(r"(```.*?```|~~~.*?~~~)", re.DOTALL)
INLINE_CODE_RE = re.compile(r"(`[^`\n]*`)")

MATHJAX = """    <script>
      window.MathJax = {
        chtml: {scale: 1.15},
        tex: {inlineMath: [['\\\\(', '\\\\)']], displayMath: [['\\\\[', '\\\\]']]},
        options: {skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']}
      };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
"""


def protect_math(text: str) -> tuple[str, list[tuple[str, bool]]]:
    """Swap math spans for inert tokens. Code blocks and code spans are skipped,
    so a stray '$' inside a snippet is never mistaken for a formula."""
    store: list[tuple[str, bool]] = []

    def stash(body: str, block: bool) -> str:
        store.append((body.strip(), block))
        return f"zzmath{len(store) - 1}zz"

    out = []
    for i, part in enumerate(FENCE_RE.split(text)):
        if i % 2:                      # a fenced code block: leave alone
            out.append(part)
            continue
        for j, chunk in enumerate(INLINE_CODE_RE.split(part)):
            if j % 2:                  # an inline code span: leave alone
                out.append(chunk)
                continue
            chunk = MATH_BLOCK_RE.sub(lambda m: stash(m.group(1), True), chunk)
            chunk = MATH_INLINE_RE.sub(lambda m: stash(m.group(1), False), chunk)
            out.append(chunk)
    return "".join(out), store


def restore_math(rendered: str, store: list[tuple[str, bool]]) -> str:
    for index, (body, block) in enumerate(store):
        escaped = html.escape(body, quote=False)
        delimited = f"\\[{escaped}\\]" if block else f"\\({escaped}\\)"
        rendered = rendered.replace(f"zzmath{index}zz", delimited)
    return rendered


REGION_RE = re.compile(
    r"(?P<indent>[ \t]*)(?P<begin><!-- BLOGS:BEGIN[^>]*-->)"
    r".*?"
    r"(?P<end><!-- BLOGS:END -->)",
    re.DOTALL,
)

# python-markdown emits '<sup id="fnref:1"><a class="footnote-ref" ...>1</a></sup>'
# at the citation and collects the bodies in a trailing '<div class="footnote">'.
FNREF_RE = re.compile(
    r'<sup id="fnref:(?P<id>[^"]+)">'
    r'<a class="footnote-ref" href="#fn:[^"]*">(?P<num>[^<]*)</a></sup>'
)
FOOTNOTE_DIV_RE = re.compile(r'\n?<div class="footnote">.*?</div>\s*$', re.DOTALL)

# A frontmatter line opens a new key only if it starts with "word:"; anything
# else (a "- bullet", a wrapped sentence) continues the value above it.
KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:(?P<value>.*)$")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

FILENAME_DATE_RE = re.compile(r"^(?P<y>\d{2})(?P<m>\d{2})(?P<d>\d{2})[-_]")
DATE_RE = re.compile(r"^(?P<y>\d{4})[/-](?P<m>\d{1,2})(?:[/-](?P<d>\d{1,2}))?$")

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

TRUE_WORDS = {"true", "yes", "1", "on"}


# --------------------------------------------------------------------------
# frontmatter
# --------------------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata, body). Missing frontmatter yields an empty dict."""
    if not text.lstrip().startswith("---"):
        return {}, text

    text = text.lstrip()
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    header = text[3:end]
    body = text[end + 4:].lstrip("\n")

    meta: dict[str, str] = {}
    key = None
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = KEY_RE.match(line)
        if match:
            key = match.group("key").lower()
            meta[key] = match.group("value").strip().strip('"').strip("'")
        elif key:
            # A line that doesn't open a new key continues the previous value,
            # which is what lets an abstract carry its own bullet list.
            meta[key] = f"{meta[key]}\n{line.rstrip()}".strip()
    return meta, body


def parse_date(meta: dict, path: Path) -> tuple[tuple, str]:
    """Return (sort_key, display_date), falling back to a YYMMDD- filename."""
    raw = meta.get("date", "").strip()
    match = DATE_RE.match(raw) if raw else None
    if match:
        year, month = int(match.group("y")), int(match.group("m"))
        day = int(match.group("d") or 0)
    else:
        stamp = FILENAME_DATE_RE.match(path.name)
        if stamp:
            year = 2000 + int(stamp.group("y"))
            month, day = int(stamp.group("m")), int(stamp.group("d"))
            if raw:
                print(
                    f"  {path.name}: unparseable date {raw!r}, using the filename date",
                    file=sys.stderr,
                )
        else:
            print(f"  {path.name}: no usable date, sorting last", file=sys.stderr)
            return (0, 0, 0), raw or "undated"

    name = MONTHS[month - 1] if 1 <= month <= 12 else str(month)
    display = f"{name} {day}, {year}" if day else f"{name} {year}"
    return (year, month, day), display


# --------------------------------------------------------------------------
# footnotes -> sidenotes
# --------------------------------------------------------------------------

def inner_xml(elem: ET.Element) -> str:
    """Serialize an element's children (and their tails) without its own tag."""
    parts = [elem.text or ""]
    for child in elem:
        parts.append(ET.tostring(child, encoding="unicode", method="html"))
    return "".join(parts)


def flatten(elem: ET.Element) -> str:
    """Render one footnote child as inline HTML, with no block-level tags.

    A sidenote is injected inside a <p>. Any block element in there -- a nested
    list, a code block -- makes the browser close that paragraph early and the
    float lands in the wrong place. So lists become bulleted lines joined by
    <br>, and code blocks collapse to inline code.
    """
    tag = elem.tag
    if tag in ("ul", "ol"):
        items = []
        for number, item in enumerate(elem.findall("li"), 1):
            marker = f"{number}. " if tag == "ol" else "\u2022 "
            items.append(marker + flatten_children(item))
        return "<br>".join(items)
    if tag == "pre":
        return f'<code>{html.escape("".join(elem.itertext()).strip())}</code>'
    if tag in ("p", "blockquote", "div", "li"):
        return flatten_children(elem)

    # Already inline: serialize without its tail, which the caller appends.
    tail, elem.tail = elem.tail, None
    out = ET.tostring(elem, encoding="unicode", method="html")
    elem.tail = tail
    return out


def flatten_children(elem: ET.Element) -> str:
    parts = [elem.text or ""]
    for child in elem:
        parts.append(flatten(child))
        parts.append(child.tail or "")
    return "".join(parts).strip()


# XML knows only these five by name; smarty emits &rsquo;, &hellip; and friends,
# which would make the XML parser below choke on an undefined entity.
XML_SAFE_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
NAMED_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")


def numeric_entities(text: str) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name in XML_SAFE_ENTITIES:
            return match.group(0)
        code = name2codepoint.get(name)
        return f"&#{code};" if code else match.group(0)

    return NAMED_ENTITY_RE.sub(replace, text)


def footnote_bodies(div_html: str) -> dict[str, str]:
    """Map footnote id -> inline HTML, parsed from the trailing footnote div.

    Parsed as XML rather than by regex because a footnote may itself contain
    nested lists, so counting '</li>' is not reliable.
    """
    root = ET.fromstring(numeric_entities(div_html))
    bodies: dict[str, str] = {}
    for li in root.iter("li"):
        ident = (li.get("id") or "")[len("fn:"):]
        if not ident:
            continue

        for parent in li.iter():
            for child in list(parent):
                if child.tag == "a" and child.get("class") == "footnote-backref":
                    parent.remove(child)

        blocks = []
        if (li.text or "").strip():
            blocks.append(li.text.strip())
        for child in li:
            chunk = flatten(child).strip().rstrip("\xa0").strip()
            if chunk:
                blocks.append(chunk)

        bodies[ident] = "<br><br>".join(blocks)
    return bodies


def sidenotes(body_html: str, source: str) -> str:
    """Move footnote bodies inline, next to the sentence that cites them.

    The markup deliberately uses <span>, not <aside> or <div>: a sidenote is
    injected mid-paragraph, and a block element inside <p> makes the browser
    close the paragraph early and wreck the layout. CSS floats the span into
    the right margin.
    """
    div = FOOTNOTE_DIV_RE.search(body_html)
    if not div:
        return body_html

    try:
        bodies = footnote_bodies(div.group(0).strip())
    except ET.ParseError as exc:
        print(
            f"  {source}: could not parse footnotes ({exc}); leaving them at the "
            "bottom of the page",
            file=sys.stderr,
        )
        return body_html

    body_html = body_html[: div.start()] + body_html[div.end():]

    missing: list[str] = []

    def replace(match: re.Match) -> str:
        ident, num = match.group("id"), match.group("num")
        content = bodies.get(ident)
        if content is None:
            missing.append(ident)
            return match.group(0)
        return (
            f'<sup class="sidenote-ref">{num}</sup>'
            f'<span class="sidenote">'
            f'<sup class="sidenote-num">{num}</sup>{content}</span>'
        )

    out = FNREF_RE.sub(replace, body_html)
    if missing:
        print(f"  {source}: footnote(s) with no body: {', '.join(missing)}", file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

PAGE_TEMPLATE = """<!DOCTYPE HTML>
<html lang="en">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

    <title>{title} &middot; Steven Luo</title>

    <meta name="author" content="Steven Luo">
    <meta name="description" content="{description}">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="shortcut icon" href="../images/favicon/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" type="text/css" href="../stylesheet.css">
{mathjax}
  </head>

  <body>
    <div class="post">
      <p class="post-nav"><a href="../index.html">&larr; Back to homepage</a></p>
      <h1 class="post-title">{title}</h1>
      <p class="post-date">{date}</p>
{abstract}
      <div class="post-body">
{content}
      </div>
      <p class="post-nav post-nav-bottom"><a href="../index.html">&larr; Back to homepage</a></p>
    </div>
  </body>
</html>
"""

ABSTRACT_TEMPLATE = """      <div class="post-abstract">
        <span class="post-abstract-label">TL;DR</span>
        {abstract}
      </div>
"""


def blank_line_before_lists(text: str) -> str:
    """Markdown only starts a list if a blank line precedes it. Frontmatter is
    written without one, so add it -- otherwise a bulleted abstract silently
    renders as a paragraph full of hyphens."""
    out: list[str] = []
    for line in text.splitlines():
        starts_list = LIST_ITEM_RE.match(line)
        if starts_list and out and out[-1].strip() and not LIST_ITEM_RE.match(out[-1]):
            out.append("")
        out.append(line)
    return "\n".join(out)


def render_abstract(md: markdown.Markdown, text: str) -> str:
    """Render the abstract as markdown.

    A one-line abstract is unwrapped from its <p> so it can sit inline; a
    multi-line one keeps its block markup, so an abstract can carry a list.
    """
    if not text.strip():
        return ""
    out = md.reset().convert(blank_line_before_lists(text)).strip()
    if out.count("<p>") == 1 and out.startswith("<p>") and out.endswith("</p>"):
        return out[3:-4]
    return out


def indent_block(text: str, spaces: str) -> str:
    """Indent generated HTML for readability -- but never inside <pre>, where
    leading whitespace is part of the code, not formatting."""
    out, in_pre = [], False
    for line in text.splitlines():
        if in_pre:
            out.append(line)
            in_pre = "</pre>" not in line
            continue
        out.append(spaces + line if line.strip() else line)
        if "<pre" in line and "</pre>" not in line:
            in_pre = True
    return "\n".join(out)


# Average adult silent-reading pace for prose; used to turn a word count into
# the "Estimated Reading Time" shown under each title.
READING_WPM = 200

MATH_SPAN_RE = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def reading_stats(content_html: str) -> tuple[int, int]:
    """Return (word_count, minutes) for a post's rendered body.

    Math spans (LaTeX between \\( \\) or \\[ \\]) and HTML tags are dropped first
    so command names and markup don't inflate the count; the sidenote text that
    was folded inline is left in, since a reader does read it.
    """
    text = MATH_SPAN_RE.sub(" ", content_html)
    text = TAG_RE.sub(" ", text)
    words = len(html.unescape(text).split())
    return words, max(1, math.ceil(words / READING_WPM))


def reading_meta(post: dict) -> str:
    """The '| N words | Estimated Reading Time: Mmin' suffix for a date row.
    Contains no HTML-special characters, so it is safe to append after escaping
    the date it follows."""
    return f' | {post["words"]:,} words | Estimated Reading Time: {post["read_min"]}min'


def load_posts() -> list[dict]:
    if not BLOGS_DIR.is_dir():
        return []

    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    abstract_md = markdown.Markdown(extensions=["extra", "sane_lists", "smarty"])

    posts = []
    for path in sorted(BLOGS_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue

        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))

        # A post with no 'title:' can lead with an H1 instead; lift it out so the
        # page template does not print the title twice.
        title = meta.get("title")
        if not title:
            heading = re.match(r"\s*#\s+(?P<title>.+)", body)
            if heading:
                title = heading.group("title").strip()
                body = body[heading.end():].lstrip("\n")
            else:
                title = path.stem.replace("-", " ").replace("_", " ").title()

        sort_key, display_date = parse_date(meta, path)
        is_draft = meta.get("draft", "").lower() in TRUE_WORDS

        body = DETAILS_RE.sub('<details markdown="block"', body)
        protected, math = protect_math(body)
        rendered = restore_math(md.reset().convert(protected), math) if body.strip() else ""
        content = sidenotes(rendered, path.name) if body.strip() else ""
        words, read_min = reading_stats(content)
        posts.append(
            {
                "slug": path.stem,
                "path": path,
                "title": title,
                "abstract": render_abstract(abstract_md, meta.get("abstract", "")),
                "date": display_date,
                "key": sort_key,
                "draft": is_draft,
                "content": content,
                "math": bool(math),
                "words": words,
                "read_min": read_min,
            }
        )

    posts.sort(key=lambda post: post["key"], reverse=True)
    return posts


def render_page(post: dict) -> str:
    abstract = (
        ABSTRACT_TEMPLATE.format(abstract=post["abstract"]) if post["abstract"] else ""
    )
    description = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", post["abstract"])).strip()[:160]
    return PAGE_TEMPLATE.format(
        mathjax=MATHJAX if post.get("math") else "",
        title=html.escape(post["title"]),
        description=html.escape(description, quote=True),
        date=html.escape(post["date"]) + reading_meta(post),
        abstract=abstract,
        content=indent_block(post["content"], "        "),
    )


def render_index_rows(posts: list[dict], indent: str) -> str:
    if not posts:
        return f"{indent}<tr><td style=\"padding:16px\"><p>Nothing published yet.</p></td></tr>"

    rows = []
    for post in posts:
        rows.append(
            f'{indent}<tr>\n'
            f'{indent}  <td style="padding:15px 16px;width:100%;vertical-align:top">\n'
            f'{indent}    <a href="blogs/{post["slug"]}.html">'
            f'<span class="papertitle">{html.escape(post["title"])}</span></a>\n'
            f'{indent}    <br>\n'
            f'{indent}    <span class="blog-date">{html.escape(post["date"])}{reading_meta(post)}</span>\n'
            f'{indent}    <p></p>\n'
            f'{indent}    <div class="blog-abstract">\n'
            f'{indent_block(post["abstract"], indent + "      ")}\n'
            f'{indent}    </div>\n'
            f'{indent}  </td>\n'
            f'{indent}</tr>'
        )
    return "\n".join(rows)


def render_index(posts: list[dict]) -> str:
    source = INDEX_HTML.read_text(encoding="utf-8")
    region = REGION_RE.search(source)
    if not region:
        sys.exit(
            "error: could not find the '<!-- BLOGS:BEGIN ... -->' and "
            "'<!-- BLOGS:END -->' markers in index.html"
        )
    indent = region.group("indent")
    rows = render_index_rows(posts, indent)
    replacement = (
        f'{indent}{region.group("begin")}\n{rows}\n{indent}{region.group("end")}'
    )
    return source[: region.start()] + replacement + source[region.end():]


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
        help="exit 1 if any generated file is out of date instead of writing",
    )
    args = parser.parse_args()

    posts = load_posts()
    published = [post for post in posts if not post["draft"]]
    drafts = [post for post in posts if post["draft"]]

    stale: list[str] = []
    for post in published:
        target = BLOGS_DIR / f"{post['slug']}.html"
        rendered = render_page(post)
        if not target.exists() or target.read_text(encoding="utf-8") != rendered:
            if args.check:
                stale.append(target.name)
            else:
                write_atomically(target, rendered)
                print(f"  wrote blogs/{target.name}")

    # A post that became a draft should not leave its page behind.
    for post in drafts:
        target = BLOGS_DIR / f"{post['slug']}.html"
        if target.exists():
            if args.check:
                stale.append(f"{target.name} (draft, should be removed)")
            else:
                target.unlink()
                print(f"  removed blogs/{target.name} (now a draft)")

    rendered_index = render_index(published)
    if rendered_index != INDEX_HTML.read_text(encoding="utf-8"):
        if args.check:
            stale.append("index.html blog list")
        else:
            write_atomically(INDEX_HTML, rendered_index)
            print("  updated the blog list in index.html")

    summary = f"{len(published)} published, {len(drafts)} draft"
    if args.check:
        if stale:
            print(f"blogs: out of date ({', '.join(stale)}); run: python3 build.py", file=sys.stderr)
            return 1
        print(f"blogs: up to date ({summary})")
        return 0

    print(f"blogs: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
