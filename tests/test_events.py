"""What Nature and the other study events do (events.py), and the milestone animals
and forest rebuilds they lean on."""

from __future__ import annotations

import random
import unittest

import helpers  # noqa: F401  (puts the add-on on the path)

import events
import fake_forest
import forest_data as fd


class EventTests(unittest.TestCase):
    """What Nature and the other study events do (events.py)."""

    @staticmethod
    def trees(agos, n=10):
        return [{"ago": a, "n": n} for a in sorted(agos, reverse=True)]

    def test_merciless_one_missed_day_wipes_the_forest(self):
        days = set(range(0, 40)) - {10}  # one day off, ten days ago (so no tree that day either)
        out = events.merciless(self.trees(days), days)
        self.assertEqual([t["ago"] for t in out["trees"]], list(range(9, -1, -1)))  # only what came after
        latest = out["latest"]
        self.assertEqual((latest["ago"], latest["lost"], latest["streak"], len(latest["before"])), (10, 29, 29, 29))

    def test_a_break_that_struck_leaves_a_crater_not_a_pond(self):
        days = set(range(0, 40)) - set(range(10, 20))  # ten days off
        trees = self.trees(days)
        trees[-10]["gap"] = 10  # the first tree after the break, as build_forest marks it
        out = events.merciless(trees, days)
        self.assertTrue(out["latest"])
        self.assertFalse(any(t.get("gap") for t in out["trees"]))
        self.assertEqual(trees[-10]["gap"], 10)  # the forest it was given is left as it was

    def test_one_strike_per_break_however_long_on_its_first_day(self):
        days = set(range(0, 60)) - set(range(10, 30))  # twenty days off
        self.assertEqual(events.strikes(days), [29])

    def test_every_crater_shows_and_the_latest_with_what_it_took(self):
        days = set(range(0, 70)) - {31, 62}  # a month, a day off, a month, a day off
        out = events.merciless(self.trees(days), days)
        self.assertEqual(out["hits"], [62, 31])
        self.assertEqual([(c["ago"], c["lost"]) for c in out["craters"]], [(62, 7), (31, 30)])  # oldest first
        self.assertEqual((out["latest"]["ago"], out["latest"]["lost"]), (31, 30))  # only what grew since the one before
        self.assertNotIn("before", out["craters"][-1])  # what it took goes only with the latest

    def test_a_healed_crater_is_gone(self):
        old = events.CRATER_GONE_DAYS + 10
        days = set(range(0, old + 20)) - {old, 5}
        out = events.merciless(self.trees(days), days)
        self.assertEqual([c["ago"] for c in out["craters"]], [5])

    def test_nothing_is_remembered_the_strikes_come_from_the_days_studied(self):
        days = set(range(0, 40)) - {10}
        trees = self.trees(days)
        self.assertEqual(events.merciless(trees, days), events.merciless(trees, days))
        self.assertEqual(len(trees), 39)  # and the forest itself is untouched, for Peaceful to show

    def test_a_held_strike_does_not_come_yet(self):
        days = set(range(0, 40)) - {10, 20}
        out = events.merciless(self.trees(days), days, hold=frozenset({10}))
        self.assertEqual((out["hits"], out["latest"]["ago"], len(out["trees"])), ([20], 20, 19))

    def test_the_warning_is_today_itself(self):
        # studied yesterday, nothing yet today: the asteroid strikes when the day ends
        doom = events.merciless(self.trees(range(1, 40)), set(range(1, 40)))["doom"]
        self.assertEqual((doom["missed"], doom["left"]), (1, 0))
        self.assertIsNone(events.merciless(self.trees(range(0, 40)), set(range(0, 40)))["doom"])
        # nothing yesterday either: it has struck already
        self.assertIsNone(events.merciless(self.trees(range(2, 40)), set(range(2, 40)))["doom"])

    def test_no_strikes_without_reviews(self):
        self.assertEqual(events.strikes(set()), [])  # never studied: no break
        out = events.merciless([], set())
        self.assertEqual((out["trees"], out["latest"], out["doom"]), ([], None, None))  # and no endless warning
        self.assertEqual(events.strikes(set(range(5, 9))), [4])  # nor before the first day you studied

    def test_a_strike_with_nothing_grown_since_leaves_no_crater(self):
        days = set(range(0, 40)) - {10, 20}
        trees = self.trees(set(range(21, 40)))  # nothing planted between the two strikes
        out = events.merciless(trees, days)
        self.assertEqual(out["hits"], [20, 10])
        self.assertEqual(out["latest"]["ago"], 20)
        self.assertEqual(out["trees"], [])

    def test_the_level_is_one_of_three(self):
        self.assertEqual([events.nature_level(v) for v in ("wild", "stormy", None, 3)], ["wild", "peaceful", "peaceful", "peaceful"])
        self.assertTrue(events.calm("peaceful") and not events.calm("wild"))


    def test_big_learning_days_found_fast_are_the_same(self):
        def slow(trees):  # every older tree scanned for each one, as it was
            out = []
            for i, t in enumerate(trees):
                window = [u["n"] for u in trees[:i] if t["ago"] < u["ago"] <= t["ago"] + events.BIG_DAY_WINDOW]
                best = max(window, default=0)
                hit = i >= events.BIG_DAY_HISTORY and best and t["n"] >= best * events.BIG_DAY_JUMP and t["n"] >= best + events.BIG_DAY_MORE
                out.append(best if hit else None)
            return out
        rnd = random.Random(3)
        for _ in range(50):
            agos = sorted(rnd.sample(range(400), rnd.randint(0, 120)), reverse=True)  # days with gaps between
            trees = [{"ago": a, "n": rnd.choice([1, 2, 3, 5, 8, 20, 40])} for a in agos]
            self.assertEqual([t.get("big") for t in events.mark_big_days(trees)], slow(trees))
            shuffled = rnd.sample(trees, len(trees))  # not oldest first: still the same answer
            self.assertEqual([t.get("big") for t in events.mark_big_days(shuffled)], slow(shuffled))

    def test_big_learning_days(self):
        def big(counts):
            trees = [{"ago": len(counts) - i, "n": n} for i, n in enumerate(counts)]
            marked = events.mark_big_days(trees)
            self.assertFalse(any("big" in t for t in trees))  # the trees given (maybe cached) are left alone
            return [t["n"] for t in marked if t.get("big")]
        week = [1] * 7
        self.assertEqual(big(week + [3, 3, 3]), [3])  # the first 3 only: after it, 3 is no jump
        self.assertEqual(big(week + [3, 6]), [3, 6])  # 6 doubles the new best, the very next day
        self.assertEqual(big(week + [2]), [])  # not two cards more
        self.assertEqual(big([18] * 7 + [25]), [25])  # a 15-20 a day pace: 25 counts
        self.assertEqual(big([1, 1, 5]), [])  # too little history to judge yet
        # only the last BIG_DAY_WINDOW days count: a big day long ago sets no bar
        window = events.BIG_DAY_WINDOW
        self.assertEqual(big([1] * 7 + [50] + [1] * (window - 1) + [5]), [50])  # still in the window
        self.assertEqual(big([1] * 7 + [50] + [1] * window + [5]), [50, 5])

    def test_missed_now_counts_today_while_it_has_no_reviews(self):
        self.assertEqual(events.missed_now({0, 1}), 0)
        self.assertEqual(events.missed_now({2, 3}), 2)  # yesterday and today so far
        self.assertEqual(events.missed_now(set()), events.LOOKBACK_DAYS)

    def test_a_crater_remembers_the_streak_it_ended(self):
        days = set(range(3, 10)) | set(range(12, 40))  # 28 days, a break at 10-11, then 7 more
        self.assertEqual(events._streak_before(days, 11), 28)
        self.assertEqual(events._streak_before(days, 2), 7)  # a break starting yesterday

    def test_the_timeline_passes_whole_days_and_today_goes_on_as_the_last(self):
        # two days studying, one reviewing only, one away: today (0) is a day away too
        self.assertEqual(events.timeline_days([["study", 2], ["review", 1], ["away", 1]]), (4, [4, 3], {4, 3, 2}, []))
        self.assertEqual(events.timeline_days([["away", 1], ["study", 1]]), (2, [1], {1, 0}, []))
        self.assertEqual(events.timeline_days([]), (0, [], set(), []))

    def test_what_happens_on_the_timeline_happens_on_the_next_day_to_come(self):
        steps = [["leech", 2], ["study", 3], ["cure", 1], ["away", 1], ["leech", 1]]
        self.assertEqual(events.timeline_days(steps), (4, [4, 3, 2], {4, 3, 2}, [("leech", 4, 2), ("cure", 1, 1), ("leech", 0, 1)]))
        self.assertEqual(events.timeline_steps([["leech", 99], ["cure", "x"]]), [["leech", events.TIMELINE_MAX_HAPPENINGS]])

    def test_timeline_steps_keep_what_makes_sense(self):
        raw = ["strike", 7, ["away", 3], ["nap", 2], ["study", 0], ["study", events.TIMELINE_MAX_DAYS]]
        self.assertEqual(events.timeline_steps(raw), [["away", 3], ["study", events.TIMELINE_MAX_DAYS - 3]])
        self.assertEqual(events.timeline_steps(None), [])

    def test_rebuild_counts_again_from_the_trees_left(self):
        forest = dict(fake_forest.make(40), lit_count=40, review_days={1, 2})
        for t in forest["trees"]:
            t["dim"] = t["ago"] % 2 == 0
        kept = forest["trees"][-10:]
        out = fd.rebuild(forest, kept, set(range(0, 10)))
        self.assertEqual((out["stats"]["trees"], out["stats"]["streak"]), (10, 10))
        self.assertEqual(out["lit_count"], sum(1 for t in kept if not t["dim"]))
        self.assertEqual(out["review_days"], {1, 2})  # kept for Nature

    def test_stagnation_is_reviewing_without_planting(self):
        trees = self.trees([30, 20])  # the newest tree is twenty days old
        self.assertGreater(events.stagnation(trees, {0, 1, 5}), 0)
        self.assertEqual(events.stagnation(trees, {20}), 0)  # not reviewing: a break, not coasting
        self.assertEqual(events.stagnation(self.trees([30, 5]), {0}), 0)  # planted five days ago
        at = events.STAGNANT_AFTER
        self.assertGreater(events.stagnation(self.trees([40, at]), {0}), 0)  # starts on the day
        self.assertEqual(events.stagnation(self.trees([40, at - 1]), {0}), 0)
        self.assertEqual(events.stagnation(self.trees([99, events.STAGNANT_FULL]), {0}), 1.0)


class BacklogRuleTests(unittest.TestCase):
    """Review hell and the backlog cleared, and Peaceful's calm."""

    def test_the_usual_day_is_the_median_of_the_days_studied(self):
        self.assertEqual((events.usual_reviews([10, 0, 30, 20]), events.usual_reviews([10, 20]), events.usual_reviews([])), (20, 15, 0))

    def test_hell_is_twice_a_usual_day_and_never_a_small_pile(self):
        self.assertEqual(events.review_hell(30, 0), 0)      # at the minimum
        self.assertEqual(events.review_hell(80, 40), 0)     # twice a usual day of 40
        self.assertEqual(events.review_hell(120, 40), 0.5)  # halfway to the most
        self.assertEqual(events.review_hell(500, 40), 1)

    def test_cleared_once_nothing_is_left_after_hell(self):
        self.assertTrue(events.backlog_cleared(0, 100, 99, None))
        self.assertFalse(events.backlog_cleared(3, 100, 99, None))     # not quite
        self.assertFalse(events.backlog_cleared(0, 100, None, None))   # there was no hell
        self.assertFalse(events.backlog_cleared(0, 100, 90, None))     # too long ago to be news
        self.assertFalse(events.backlog_cleared(0, 100, 99, 99))       # cleared already, and no hell since
        self.assertTrue(events.backlog_cleared(0, 100, 99, 100))       # all day long

    def test_peaceful_trees_lose_their_crows_and_the_given_ones_keep_them(self):
        trees = [{"ago": 1, "leeches": 2}, {"ago": 0}]
        self.assertEqual(events.calm_trees(trees), [{"ago": 1}, {"ago": 0}])
        self.assertEqual(trees[0]["leeches"], 2)
        self.assertTrue(events.calm("peaceful") and not events.calm("wild"))


class FireTests(unittest.TestCase):
    """Wild's fire (events.fire_state, events.set_fire)."""

    @staticmethod
    def trees(agos):
        return [{"ago": a, "n": 10, "seed": a * 7919} for a in sorted(agos, reverse=True)]

    def test_two_days_away_is_no_fire_three_are(self):
        self.assertIsNone(events.fire_state(set(range(0, 40)) - {5}))
        self.assertIsNone(events.fire_state(set(range(0, 40)) - {5, 6}))
        st = events.fire_state(set(range(0, 40)) - {5, 6, 7})
        self.assertEqual((st["share"], st["missed"], st["began"], st["healed"]), (events.FIRE_PER_DAY, 3, 7, 5))

    def test_a_weekend_away_is_no_fire_nor_stops_it_healing(self):
        # Saturday and Sunday off, studied the rest of the week, for months: whichever day
        # today is (studied by now), nothing burns
        for today in range(7):
            days = {d for d in range(120) if (d + today) % 7 not in (5, 6)} | {0}
            self.assertIsNone(events.fire_state(days))
            trees = self.trees(days)
            self.assertEqual(events.set_fire(trees, days), (trees, None))
        # a fire four days away lit is out on the seventh day studied, a weekend off between:
        # back Monday to Friday, Saturday and Sunday off, then Monday and today, Tuesday
        days = set(range(40)) - {2, 3} - {9, 10, 11, 12}
        st = events.fire_state(days)
        self.assertEqual((st["share"], st["out"]), (0.0, True))
        st = events.fire_state({d - 1 for d in days if d})  # yesterday: the sixth day studied
        self.assertEqual((round(st["share"], 2), st["healed"]), (0.1, 6))

    def test_today_is_no_day_missed_yet(self):
        self.assertIsNone(events.fire_state(set(range(3, 40))))  # two days and today so far: two days
        st = events.fire_state(set(range(4, 40)))
        self.assertEqual((st["share"], st["healed"], st["news"]), (events.FIRE_PER_DAY, 0, True))

    def test_it_spreads_each_day_up_to_half(self):
        share = lambda away: events.fire_state(set(range(away + 1, 99)))["share"]  # noqa: E731
        self.assertEqual([round(share(d), 2) for d in (3, 4, 6)], [0.05, 0.1, 0.2])
        self.assertEqual(share(12), events.FIRE_MAX)
        self.assertEqual(share(60), events.FIRE_MAX)

    def test_a_week_of_study_puts_it_out_and_that_day_is_news(self):
        away = set(range(10, 40))  # nine days away, then back
        for k in range(1, events.FIRE_HEAL_DAYS):
            st = events.fire_state(away | set(range(k)) | {0})
            self.assertEqual(st["healed"], k)
        st = events.fire_state(away | set(range(events.FIRE_HEAL_DAYS)))
        self.assertEqual((st["share"], st["out"]), (0.0, True))
        self.assertIsNone(events.fire_state(away | set(range(1, events.FIRE_HEAL_DAYS + 1))))  # out yesterday: no news today

    def test_the_study_days_count_not_the_calendar(self):
        days = set(range(0, 40)) - {10, 9, 8, 7, 6} - {4, 3}  # five days away, then back with two days off
        st = events.fire_state(days)
        self.assertEqual((st["healed"], round(st["share"], 2)), (4, 0.15))  # two days off only pause it

    def test_staying_away_again_fans_it_up_anew(self):
        days = set(range(20, 60)) | {15, 14, 13} | set(range(0, 6))  # away 16-19, back 3 days, away 6-12, back 6
        st = events.fire_state(days)
        self.assertEqual((st["began"], round(st["share"], 2), st["healed"], st["missed"]), (19, 0.25, 6, 7))

    def test_burning_trees_come_by_lot_the_same_every_day(self):
        days = set(range(13, 400))  # twelve days away: half the forest
        trees = self.trees(range(13, 400))
        out, info = events.set_fire(trees, days)
        burning = [t["ago"] for t in out if t.get("burn")]
        self.assertEqual((info["trees"], len(burning), info["left"], info["news"]), (194, 194, events.FIRE_HEAL_DAYS, True))
        self.assertFalse(any("burn" in t for t in trees))  # the trees given are left alone
        # a day later, with that day studied: the same trees, a seventh less aflame
        later = [dict(t, ago=t["ago"] + 1) for t in trees]
        out, info = events.set_fire(later, {d + 1 for d in days} | {0})
        self.assertEqual([t["ago"] - 1 for t in out if t.get("burn")], burning)
        self.assertEqual({t["burn"] for t in out if t.get("burn")}, {round(1 - 1 / events.FIRE_HEAL_DAYS, 3)})
        self.assertEqual(info["left"], events.FIRE_HEAL_DAYS - 1)
    def test_two_days_missed_smoke_until_today_is_studied(self):
        self.assertEqual(events.smoke_state(set(range(3, 40))), {"began": 2, "epoch": 37})
        self.assertIsNone(events.smoke_state(set(range(3, 40)) | {0}))  # studied today: no fire coming
        self.assertIsNone(events.smoke_state(set(range(2, 40))))  # one day and today so far
        self.assertIsNone(events.smoke_state(set(range(1, 40))))  # only today so far
        self.assertIsNone(events.smoke_state(set(range(4, 40))))  # already burning
        self.assertIsNone(events.smoke_state(set()))

    def test_the_smoking_trees_are_the_ones_that_catch_fire(self):
        days, trees = set(range(3, 400)), self.trees(range(3, 400))
        out, info = events.set_fire(trees, days)
        smoking = [t["ago"] for t in out if t.get("smoke")]
        self.assertEqual((info["smoke"], info["trees"], len(smoking)), (20, 0, 20))
        self.assertFalse(any(t.get("burn") for t in out))
        later = [dict(t, ago=t["ago"] + 1) for t in trees]  # the day went by without reviews
        out, info = events.set_fire(later, {d + 1 for d in days})
        self.assertEqual([t["ago"] - 1 for t in out if t.get("burn")], smoking)
        self.assertEqual(info["smoke"], 0)

    def test_only_trees_standing_when_it_broke_out_and_drawn_one_by_one(self):
        days = set(range(0, 5)) | set(range(8, 300))  # away 5-7, back
        out, info = events.set_fire(self.trees(days), days, limit=100)
        burning = [t["ago"] for t in out if t.get("burn")]
        self.assertEqual(len(burning), info["trees"])
        self.assertTrue(burning and all(8 <= a <= 102 for a in burning))  # the newest 100, less those planted since


class CustomizeTests(unittest.TestCase):
    """Nature's Customize (events.rules): the numbers behind the asteroid, the fire and the grass,
    read against the days studied as the levels' own are - so a change goes back in time too."""

    trees = staticmethod(EventTests.trees)

    def test_the_asteroid_strikes_on_the_day_customize_says_and_not_before(self):
        days = set(range(0, 60)) - {10, 11}  # two days off, 11 and 10 days ago
        self.assertEqual(events.strikes(days), [11])  # its own: the first day
        self.assertEqual(events.strikes(days, after=2), [10])  # the second day of the two
        self.assertEqual(events.strikes(days, after=3), [])  # two days are no strike
        out = events.merciless(self.trees(days), days, after=3)
        self.assertEqual((out["hits"], out["craters"], out["latest"], len(out["trees"])), ([], [], None, 58))
        longer = set(range(0, 60)) - set(range(10, 15))  # five days off: the third of them strikes
        out = events.merciless(self.trees(longer), longer, after=3)
        self.assertEqual(out["hits"], [12])
        self.assertEqual([t["ago"] for t in out["trees"]], list(range(9, -1, -1)))

    def test_the_asteroid_comes_closer_on_each_day_of_the_run(self):
        # studied up to 8 days ago; then day by day, today counted while it has no reviews yet
        for missed in range(1, 8):
            days = set(range(missed, 60))
            out = events.merciless(self.trees(days), days, after=7)
            self.assertEqual(out["doom"], {"missed": missed, "grace": 7, "left": 7 - missed}, missed)
            self.assertEqual(out["hits"], [])  # (it strikes only as the seventh day ends)
        days = set(range(8, 60))  # the seventh day (yesterday) ended: it struck, and no warning is left
        out = events.merciless(self.trees(days), days, after=7)
        self.assertEqual((out["hits"], out["doom"]), ([1], None))

    def test_a_review_today_turns_it_back(self):
        days = set(range(3, 60)) | {0}  # two days missed, then a review today
        self.assertIsNone(events.merciless(self.trees(days), days, after=7)["doom"])
        self.assertIsNone(events.merciless(self.trees(set(range(0, 60))), set(range(0, 60)), after=7)["doom"])
        self.assertIsNone(events.merciless([], set(), after=7)["doom"])  # never studied: nothing on its way

    def test_strikes_after_one_is_as_it_was(self):
        days = set(range(2, 40))  # yesterday missed, nothing yet today: it struck yesterday
        out = events.merciless(self.trees(days), days)
        self.assertEqual((out["hits"], out["doom"]), ([1], None))
        today_only = set(range(1, 40))
        self.assertEqual(events.merciless(self.trees(today_only), today_only)["doom"], {"missed": 1, "grace": 1, "left": 0})
        self.assertEqual(events.merciless(self.trees(today_only), today_only, after=2)["doom"], {"missed": 1, "grace": 2, "left": 1})

    def test_the_fire_breaks_out_on_the_day_customize_says(self):
        away4 = set(range(5, 200))  # four days missed, nothing yet today
        self.assertEqual(events.fire_state(away4)["share"], 0.1)  # its own: from the third, 5% a day
        self.assertIsNone(events.fire_state(away4, fire_from=5))
        self.assertEqual(events.smoke_state(away4, fire_from=5)["began"], 4)  # the day before: smoke
        self.assertIsNone(events.smoke_state(away4))
        _trees, info = events.set_fire(self.trees(away4), away4, fire_from=5)
        self.assertEqual((info["smoke"] > 0, info["trees"], info["from"]), (True, 0, 5))
        away5 = set(range(6, 200))
        self.assertEqual(events.fire_state(away5, fire_from=5)["share"], 0.05)

    def test_it_goes_out_after_the_days_of_study_customize_says(self):
        days = set(range(0, 4)) | set(range(10, 200))  # away 4-9, studying the four days since
        self.assertEqual(events.fire_state(days)["healed"], 4)  # its own seven: still burning
        _trees, info = events.set_fire(self.trees(days), days)
        self.assertEqual((info["left"], info["heal"]), (3, 7))
        self.assertIsNone(events.fire_state(days, heal=3))  # out the day before yesterday
        self.assertTrue(events.fire_state(set(range(0, 3)) | set(range(10, 200)), heal=3)["out"])  # the day it went out
        burning, info = events.set_fire(self.trees(days), days, heal=10)
        self.assertEqual(info["left"], 6)
        self.assertEqual({t["burn"] for t in burning if t.get("burn")}, {0.6})

    def test_the_grass_grows_after_the_days_customize_says(self):
        trees = self.trees([40, 10])  # nothing new for ten days, reviewing today
        self.assertGreater(events.stagnation(trees, {0}), 0)
        self.assertEqual(events.stagnation(trees, {0}, after=14), 0)
        self.assertGreater(events.stagnation(self.trees([40, 14]), {0}, after=14), 0)
        # as tall after the same days past its start as its own is
        self.assertEqual(events.stagnation(self.trees([99, 20]), {0}, after=14), events.stagnation(self.trees([99, 13]), {0}))

    def test_only_a_real_change_to_the_level_is_kept(self):
        raw = {"tumbleweeds": False, "crows": True, "strike_after": 3, "fire_from": 5, "grass_after": 7,
               "fire_heal": 99, "made_up": 1, "grass": "no"}
        # crows on is Merciless's own, Wild's fire is no part of it, 7 is the grass's own, 99 out of range
        self.assertEqual(events.custom_values("merciless", raw), {"tumbleweeds": False, "strike_after": 3})
        self.assertEqual(events.custom_values("wild", raw), {"tumbleweeds": False, "fire_from": 5})
        self.assertEqual(events.custom_values("peaceful", raw), {"crows": True})
        self.assertEqual(events.custom_values("merciless", [1]), {})
        self.assertEqual(events.custom_values("merciless", {"strike_after": True}), {})  # (a bool is no number)
        r = events.rules("merciless", raw)
        self.assertEqual((r["tumbleweeds"], r["crows"], r["grass"], r["strike_after"], r["fire_from"]), (False, True, True, 3, 3))
        self.assertEqual(events.rules("peaceful"), dict(events.own_rules("peaceful"), crows=False, grass=False, tumbleweeds=False))

    def test_a_change_goes_back_in_time_and_back_again(self):
        days = set(range(0, 80)) - {50, 51}  # an old two-day break
        trees = self.trees(days)
        struck = events.merciless(trees, days)
        self.assertEqual(len(struck["trees"]), 50)
        spared = events.merciless(trees, days, after=3)
        self.assertEqual(len(spared["trees"]), 78)  # every tree, the old ones too
        self.assertEqual(events.merciless(trees, days), struck)  # and back: as it was
