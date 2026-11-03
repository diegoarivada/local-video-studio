import unittest

from studio import text
from studio.script import ScriptError, section_count, validate_outline


class TextTests(unittest.TestCase):
    def test_clean_for_speech(self):
        self.assertEqual(text.clean("## Heading\n- **Bold** point — next"), "Bold point, next")

    def test_sentences_and_groups(self):
        s = text.split_sentences("Short. Also short. This one is a much longer sentence that stands on its own two feet.")
        self.assertEqual(len(s), 3)
        groups = text.group_sentences(s, min_chars=15)
        self.assertEqual(groups[0], "Short. Also short.")   # "Short." alone is too short a line to voice
        self.assertEqual(len(text.group_sentences(s, min_chars=30)), 1)
        self.assertEqual(" ".join(groups), " ".join(s))

    def test_long_sentences_split_at_commas(self):
        long = ", ".join(["this clause keeps going"] * 20) + "."
        groups = text.group_sentences([long], max_chars=120)
        self.assertTrue(all(len(g) <= 120 for g in groups))
        self.assertEqual(" ".join(groups), long)

    def test_caption_timing_covers_the_chunk(self):
        ev = text.caption_events("one two three four five six seven", 10.0, 13.5)
        self.assertEqual(ev[0][0], 10.0)
        self.assertAlmostEqual(ev[-1][1], 13.5)
        self.assertEqual([e[2] for e in ev], ["one two three", "four five six", "seven"])

    def test_srt_and_ass(self):
        self.assertEqual(text.ts_srt(3661.5), "01:01:01,500")
        self.assertEqual(text.ts_ass(65.25), "0:01:05.25")
        srt = text.to_srt([(0, 1.2, "hi there")])
        self.assertIn("00:00:00,000 --> 00:00:01,200", srt)
        ass = text.to_ass([(0, 1, "a {weird} line")])
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:01.00,Caption,,0,0,0,,a (weird) line", ass)

    def test_chapters_follow_youtube_rules(self):
        ch = text.chapters([(0.4, "Hook"), (5, "Too soon"), (40, "Part one"), (95, "Wrap up")])
        self.assertEqual(ch, ["0:00 Hook", "0:40 Part one", "1:35 Wrap up"])
        self.assertEqual(text.chapters([(0, "A"), (30, "B")]), [])   # YouTube needs 3+

    def test_slugify(self):
        self.assertEqual(text.slugify("Copilot vs. Claude Code: Which?"), "copilot-vs-claude-code-which")
        self.assertEqual(text.slugify("../../etc"), "etc")


class OutlineTests(unittest.TestCase):
    def test_validate_outline(self):
        o = validate_outline({"title": "T", "sections": [{"heading": f"S{i}", "points": ["p"], "stock_queries": ["q"]}
                                                          for i in range(4)] + [{"nope": 1}]})
        self.assertEqual(len(o["sections"]), 4)
        with self.assertRaises(ScriptError):
            validate_outline({"sections": [{"heading": "only one"}]})

    def test_section_count(self):
        self.assertEqual(section_count(1), 3)
        self.assertEqual(section_count(10), 9)


class ShotTests(unittest.TestCase):
    def test_plan_shots_marks_chapter_starts(self):
        from studio.pipeline import plan_shots
        plan = {"sections": [{"heading": "Hook", "stock_queries": ["a", "b"], "narration": "One sentence here, long enough. Two."},
                             {"heading": "Next", "stock_queries": [], "narration": "Another section with words in it."}]}
        shots = plan_shots(plan)
        self.assertEqual([s["first"] for s in shots], [True, True])
        self.assertEqual(shots[1]["queries"], ["Next"])   # falls back to the heading


if __name__ == "__main__":
    unittest.main()
