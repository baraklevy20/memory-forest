"""Picking the goats (Patreon sponsors) to thank out of Patreon's member list (dev/goats.py)."""

from __future__ import annotations

import os
import sys
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev"))

import goats

GOAT, EARLY = "t1", "t2"


def member(uid, name, tiers, status="active_patron", since="2026-10-05T10:00:00.000+00:00"):
    return {"attributes": {"full_name": name, "patron_status": status, "pledge_relationship_start": since},
            "relationships": {"currently_entitled_tiers": {"data": [{"id": t, "type": "tier"} for t in tiers]},
                              "user": {"data": {"id": uid, "type": "user"}}}}


def page(*members):
    return {"data": list(members), "included": [{"id": GOAT, "type": "tier", "attributes": {"title": "Sponsor"}},
                                                {"id": EARLY, "type": "tier", "attributes": {"title": "Early Access"}},
                                                {"id": "u9", "type": "user", "attributes": {}}]}


class GoatTests(unittest.TestCase):
    def test_only_active_goats_are_thanked(self):
        pages = [page(member("u1", "Ada", [GOAT]), member("u2", "Bea", [EARLY]),
                      member("u3", "Cy", [GOAT], status="former_patron"), member("u4", "Di", [GOAT], status="declined_patron"))]
        self.assertEqual([s for _u, _r, s in goats.goats(pages, {})], ["Ada"])

    def test_a_chosen_name_replaces_the_patreon_one_and_null_hides_it(self):
        pages = [page(member("u1", "Ada Lovelace", [GOAT]), member("u2", "Bea Smith", [GOAT]))]
        found = goats.goats(pages, {"u1": "Ada", "u2": None})
        self.assertEqual(found, [("u1", "Ada Lovelace", "Ada"), ("u2", "Bea Smith", None)])

    def test_longest_standing_first_across_pages(self):
        pages = [page(member("u1", "New", [GOAT], since="2027-01-01T00:00:00.000+00:00")),
                 page(member("u2", "Old", [GOAT], since="2026-10-02T00:00:00.000+00:00"))]
        self.assertEqual([s for _u, _r, s in goats.goats(pages, {})], ["Old", "New"])

    def test_a_member_with_no_name_is_left_out(self):
        pages = [page(member("u1", "  ", [GOAT]))]
        self.assertEqual(goats.goats(pages, {}), [("u1", "", None)])


if __name__ == "__main__":
    unittest.main()
