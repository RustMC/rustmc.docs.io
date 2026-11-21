"""Refresh data/sponsors.json from the GitHub Sponsors listing of neonjava.

Why: the Sponsor page must show the real tiers and sponsors, never typed-in
ones. Uses the GitHub CLI's GraphQL access (GH_TOKEN in CI).
Done: tiers (name, monthly price, one-time flag, description) and public
sponsors. Not done: private sponsors, which GitHub does not expose.

    python3 scripts/fetch_sponsors.py
"""

import json
import subprocess
import sys
from pathlib import Path

ACCOUNT = "neonjava"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "sponsors.json"
# GitHub's GraphQL connections return at most 100 nodes per page.
PAGE = 100
QUERY = """
query($login: String!, $first: Int!) {
  user(login: $login) {
    hasSponsorsListing
    sponsorsListing {
      url
      tiers(first: $first) {
        nodes { name monthlyPriceInDollars isOneTime description }
      }
    }
    sponsors(first: $first) {
      nodes {
        ... on User { login url }
        ... on Organization { login url }
      }
    }
  }
}
"""


def main():
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={ACCOUNT}",
         "-F", f"first={PAGE}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"fetch_sponsors: GitHub API request failed: {result.stderr.strip()}")
    user = json.loads(result.stdout)["data"]["user"]
    listing = user["sponsorsListing"] or {}
    data = {
        "account": ACCOUNT,
        "enabled": user["hasSponsorsListing"],
        "url": listing.get("url", ""),
        "tiers": sorted(
            (listing.get("tiers") or {}).get("nodes", []),
            key=lambda tier: (tier["isOneTime"], tier["monthlyPriceInDollars"]),
        ),
        "sponsors": user["sponsors"]["nodes"],
    }
    OUTPUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"fetch_sponsors: {len(data['tiers'])} tiers, {len(data['sponsors'])} sponsors")


if __name__ == "__main__":
    main()
