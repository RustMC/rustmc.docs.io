"""Generate the site's documentation, status and updates from a RustMC checkout.

Why: every page about RustMC must come from the RustMC repository itself, so
the site never drifts from the project. Run before `zola build`:

    python3 scripts/build_content.py <path-to-RustMC-checkout>

Done: docs pages with their internal links rewritten, the configuration page
from the example config, status from docs/STATUS.md, one update per commit
reachable from the checked-out branch, newest first. Not done: nothing known.

Writes only generated, git-ignored files: content/docs/ and data/generated/.
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
DATA_OUT = ROOT / "data" / "generated"

# (slug, title, source path in RustMC, short description); order is the menu order.
DOCS = [
    ("getting-started", "Getting started", "docs/DEVELOPMENT.md",
     "Build, test and run RustMC locally."),
    ("configuration", "Configuration", "config/rustmc.example.toml",
     "Every configuration key, from the example file."),
    ("commands", "Commands", "docs/COMMANDS.md",
     "Commands, permission levels and where they run."),
    ("architecture", "Architecture", "docs/ARCHITECTURE.md",
     "How the server is put together."),
    ("compatibility", "Compatibility", "docs/COMPATIBILITY.md",
     "Supported editions and versions, with evidence."),
    ("parity", "Vanilla parity", "docs/PARITY.md",
     "How closely each feature matches vanilla, with numbers."),
    ("roadmap", "Roadmap", "ROADMAP.md",
     "Milestones and their exit evidence."),
    ("status", "Status", "docs/STATUS.md",
     "Done, in progress, known bugs and next steps."),
    ("contributing", "Contributing", "CONTRIBUTING.md",
     "How changes are proposed and reviewed."),
    ("security", "Security", "SECURITY.md",
     "How to report vulnerabilities."),
]

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


def rewrite_links(text, source):
    """Points links at the matching site page, or at the file on GitHub."""
    pages = {path: slug for slug, _, path, _ in DOCS}
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


def front_matter(title, weight, description, source):
    return (
        "+++\n"
        f"title = {json.dumps(title)}\n"
        f"description = {json.dumps(description)}\n"
        f"weight = {weight}\n"
        "[extra]\n"
        f"source = {json.dumps(source)}\n"
        "+++\n\n"
    )


def docs_pages(checkout):
    if DOCS_OUT.exists():
        shutil.rmtree(DOCS_OUT)
    DOCS_OUT.mkdir(parents=True)
    (DOCS_OUT / "_index.md").write_text(
        '+++\ntitle = "Documentation"\nsort_by = "weight"\ntemplate = "docs.html"\n'
        'page_template = "doc.html"\n+++\n',
        encoding="utf-8",
    )
    for weight, (slug, title, source, description) in enumerate(DOCS, start=1):
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
            front_matter(title, weight, description, source) + body, encoding="utf-8"
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
    return {
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


def main():
    if len(sys.argv) != 2:
        fail("usage: build_content.py <path-to-RustMC-checkout>")
    checkout = Path(sys.argv[1]).resolve()
    docs_pages(checkout)
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    (DATA_OUT / "status.json").write_text(json.dumps(status(checkout), indent=1), encoding="utf-8")
    entries = updates(checkout)
    (DATA_OUT / "updates.json").write_text(json.dumps(entries, indent=1), encoding="utf-8")
    print(f"build_content: {len(DOCS)} docs pages, {len(entries)} updates")


if __name__ == "__main__":
    main()
