import unittest
from datetime import date, timedelta

from compass_app.engine import Buddy, Joiner, MatchSettings, run_match

TODAY = date(2026, 11, 2)


def joiner(answers, **kw):
    return Joiner(id="J1", department="Sales", location="Mumbai", answers=answers, **kw)


def buddy(id, answers, dept="Sales", loc="Mumbai", **kw):
    return Buddy(id=id, name=f"Buddy {id}", department=dept, location=loc, answers=answers, **kw)


def ids(candidates):
    return [c.buddy_id for c in candidates]


def codes(candidate):
    return [f.code for f in candidate.flags]


def find(result, buddy_id):
    return next(c for c in result.scored if c.buddy_id == buddy_id)


J = [5, 4, 5, 4, 5]
POOL = [
    buddy("A", [3, 2, 4, 1, 3]),
    buddy("B", [4, 5, 4, 5, 4]),
    buddy("C", [5, 4, 5, 2, 5]),
    buddy("D", [5, 5, 4, 1, 5]),
    buddy("E", [4, 3, 3, 4, 4]),
    buddy("F", [3, 3, 5, 4, 3]),
]


class WorkedExample(unittest.TestCase):
    def test_ranking_and_bands(self):
        r = run_match(joiner(J), POOL, today=TODAY)
        self.assertEqual(r.tier_reached, "1")
        self.assertEqual(ids(r.shown), ["B", "C", "E"])
        self.assertEqual(ids(r.more), ["D"])
        self.assertEqual(find(r, "B").band, "Strong")
        self.assertEqual(find(r, "C").band, "Good")
        self.assertEqual(find(r, "A").band, "Not suggested")
        self.assertNotIn("A", ids(r.shown) + ids(r.more))
        self.assertNotIn("F", ids(r.shown) + ids(r.more))

    def test_flags(self):
        r = run_match(joiner(J), POOL, today=TODAY)
        self.assertEqual(codes(find(r, "B")), [])
        self.assertEqual(codes(find(r, "C")), ["STYLE_GAP"])
        self.assertEqual(find(r, "C").flags[0].question, 4)
        self.assertEqual(codes(find(r, "E")), ["STYLE_GAP"])
        self.assertEqual(codes(find(r, "D")), ["OPPOSITE"])
        self.assertEqual(find(r, "D").flags[0].level, "Red")

    def test_weaker_only_when_nothing_better(self):
        r = run_match(joiner(J), [buddy("F", [3, 3, 5, 4, 3])], today=TODAY)
        self.assertEqual(r.tier_reached, "FALLBACK")
        self.assertEqual(ids(r.shown), ["F"])
        self.assertEqual(r.shown[0].band, "Weaker")
        self.assertIn("WEAKER", codes(r.shown[0]))

    def test_nothing_suitable_goes_manual(self):
        r = run_match(joiner(J), [buddy("A", [3, 2, 4, 1, 3])], today=TODAY)
        self.assertEqual(r.tier_reached, "MANUAL")
        self.assertEqual(r.shown, [])


class ExtraCases(unittest.TestCase):
    def test_identical_answers_are_strong_with_no_flags(self):
        j = [2, 4, 1, 5, 2]
        r = run_match(joiner(j), [buddy("X", j, completed_at=TODAY)], today=TODAY)
        c = r.shown[0]
        self.assertEqual((c.band, c.total_gap, c.flags), ("Strong", 0, []))

    def test_good_match_can_hide_a_red_flag(self):
        r = run_match(joiner([1, 1, 1, 1, 1]), [buddy("X", [2, 2, 2, 2, 5])], today=TODAY)
        c = r.shown[0]
        self.assertEqual(c.band, "Good")
        self.assertEqual(codes(c), ["OPPOSITE"])
        self.assertEqual(c.flags[0].question, 5)

    def test_no_same_department_goes_to_tier_3_incl_own_location(self):
        r = run_match(joiner(J), [buddy("X", J, dept="Finance", loc="Mumbai")], today=TODAY)
        self.assertEqual(r.tier_reached, "3")
        self.assertIn("OTHER_DEPARTMENT", codes(r.shown[0]))
        self.assertNotIn("OTHER_LOCATION", codes(r.shown[0]))

    def test_same_department_other_location_is_tier_2(self):
        r = run_match(joiner(J), [buddy("X", J, loc="Pune")], today=TODAY)
        self.assertEqual(r.tier_reached, "2")
        self.assertIn("OTHER_LOCATION", codes(r.shown[0]))

    def test_tier3_good_beats_tier1_weaker(self):
        j = [3, 3, 3, 3, 3]
        pool = [buddy("T1", [3, 3, 3, 5, 5]),
                buddy("T3", [3, 3, 3, 3, 5], dept="Finance")]
        r = run_match(joiner(j), pool, today=TODAY)
        self.assertEqual(r.tier_reached, "3")
        self.assertEqual(ids(r.shown), ["T3"])

    def test_managers_never_appear(self):
        r = run_match(joiner(J, manager_chain=("M1",)), [buddy("M1", J)], today=TODAY)
        self.assertEqual(r.scored, [])
        self.assertEqual(r.tier_reached, "MANUAL")

    def test_inactive_and_wrong_version_excluded(self):
        pool = [buddy("P", J, pool_active=False), buddy("V", J, version=2)]
        self.assertEqual(run_match(joiner(J), pool, today=TODAY).scored, [])

    def test_settings_change_applies_to_next_run(self):
        pool = [buddy("X", [5, 4, 3, 1, 1])]  # gaps 0,0,2,3,4 -> 2 close
        self.assertEqual(find(run_match(joiner(J), pool, today=TODAY), "X").band, "Not suggested")
        loose = MatchSettings(good_threshold=2, weaker_threshold=2)
        self.assertEqual(find(run_match(joiner(J), pool, loose, TODAY), "X").band, "Good")

    def test_tie_breaks_on_earliest_completion(self):
        pool = [buddy("LATE", J, completed_at=date(2026, 6, 1)),
                buddy("EARLY", J, completed_at=date(2026, 1, 1))]
        self.assertEqual(ids(run_match(joiner(J), pool, today=TODAY).shown), ["EARLY", "LATE"])

    def test_info_flags(self):
        old = TODAY - timedelta(days=400)
        b = buddy("X", [3, 3, 3, 3, 5], completed_at=old)
        r = run_match(joiner([3, 3, 3, 3, 4]), [b], today=TODAY)
        got = codes(r.shown[0])
        for code in ("MIDDLE_ANSWERS", "OLD_ANSWERS"):
            self.assertIn(code, got)

    def test_top_three_and_show_more(self):
        pool = [buddy(str(i), J, completed_at=date(2026, 1, i + 1)) for i in range(5)]
        r = run_match(joiner(J), pool, today=TODAY)
        self.assertEqual(len(r.shown), 3)
        self.assertEqual(len(r.more), 2)


if __name__ == "__main__":
    unittest.main()