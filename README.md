# rustmc.docs.io

The website of [RustMC](https://github.com/RustMC/RustMC), published at
<https://rustmc.github.io/rustmc.docs.io/>.

Every page about RustMC is generated from the RustMC repository at build
time: the documentation pages, the status on the home page (from
`docs/STATUS.md`) and the Updates page (one entry per commit on `main`). The
Sponsor page reads `data/sponsors.json`, written by `scripts/fetch_sponsors.py`
from the GitHub Sponsors listing; the build refreshes it when the repository
has a `SPONSORS_TOKEN` secret (a read-only personal token), because the
workflow's own token cannot read a user's Sponsors listing. Nothing about the project is typed into this
repository by hand.

## Why Zola

The site is built with [Zola](https://www.getzola.org/), a static site
generator distributed as one self-contained binary. It needs no language
runtime or package installation, which keeps the hourly build fast and its
supply chain small (the workflow downloads one pinned release and checks its
SHA-256); it renders Markdown, so the RustMC docs are used as written; and its
templates need no JavaScript: the pages work without it, and the small
scripts only add the theme toggle, filters, search and copy buttons. Like RustMC itself, it is
written in Rust.

## Build locally

```sh
git clone https://github.com/RustMC/RustMC.git upstream
python3 scripts/fetch_sponsors.py        # needs the GitHub CLI; optional
python3 scripts/build_content.py upstream
zola build
python3 scripts/check_site.py public static/css/site.css
```

`zola serve` previews the site at <http://127.0.0.1:1111>.

## Layout

| Path | Purpose |
| --- | --- |
| `scripts/build_content.py` | Generates the docs pages, status and updates from a RustMC checkout |
| `scripts/fetch_sponsors.py` | Refreshes `data/sponsors.json` from GitHub Sponsors |
| `scripts/check_site.py` | Contrast, colour-token and page-structure checks |
| `templates/` | Page templates |
| `static/css/site.css` | All styles; every colour is a token there (light: Overworld palette, dark: End palette) |
| `static/js/theme.js`, `static/js/site.js` | Light/dark toggle; docs filter, search over every commit, copy buttons (all optional) |
| `static/icons/` | The site's own 8x8 pixel icons |
| `.github/workflows/site.yml` | Builds and checks every change; deploys `main` on push and hourly |

The site is not affiliated with Mojang or Microsoft.
