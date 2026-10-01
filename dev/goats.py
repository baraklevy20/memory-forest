"""Write goats.json: the names the About tab thanks, from Patreon's Sponsor tier ("goats" in the code).

    python3 dev/goats.py           # fetch, and write goats.json
    python3 dev/goats.py --list    # also show each goat's Patreon ID, to rename one

Each goat appears under their Patreon name unless dev/goat_names.json says
otherwise: it maps a Patreon user ID to the name they asked for, or to null for someone
who asked not to be listed. IDs, not names, because people rename their accounts. That
file stays in the private repo; only the final names ship.

Run it before a release: the add-on reads goats.json and never calls Patreon itself.
It needs the Creator's Access Token from https://www.patreon.com/portal/registration/register-clients,
in dev/patreon_token (git-ignored) or the PATREON_TOKEN environment variable.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
TOKEN_FILE = os.path.join(HERE, "patreon_token")
NAMES_FILE = os.path.join(HERE, "goat_names.json")
OUT = os.path.join(ADDON, "goats.json")
API = "https://www.patreon.com/api/oauth2/v2"
TIER = "Sponsor"
PAGE = 500


def token() -> str:
    if os.environ.get("PATREON_TOKEN"):
        return os.environ["PATREON_TOKEN"].strip()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            return f.read().strip()
    sys.exit(f"no Patreon token: put the Creator's Access Token in {os.path.relpath(TOKEN_FILE)} or PATREON_TOKEN")


def get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "User-Agent": "memory-forest-goats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def members(tok: str) -> list:
    """Every page of the campaign's members, as Patreon returns them."""
    campaigns = get(f"{API}/campaigns", tok)["data"]
    if not campaigns:
        sys.exit("this token has no campaign")
    query = urllib.parse.urlencode({
        "include": "currently_entitled_tiers,user",
        "fields[member]": "full_name,patron_status,pledge_relationship_start",
        "fields[tier]": "title",
        "page[count]": PAGE,
    })
    url, pages = f"{API}/campaigns/{campaigns[0]['id']}/members?{query}", []
    while url:
        page = get(url, tok)
        pages.append(page)
        url = page.get("links", {}).get("next")
    return pages


def goats(pages: list, names: dict, tier: str = TIER) -> list:
    """(user ID, Patreon name, name shown or None) for each active member of `tier`,
    longest-standing first."""
    titles = {i["id"]: i["attributes"].get("title") for p in pages for i in p.get("included", []) if i["type"] == "tier"}
    found = []
    for p in pages:
        for m in p["data"]:
            a, rel = m["attributes"], m["relationships"]
            if a.get("patron_status") != "active_patron":
                continue
            if tier not in (titles.get(t["id"]) for t in rel["currently_entitled_tiers"]["data"]):
                continue
            uid = rel["user"]["data"]["id"]
            real = (a.get("full_name") or "").strip()
            shown = names.get(uid, real or None)
            found.append((a.get("pledge_relationship_start") or "", uid, real, shown))
    return [(uid, real, shown) for _start, uid, real, shown in sorted(found)]


def main() -> None:
    names = {}
    if os.path.exists(NAMES_FILE):
        with open(NAMES_FILE, encoding="utf-8") as f:
            names = json.load(f)
    found = goats(members(token()), names)
    shown = [s for _uid, _real, s in found if s]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(shown, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if "--list" in sys.argv:
        for uid, real, s in found:
            print(f"{uid:>12}  {real}" + ("" if s == real else f"  ->  {s or '(not listed)'}"))
    print(f"wrote {os.path.relpath(OUT)}: {len(shown)} of {len(found)} goats listed")


if __name__ == "__main__":
    main()
