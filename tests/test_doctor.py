from __future__ import annotations

import json

from helpers import SelectorCase, write_skill


class DoctorTests(SelectorCase):
    def report(self):
        return self.s.doctor_report(self.s.build_index(self.env))

    def test_counts_and_bytes_per_source(self):
        write_skill(self.root, "one", "ş")
        write_skill(self.root, "two", "abc")
        write_skill(self.home / ".agents/skills", "three", "")
        report = self.report()
        self.assertEqual(report["sources"], [
            {"source": "claude-user", "count": 2, "listing_bytes": 11},
            {"source": "agents-user", "count": 1, "listing_bytes": 5}])
        self.assertEqual((report["total"], report["listing_bytes"]), (3, 16))

    def test_duplicates_across_sources(self):
        for host in (".claude", ".agents"):
            write_skill(self.home / host / "skills", "dup", host)
        self.assertEqual(self.report()["duplicates"], [{"name": "dup", "sources": ["claude-user", "agents-user"]}])

    def test_empty_descriptions_and_problems_listed(self):
        path = write_skill(self.root, "plain", "", raw_frontmatter="text") / "SKILL.md"
        report = self.report()
        self.assertEqual(report["empty_descriptions"], [str(path)])
        self.assertEqual(report["problems"], [{"path": str(path), "reason": "no-frontmatter"}])

    def test_longest_descriptions_capped_at_ten(self):
        for i in range(12):
            write_skill(self.root, str(i), "ş" * i)
        self.assertEqual(self.report()["longest_descriptions"],
                         [{"name": str(i), "source": "claude-user", "chars": i} for i in range(11, 1, -1)])

    def test_cli_json_is_valid_and_matches_report(self):
        write_skill(self.root, "one", "details")
        code, text = self.cli("doctor", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(text), self.report())

    def test_doctor_writes_nothing(self):
        write_skill(self.root, "one", "")
        before = sorted(self.tmp.rglob("*"))
        code, text = self.cli("doctor")
        self.assertEqual(code, 0)
        for fragment in ["claude-user", "total", "empty descriptions", "longest descriptions"]:
            self.assertIn(fragment, text.lower())
        self.assertEqual(sorted(self.tmp.rglob("*")), before)
