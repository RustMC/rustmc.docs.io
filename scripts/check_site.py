"""Accessibility and style checks on the built site.

Why: the site promises WCAG AA contrast, accessible structure and colours only
from the token file; this script fails the build when that slips.

    python3 scripts/check_site.py public static/css/site.css

Done: contrast of every text/background token pair the stylesheet uses for
text (4.5:1, AA normal text), colour literals outside the token block, and per
page: a language, one h1, no skipped heading levels, a main landmark, a skip
link, labelled navigation, non-empty link text and alt text on images.
Not done: anything that needs a rendering engine (focus order, zoom reflow).
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# (text token, background token) pairs the stylesheet uses for readable text.
TEXT_PAIRS = [
    ("text", "page"), ("text", "surface"), ("muted", "page"), ("muted", "surface"),
    ("accent", "page"), ("accent", "surface"), ("accent-strong", "surface"),
    ("on-accent", "accent"), ("on-accent", "accent-strong"),
]
AA_NORMAL_TEXT = 4.5
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(")


def luminance(hex_colour):
    value = hex_colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def check_css(path, problems):
    text = path.read_text(encoding="utf-8")
    root = re.search(r":root\s*\{(.*?)\}", text, re.S)
    if not root:
        problems.append(f"{path}: no :root token block")
        return
    tokens = dict(re.findall(r"--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})", root.group(1)))
    outside = COLOUR.findall(text[:root.start()] + text[root.end():])
    if outside:
        problems.append(f"{path}: colour values outside the token block: {outside}")
    for fg, bg in TEXT_PAIRS:
        if fg not in tokens or bg not in tokens:
            problems.append(f"{path}: missing token --color-{fg} or --color-{bg}")
            continue
        ratio = contrast(tokens[fg], tokens[bg])
        if ratio < AA_NORMAL_TEXT:
            problems.append(f"--color-{fg} on --color-{bg}: {ratio:.2f}:1 is below {AA_NORMAL_TEXT}:1")
        print(f"contrast --color-{fg} on --color-{bg}: {ratio:.2f}:1")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.headings = []
        self.main = False
        self.skip = False
        self.navs_unlabelled = 0
        self.images_without_alt = 0
        self.link_depth = 0
        self.link_text = ""
        self.empty_links = 0
        self.colour_attrs = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        if tag == "main":
            self.main = True
        if tag == "nav" and not attrs.get("aria-label"):
            self.navs_unlabelled += 1
        if tag == "img" and attrs.get("alt") is None:
            self.images_without_alt += 1
        if tag == "a":
            if "skip-link" in (attrs.get("class") or ""):
                self.skip = True
            self.link_depth += 1
            self.link_text = attrs.get("aria-label") or ""
        if "style" in attrs and COLOUR.search(attrs["style"] or ""):
            self.colour_attrs += 1

    def handle_endtag(self, tag):
        if tag == "a" and self.link_depth:
            self.link_depth -= 1
            if not self.link_text.strip():
                self.empty_links += 1

    def handle_data(self, data):
        if self.link_depth:
            self.link_text += data


def check_page(path, problems):
    page = Page()
    page.feed(path.read_text(encoding="utf-8"))
    name = path.as_posix()
    if page.lang != "en":
        problems.append(f"{name}: missing lang")
    if page.headings.count(1) != 1:
        problems.append(f"{name}: {page.headings.count(1)} h1 elements")
    for before, after in zip(page.headings, page.headings[1:]):
        if after > before + 1:
            problems.append(f"{name}: heading jumps from h{before} to h{after}")
    for ok, what in [(page.main, "main landmark"), (page.skip, "skip link")]:
        if not ok:
            problems.append(f"{name}: no {what}")
    for count, what in [(page.navs_unlabelled, "unlabelled nav"),
                        (page.images_without_alt, "image without alt"),
                        (page.empty_links, "link without text"),
                        (page.colour_attrs, "inline colour")]:
        if count:
            problems.append(f"{name}: {count} {what}")


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: check_site.py <built-site> <stylesheet>")
    site, css = Path(sys.argv[1]), Path(sys.argv[2])
    problems = []
    check_css(css, problems)
    pages = [p for p in sorted(site.rglob("*.html")) if p.name != "404.html"]
    for page in pages:
        check_page(page, problems)
    for problem in problems:
        print(f"problem: {problem}")
    print(f"check_site: {len(pages)} pages, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
