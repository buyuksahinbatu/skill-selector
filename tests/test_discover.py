from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from helpers import SelectorCase, write_skill


class DiscoveryTests(SelectorCase):
    def entries(self):
        return self.s.discover(self.env)[0]

    def test_user_roots_and_labels(self):
        roots = {"claude-user": self.root, "codex-user": self.home / ".codex/skills",
                 "agents-user": self.home / ".agents/skills", "project": self.cwd / ".claude/skills",
                 "parked": self.state / "parked/claude-user", "sandbox": self.env.sandbox_root / "public",
                 "library": self.env.skill_dir / "library"}
        for label, root in roots.items():
            write_skill(root, label, "skill")
        self.assertEqual({s["name"]: s["source"] for s in self.entries()}, {k: k for k in roots})

    def test_nested_and_depth_limit(self):
        write_skill(self.root / "cat", "x", "")
        write_skill(self.root / "a/b/c", "four", "")
        write_skill(self.root / "a/b/c/d", "five", "")
        self.assertEqual(sorted(s["name"] for s in self.entries()), ["four", "x"])

    def test_hidden_archive_skipped_but_system_indexed(self):
        write_skill(self.root / ".archive", "x", "")
        write_skill(self.env.codex_home / "skills/.system", "y", "")
        self.assertEqual([(s["name"], s["source"]) for s in self.entries()], [("y", "codex-user")])

    def test_hidden_archive_symlink_skipped(self):
        write_skill(self.tmp / "retired", "x", "")
        self.root.mkdir(parents=True)
        (self.root / ".archive").symlink_to(self.tmp / "retired")
        self.assertEqual(self.entries(), [])

    def test_symlink_into_other_root_is_one_entry(self):
        target = write_skill(self.home / ".agents/skills", "c", "")
        self.root.mkdir(parents=True)
        (self.root / "c").symlink_to(target)
        self.assertEqual([s["source"] for s in self.entries()], ["claude-user"])

    def test_symlink_cycle_terminates(self):
        write_skill(self.root / "cat", "test", "")
        (self.root / "cat/back").symlink_to(self.root)
        self.assertEqual([s["name"] for s in self.entries()], ["test"])

    def test_claude_plugin_enablement(self):
        db = {}
        for key in ("enabled", "disabled"):
            plugin = self.tmp / key
            write_skill(plugin / "skills", key, "")
            db[key] = [{"installPath": str(plugin)}]
        db["enabled"] = db["enabled"][0]
        path = self.home / ".claude/plugins/installed_plugins.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 2, "plugins": db}))
        (path.parents[1] / "settings.json").write_text('{"enabledPlugins":{"disabled":false}}')
        self.assertEqual([s["source"] for s in self.entries()], ["claude-plugin:enabled"])

    def test_codex_plugin_newest_version_wins(self):
        cache = self.env.codex_home / "plugins/cache/market/plugin"
        for version, stamp in [("9", 100), ("2", 200)]:
            folder = write_skill(cache / version / "skills", "same", version)
            for path in (folder / "SKILL.md", folder, folder.parent, folder.parent.parent):
                os.utime(path, (stamp, stamp))
        self.assertEqual([(s["source"], s["path"]) for s in self.entries()],
                         [("codex-plugin:market/plugin", str(cache / "2/skills/same/SKILL.md"))])

    def test_selector_copies_excluded(self):
        copy = write_skill(self.root, "skill-selector", "")
        (copy / "scripts").mkdir()
        (copy / "scripts/selector.py").touch()
        self.assertFalse(self.entries())

    def test_project_root_equal_to_home_skipped(self):
        self.env.cwd = self.home
        write_skill(self.root, "user", "")
        self.assertEqual(self.entries()[0]["source"], "claude-user")

    def test_bad_files_reported(self):
        for name, data in [("bad", b"\xff"), ("plain", b"hello"), ("binary", b"\x00hi")]:
            path = write_skill(self.root, name, "") / "SKILL.md"
            path.write_bytes(data)
        entries, problems = self.s.discover(self.env)
        self.assertEqual([(s["name"], s["description"]) for s in entries], [("plain", "")])
        reasons = {Path(p["path"]).parent.name: p["reason"] for p in problems}
        self.assertEqual(reasons["bad"], "not-utf8")
        self.assertEqual(reasons["plain"], "no-frontmatter")
        self.assertIn(reasons["binary"], ("unreadable", "not-utf8"))

    def test_config_extra_roots_and_exclude_sources(self):
        write_skill(self.root, "skip", "")
        write_skill(self.tmp / ".extra", "added", "")
        self.state.mkdir()
        (self.state / "config.json").write_text(json.dumps({
            "exclude_sources": ["claude-user"], "extra_roots": [str(self.tmp / ".extra")]}))
        self.assertEqual([s["source"] for s in self.entries()], ["extra"])

    def test_malformed_config_uses_defaults(self):
        self.state.mkdir()
        (self.state / "config.json").write_text("{")
        self.assertEqual(self.s.load_config(self.env), self.s.DEFAULT_CONFIG)

    def test_index_roundtrip_is_atomic(self):
        write_skill(self.root, "one", "")
        idx = self.s.build_index(self.env)
        self.assertTrue(self.s.save_index(self.env, idx))
        self.assertEqual(list(self.state.iterdir()), [self.state / "index.json"])
        with patch.object(self.s, "build_index", side_effect=AssertionError):
            self.assertEqual(self.s.load_index(self.env), idx)

    def test_corrupt_or_old_index_rebuilt(self):
        write_skill(self.root, "one", "")
        self.state.mkdir()
        path = self.state / "index.json"
        for data in ("{", '{"version":0}'):
            path.write_text(data)
            self.assertEqual(self.s.load_index(self.env)["count"], 1)
        idx = self.s.load_index(self.env)
        idx["built_at"] = 0
        path.write_text(json.dumps(idx))
        write_skill(self.root, "two", "")
        self.assertEqual(self.s.load_index(self.env)["count"], 2)

    def test_index_from_before_hidden_directory_filter_is_rebuilt(self):
        write_skill(self.root / "archive", "retired", "")
        index = self.s.build_index(self.env)
        index["version"] = 2
        self.assertTrue(self.s.save_index(self.env, index))
        (self.root / "archive").rename(self.root / ".archive")
        self.assertEqual(self.s.load_index(self.env)["skills"], [])

    def test_unwritable_state_dir(self):
        self.state.touch()
        self.env.state_dir = self.state / "child"
        write_skill(self.root, "one", "")
        self.assertFalse(self.s.save_index(self.env, self.s.build_index(self.env)))
        self.assertEqual(self.s.load_index(self.env)["count"], 1)

    def test_deadline_raises_timeout(self):
        with self.assertRaises(TimeoutError):
            self.s.discover(self.env, deadline=time.monotonic() - 1)

    def test_cli_index_output(self):
        for root, name in [(self.root, "one"), (self.root, "two"), (self.home / ".agents/skills", "three")]:
            write_skill(root, name, "")
        self.assertEqual(self.cli("index"), (0, "indexed 3 skills from 2 sources\n"))

    def test_weighted_terms_dedup_and_body_limit(self):
        header = "---\nname: quartz\ndescription: quartz\nwhen_to_use: scan\n---"
        for root in (self.root, self.home / ".agents/skills"):
            write_skill(root, "q", "", "quartz" + " " * 2000 + "ignored", header)
        idx = self.s.build_index(self.env)
        self.assertEqual(idx["count"], 1)
        skill = idx["skills"][0]
        self.assertEqual(skill["description"], "quartz scan")
        self.assertEqual(skill["tf"], {"quartz": 6, "scan": 2})
        self.assertEqual((skill["dl"], idx["avgdl"]), (8, 8))
        self.assertEqual(idx["nd_df"], {"quartz": 1, "scan": 1})
