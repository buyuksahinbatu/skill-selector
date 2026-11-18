from __future__ import annotations

import json
import time

from corpus_gen import generate_corpus, write_targets
from helpers import SelectorCase, write_skill

FIXTURE = [
 ("systematic-debugging", "Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes.", "debug failing test"),
 ("frontend-design", "Create distinctive, production-grade frontend interfaces with high design quality.", "frontend interface design"),
 ("pdf-forms", "Fill, sign and flatten PDF forms; extract form fields.", "fill pdf form"),
 ("turkish-native", "Write and rewrite Turkish so it reads as native Turkish rather than translated English.", "rewrite turkish copy"),
 ("rn-performance", "React Native performance: FlatList, Hermes, bundle size, re-renders.", "react native flatlist performance"),
 ("git-commits", "Write conventional commit messages and split changes into atomic commits.", "commit message"),
]


class SearchTests(SelectorCase):
    def test_skill_path_with_double_space_is_printed_verbatim(self):
        directory = write_skill(self.tmp / "My  Skills", "quartz-ledger", "Reconcile quartz ledger exports.")
        (self.state).mkdir(parents=True, exist_ok=True)
        (self.state / "config.json").write_text(json.dumps({"extra_roots": [str(self.tmp / "My  Skills")]}))
        code, out = self.cli("search", "quartz", "ledger", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]["path"], str(directory / "SKILL.md"))

    def test_zero_length_corpus_returns_no_match(self):
        for name in ("a", "b"):  # one-letter names tokenize to nothing
            write_skill(self.root, name, "")
        index = self.s.build_index(self.env)
        self.assertEqual([s["dl"] for s in index["skills"]], [0, 0])
        term, = self.s.tokenize("anything")
        for df in ({}, {term: 1}):
            with self.subTest(df=df):
                index["df"] = df  # A saved index can retain a stale term frequency.
                self.assertTrue(self.s.save_index(self.env, index))
                self.assertEqual(self.s.search(index, "anything"), [])
                self.assertEqual(self.cli("search", "anything"), (0, "no match\n"))

    def test_unknown_source_sorts_after_known_source(self):
        for name in ("alpha", "zulu"):
            write_skill(self.root, name, "quartz")
        index = self.s.build_index(self.env)
        for skill in index["skills"]:
            skill["source"] = "future-host" if skill["name"] == "alpha" else "extra"
        expected = ["extra", "future-host"]
        with self.subTest(command="doctor"):
            report = self.s.doctor_report(index)
            self.assertEqual([row["source"] for row in report["sources"]], expected)
        with self.subTest(command="search"):
            results = self.s.search(index, "quartz")
            self.assertEqual([row["source"] for row in results], expected)
            self.assertEqual(results[0]["score"], results[1]["score"])

    def test_fixture_ranking(self):
        for name, description, _ in FIXTURE:
            write_skill(self.root, name, description)
        index = self.s.build_index(self.env)
        for name, _, query in FIXTURE:
            with self.subTest(query=query):
                self.assertEqual(self.s.search(index, query)[0]["name"], name)

    def test_rare_limit_small_and_large_corpus(self):
        for count, limit in ((149, 3), (150, 3), (300, 6)):
            index = {"count": count, "nd_df": {"last": limit, "above": limit + 1}}
            self.assertTrue(self.s.is_rare(index, "last"))
            self.assertFalse(self.s.is_rare(index, "above"))
            self.assertFalse(self.s.is_rare(index, "never"))

    def test_bare_numbers_never_rare(self):
        generate_corpus(self.root, n=299)
        write_skill(self.root, "release-notes", "Review release 87")
        index = self.s.build_index(self.env)
        self.assertEqual(index["nd_df"]["87"], 1)
        self.assertFalse(self.s.is_rare(index, "87"))
        result, = self.s.search(index, "87")
        self.assertEqual(result["name"], "release-notes")
        self.assertGreater(result["score"], 0)

    def test_strong_needs_rare_hits_and_coverage(self):
        generate_corpus(self.root, n=300)
        write_targets(self.root)
        index = self.s.build_index(self.env)
        rank = self.s.search(index, "reconcile supplier invoices ledger")
        self.assertEqual(rank[0]["name"], "quartz-invoice-reconciler")
        self.assertTrue(rank[0]["strong"])
        self.assertFalse(any(r["strong"] for r in self.s.search(index, "fix test page update", top=400)))
        rank = self.s.search(index, "supplier ledger kubernetes kafka terraform shopify", top=400)
        self.assertFalse(next(r for r in rank if r["name"] == "quartz-invoice-reconciler")["strong"])

    def test_strong_by_full_name(self):
        generate_corpus(self.root, n=300)
        write_skill(self.root, "frontend-design", "")
        rank = self.s.search(self.s.build_index(self.env), "improve the frontend design")
        self.assertEqual(rank[0]["name"], "frontend-design")
        self.assertTrue(rank[0]["strong"])

    def test_tie_break_by_source_priority(self):
        for host, name in [(".agents", "aaa"), (".codex", "zzz")]:
            write_skill(self.home / host / "skills", name, "quartz")
        rank = self.s.search(self.s.build_index(self.env), "quartz")
        self.assertEqual([r["source"] for r in rank], ["codex-user", "agents-user"])
        self.assertEqual(rank[0]["score"], rank[1]["score"])

    def test_search_cli_text_json_and_no_match(self):
        path = write_skill(self.root, "quartz", "reconcile " * 40) / "SKILL.md"
        code, text = self.cli("search", "reconcile", "quartz", "--top", "1")
        self.assertEqual(code, 0)
        self.assertIn("1. quartz  [claude-user]  score ", text)
        self.assertIn(str(path), text)
        self.assertNotIn("also in:", text)
        code, data = self.cli("search", "quartz", "--json")
        result, = json.loads(data)
        self.assertEqual(set(result), {"name", "source", "score", "strong", "description", "path", "also"})
        self.assertEqual(result["also"], [])
        self.assertLessEqual(len(result["description"]), 300)
        self.assertEqual(self.cli("search", "xyz"), (0, "no match\n"))
        self.assertEqual(json.loads(self.cli("search", "xyz", "--json")[1]), [])

    def test_search_collapses_names_before_top(self):
        for host, description in [(".claude", "quartz checklist"), (".codex", "quartz " * 8),
                                  (".agents", "quartz quartz")]:
            write_skill(self.home / host / "skills", "shared", description)
        for name in ("alpha", "beta"):
            write_skill(self.root, name, "", "quartz")
        code, data = self.cli("search", "quartz", "--top", "3", "--json")
        self.assertEqual(code, 0)
        rows = json.loads(data)
        self.assertEqual([row["name"] for row in rows], ["shared", "alpha", "beta"])
        self.assertEqual(rows[0]["source"], "codex-user")
        self.assertEqual(rows[0]["also"], ["claude-user", "agents-user"])
        _, text = self.cli("search", "quartz", "--top", "1")
        self.assertIn("   also in: claude-user, agents-user", text.splitlines())

    def test_show_prints_base_directory(self):
        folder = write_skill(self.root, "quartz", "reconcile", "See docs/note.")
        self.assertEqual(self.cli("show", "quartz"),
                         (0, "Base directory: %s\n\n%s" % (folder, (folder / "SKILL.md").read_text())))

    def test_show_not_found_returns_1(self):
        self.assertEqual(self.cli("show", "absent"), (1, "not found: absent\n"))

    def test_show_ambiguous_lists_sources_and_source_flag_resolves(self):
        for host in (".claude", ".agents"):
            write_skill(self.home / host / "skills", "quartz", host)
        code, text = self.cli("show", "quartz")
        self.assertEqual(code, 1)
        for source in ("claude-user", "agents-user"):
            self.assertIn("quartz  [%s]" % source, text)
        code, text = self.cli("show", "quartz", "--source", "agents-user")
        self.assertEqual(code, 0)
        self.assertIn('description: ".agents"', text)

    def test_performance_2000(self):
        generate_corpus(self.root, n=2000)
        start = time.perf_counter()
        index = self.s.build_index(self.env)
        built = time.perf_counter()
        result = self.s.search(index, "fix test page update")
        searched = time.perf_counter()
        print("index %.4f s, search %.4f s" % (built - start, searched - built))
        self.assertEqual(index["count"], 2000)
        self.assertTrue(result)
        self.assertLess(built - start, 10)
        self.assertLess(searched - built, 1.5)
