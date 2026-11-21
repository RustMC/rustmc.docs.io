"""Generate the site's documentation, status and updates from a RustMC checkout.

Why: every page about RustMC must come from the RustMC repository itself, so
the site never drifts from the project. Run before `zola build`:

    python3 scripts/build_content.py <path-to-RustMC-checkout>

Done: docs pages with their internal links rewritten, the configuration page
from the example config, status from docs/STATUS.md, one update per commit
reachable from the checked-out branch, newest first. Not done: nothing known.

Writes only generated, git-ignored files: content/docs/, content/updates/,
data/generated/ and static/generated/.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "https://github.com/RustMC/RustMC"
DOCS_OUT = ROOT / "content" / "docs"
UPDATES_OUT = ROOT / "content" / "updates"
# The preview recording shown on the home page, copied from the RustMC repository.
VIDEO_SOURCE = "assets/demos/rustmc-java-26.3-preview-2026-09-29.mp4"
VIDEO_OUT = ROOT / "static" / "generated" / "preview.mp4"
# Served compact commit list for searching all updates in the browser.
SEARCH_OUT = ROOT / "static" / "generated" / "updates.json"
# Commits per Updates page: short enough to scan, few enough pages to page through.
UPDATES_PER_PAGE = 50
DATA_OUT = ROOT / "data" / "generated"

# Docs groups in menu order, each with the pages it lists explicitly:
# (slug, title, source path in RustMC, short description).
GROUPS = [
    ("Start", [
        ("getting-started", "Getting started", "docs/DEVELOPMENT.md",
         "Build, test and run RustMC locally."),
        ("configuration", "Configuration", "config/rustmc.example.toml",
         "Every configuration key, from the example file."),
        ("commands", "Commands", "docs/COMMANDS.md",
         "Commands, permission levels and where they run."),
    ]),
    ("Project", [
        ("status", "Status", "docs/STATUS.md",
         "Done, in progress, known bugs and next steps."),
        ("roadmap", "Roadmap", "ROADMAP.md", "Milestones and their exit evidence."),
        ("changelog", "Changelog", "CHANGELOG.md", "Notable changes by release."),
        ("parity", "Vanilla parity", "docs/PARITY.md",
         "How closely each feature matches vanilla, with numbers."),
        ("compatibility", "Compatibility", "docs/COMPATIBILITY.md",
         "Supported editions and versions, with evidence."),
        ("benchmarks", "Benchmarks", "docs/BENCHMARKS.md",
         "Measured speed and resource use, with method and hardware."),
        ("testing", "Testing", "docs/TESTING.md", "How RustMC is tested."),
    ]),
    ("Internals", [
        ("architecture", "Architecture", "docs/ARCHITECTURE.md",
         "How the server is put together."),
        ("review", "Code review", "docs/REVIEW.md",
         "Every module, whether live play reaches it, and what was removed."),
        ("provenance", "Provenance", "docs/PROVENANCE.md",
         "Where every fact and dependency comes from."),
        ("project-decisions", "Project decisions", "docs/PROJECT_DECISIONS.md",
         "Decisions about scope and process."),
    ]),
    ("Decisions", "docs/decisions"),
    ("Milestones", "docs/milestones"),
    ("Research", "docs/research"),
    ("Community", [
        ("contributing", "Contributing", "CONTRIBUTING.md",
         "How changes are proposed and reviewed."),
        ("security", "Security", "SECURITY.md", "How to report vulnerabilities."),
    ]),
]
# Longest description shown on a docs card.
DESCRIPTION_CHARS = 160


def first_paragraph(text):
    """The first prose paragraph after the title, shortened for a card."""
    for block in re.sub(r"\A# [^\n]*\n+", "", text).split("\n\n"):
        block = " ".join(block.split())
        if block and not block.startswith(("#", "|", "-", "*", "```", "<", ">")):
            plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", block).replace("`", "")
            if len(plain) > DESCRIPTION_CHARS:
                plain = plain[:DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "…"
            return plain
    return ""


def collect_docs(checkout):
    """Every docs page as (group, slug, title, source, description)."""
    docs = []
    for group, pages in GROUPS:
        if isinstance(pages, str):
            folder = checkout / pages
            if not folder.is_dir():
                fail(f"{pages} is missing from the RustMC checkout")
            for path in sorted(folder.glob("*.md")):
                text = path.read_text(encoding="utf-8")
                heading = re.match(r"# (.+)", text)
                title = heading.group(1).strip() if heading else path.stem
                source = f"{pages}/{path.name}"
                docs.append((group, path.stem.lower(), title, source, first_paragraph(text)))
        else:
            docs.extend((group, *page) for page in pages)
    slugs = [slug for _, slug, _, _, _ in docs]
    duplicates = {slug for slug in slugs if slugs.count(slug) > 1}
    if duplicates:
        fail(f"duplicate docs slugs: {sorted(duplicates)}")
    return docs


# Markdown link target: ](path#anchor) where path is relative.
LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s#]+)(#[^)\s]*)?\)")
PROGRESS = re.compile(r"^Progress: (\d+) of (\d+) plan phases complete", re.M)
SECTION = re.compile(r"^## (.+?)\n(.*?)(?=^## |\Z)", re.M | re.S)
# Paths whose first segment names the area of the project a commit touched.
AREAS = [
    ("crates/rustmc-server/", "server"),
    ("crates/rustmc-tools/", "tools"),
    ("docs/", "documentation"),
    (".github/", "continuous integration"),
    ("config/", "configuration"),
]


def fail(message):
    sys.exit(f"build_content: {message}")


def git(checkout, *args):
    result = subprocess.run(
        ["git", "-C", str(checkout), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


PAGES = {}


def rewrite_links(text, source):
    """Points links at the matching site page, or at the file on GitHub."""
    pages = PAGES
    base = Path(source).parent

    def replace(match):
        target, anchor = match.group(1), match.group(2) or ""
        resolved = (base / target).as_posix()
        parts = []
        for part in resolved.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        resolved = "/".join(parts)
        if resolved in pages:
            return f"](@/docs/{pages[resolved]}.md{anchor})"
        return f"]({REPOSITORY}/blob/main/{resolved}{anchor})"

    return LINK.sub(replace, text)


def front_matter(title, weight, description, source, group):
    return (
        "+++\n"
        f"title = {json.dumps(title)}\n"
        f"description = {json.dumps(description)}\n"
        f"weight = {weight}\n"
        "[extra]\n"
        f"source = {json.dumps(source)}\n"
        f"group = {json.dumps(group)}\n"
        "+++\n\n"
    )


def docs_pages(checkout, docs):
    if DOCS_OUT.exists():
        shutil.rmtree(DOCS_OUT)
    DOCS_OUT.mkdir(parents=True)
    (DOCS_OUT / "_index.md").write_text(
        '+++\ntitle = "Documentation"\nsort_by = "weight"\ntemplate = "docs.html"\n'
        'page_template = "doc.html"\n+++\n',
        encoding="utf-8",
    )
    for weight, (group, slug, title, source, description) in enumerate(docs, start=1):
        path = checkout / source
        if not path.is_file():
            fail(f"{source} is missing from the RustMC checkout")
        text = path.read_text(encoding="utf-8")
        if source.endswith(".toml"):
            body = (
                f"The annotated example configuration, `{source}`, as it is in the "
                "repository. Commented lines show optional keys and their defaults.\n\n"
                f"```toml\n{text.rstrip()}\n```\n"
            )
        else:
            # The page title comes from front matter; drop the file's own H1.
            body = re.sub(r"\A# [^\n]*\n+", "", text)
            body = rewrite_links(body, source)
        (DOCS_OUT / f"{slug}.md").write_text(
            front_matter(title, weight, description, source, group) + body, encoding="utf-8"
        )


def status(checkout):
    text = (checkout / "docs" / "STATUS.md").read_text(encoding="utf-8")
    match = PROGRESS.search(text)
    if not match:
        fail("docs/STATUS.md has no 'Progress: N of M plan phases complete' line")
    done, total = int(match.group(1)), int(match.group(2))
    sections = {name.strip(): body.strip() for name, body in SECTION.findall(text)}
    for required in ("Done", "In progress", "Not done", "Next"):
        if required not in sections:
            fail(f"docs/STATUS.md has no '## {required}' section")
    updated = re.search(r"^Last updated: (.+?)\.?$", text, re.M)
    cargo = (checkout / "crates" / "rustmc-server" / "Cargo.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', cargo, re.M)
    if not version:
        fail("crates/rustmc-server/Cargo.toml has no version")
    return {
        "version": version.group(1),
        "phases_complete": done,
        "phases_total": total,
        "percent": round(100 * done / total),
        "updated": updated.group(1) if updated else "",
        "done": rewrite_links(sections["Done"], "docs/STATUS.md"),
        "in_progress": rewrite_links(sections["In progress"], "docs/STATUS.md"),
        "next": rewrite_links(sections["Next"], "docs/STATUS.md"),
    }


def summarize(body, paths):
    """A plain-language line: the message body's first paragraph, then the
    areas the commit touched."""
    lines = [
        line for line in body.split("\n\n", 1)[0].splitlines()
        if not line.lower().startswith(("signed-off-by:", "co-authored-by:"))
    ]
    text = " ".join(line.strip() for line in lines).strip()
    areas = []
    for path in paths:
        area = next((name for prefix, name in AREAS if path.startswith(prefix)), "project files")
        if area not in areas:
            areas.append(area)
    touched = f"Changed {len(paths)} file{'s' if len(paths) != 1 else ''}"
    if areas:
        touched += " in " + ", ".join(areas)
    if text and not text.endswith((".", "!", "?")):
        text += "."
    return f"{text} {touched}." if text else f"{touched}."


def updates(checkout):
    record, field = "\x1e", "\x1f"
    meta = git(
        checkout, "log",
        f"--format={record}%H{field}%h{field}%as{field}%an{field}%s{field}%b",
    )
    # Changed paths per commit; for merges, against the first parent, which is
    # what the merge brought to the branch.
    changed = {}
    for chunk in git(checkout, "log", "--diff-merges=first-parent", "--name-only",
                     f"--format={record}%H").split(record)[1:]:
        lines = [line for line in chunk.splitlines() if line.strip()]
        if lines:
            changed[lines[0]] = lines[1:]
    entries = []
    for chunk in meta.split(record)[1:]:
        full, short, date, author, subject, body = chunk.split(field, 5)
        entries.append({
            "hash": short,
            "url": f"{REPOSITORY}/commit/{full}",
            "date": date,
            "author": author,
            "subject": subject,
            "summary": summarize(body.strip(), changed.get(full, [])),
        })
    if not entries:
        fail("the RustMC checkout has no commits")
    return entries


def update_pages(entries):
    """One page per commit, so the Updates section can paginate them."""
    if UPDATES_OUT.exists():
        shutil.rmtree(UPDATES_OUT)
    UPDATES_OUT.mkdir(parents=True)
    (UPDATES_OUT / "_index.md").write_text(
        "+++\n"
        'title = "Updates"\n'
        'description = "Every commit on the RustMC main branch, newest first."\n'
        'template = "updates.html"\n'
        'page_template = "update.html"\n'
        'sort_by = "weight"\n'
        f"paginate_by = {UPDATES_PER_PAGE}\n"
        "[extra]\n"
        f"total = {len(entries)}\n"
        "+++\n",
        encoding="utf-8",
    )
    for weight, entry in enumerate(entries, start=1):
        extra = {key: entry[key] for key in ("hash", "url", "date", "author", "summary")}
        (UPDATES_OUT / f"{entry['hash']}.md").write_text(
            "+++\n"
            f"title = {json.dumps(entry['subject'])}\n"
            f"weight = {weight}\n"
            "[extra]\n"
            + "".join(f"{key} = {json.dumps(value)}\n" for key, value in extra.items())
            + "+++\n",
            encoding="utf-8",
        )


def main():
    if len(sys.argv) != 2:
        fail("usage: build_content.py <path-to-RustMC-checkout>")
    checkout = Path(sys.argv[1]).resolve()
    docs = collect_docs(checkout)
    PAGES.update({source: slug for _, slug, _, source, _ in docs})
    docs_pages(checkout, docs)
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    (DATA_OUT / "status.json").write_text(json.dumps(status(checkout), indent=1), encoding="utf-8")
    entries = updates(checkout)
    update_pages(entries)
    SEARCH_OUT.parent.mkdir(parents=True, exist_ok=True)
    video = checkout / VIDEO_SOURCE
    if not video.is_file():
        fail(f"{VIDEO_SOURCE} is missing from the RustMC checkout")
    shutil.copyfile(video, VIDEO_OUT)
    SEARCH_OUT.write_text(json.dumps(
        [[e["hash"], e["date"], e["subject"], e["url"]] for e in entries]
    ), encoding="utf-8")
    print(f"build_content: {len(docs)} docs pages, {len(entries)} updates")


if __name__ == "__main__":
    main()
