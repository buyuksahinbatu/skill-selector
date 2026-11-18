from __future__ import annotations

import contextlib
import errno
from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
from unittest.mock import patch

from helpers import SelectorCase, write_skill


class ParkTests(SelectorCase):
    def setUp(self):
        super().setUp()
        self.agents = self.home / ".agents/skills"
        self.parked = self.state / "parked"

    def manifest(self):
        return json.loads((self.parked / "manifest.json").read_text())["entries"]

    def linked_skill(self):
        target = write_skill(self.agents, "c", "calibrate quartz")
        self.root.mkdir(parents=True)
        link = self.root / "c"
        link.symlink_to(os.path.relpath(target, self.root))
        return link, target

    def test_dry_run_changes_nothing(self):
        write_skill(self.root, "x", "example")

        def snapshot():
            return {p: (p.lstat().st_size, p.lstat().st_mtime_ns)
                    for p in [self.home, *self.home.rglob("*")]}

        before = snapshot()
        code, out = self.cli("park", "x")
        self.assertEqual(code, 0)
        self.assertIn("would park", out)
        self.assertEqual(snapshot(), before)
        self.assertFalse(self.state.exists())

    def test_park_apply_and_unpark_roundtrip(self):
        directory = write_skill(self.root, "quartz", "calibrate clock")
        (directory / "scripts").mkdir()
        script = directory / "scripts/run"
        script.write_bytes(b"#!/bin/sh\n")
        script.chmod(0o751)

        def tree(root):
            return {p.relative_to(root): (p.stat().st_mode, p.read_bytes() if p.is_file() else None)
                    for p in root.rglob("*")}

        original = tree(directory)
        self.assertEqual(self.cli("park", "quartz", "--apply")[0], 0)
        self.assertFalse(directory.exists())
        self.assertEqual(tree(self.parked / "claude-user/quartz"), original)
        result, = json.loads(self.cli("search", "calibrate", "--json")[1])
        self.assertEqual(result["source"], "parked")
        entry, = self.manifest()
        self.assertEqual(datetime.fromisoformat(entry["parked_at"]).utcoffset(), timezone.utc.utcoffset(None))
        self.assertIn(entry["parked_at"], self.cli("parked")[1])
        self.assertEqual(json.loads(self.cli("parked", "--json")[1]), [entry])
        self.assertEqual(self.cli("unpark", "quartz")[0], 0)
        self.assertEqual(tree(directory), original)
        self.assertEqual(self.manifest(), [])

    def test_nested_skill_restored_to_same_relative_path(self):
        parent = self.root / "one/two/three"
        path = write_skill(parent, "x", "deep quartz")
        self.assertEqual(self.cli("park", "x", "--apply")[0], 0)
        self.assertTrue((self.parked / "claude-user/one/two/three/x/SKILL.md").is_file())
        self.assertEqual(json.loads(self.cli("search", "deep quartz", "--json")[1])[0]["source"], "parked")
        parent.rmdir()
        self.assertEqual(self.cli("unpark", "--all")[0], 0)
        self.assertTrue((path / "SKILL.md").is_file())

    def test_link_only_parks_link(self):
        link, target = self.linked_skill()
        original = os.readlink(link)
        data = (target / "SKILL.md").read_bytes()
        self.assertIn("target %s stays listed" % original, self.cli("park", "c", "--source", "claude-user")[1])
        self.assertEqual(self.cli("park", "c", "--source", "claude-user", "--apply")[0], 0)
        self.assertFalse(os.path.lexists(link))
        self.assertEqual((target / "SKILL.md").read_bytes(), data)
        entry, = self.manifest()
        self.assertEqual((entry["kind"], entry["parked_path"], entry["link_target"]), ("link", None, original))
        self.assertEqual(self.cli("unpark", "c")[0], 0)
        self.assertEqual(os.readlink(link), original)

    def test_parking_target_parks_incoming_links(self):
        link, target = self.linked_skill()
        self.assertEqual(self.cli("park", "c", "--source", "agents-user", "--apply")[0], 0)
        self.assertFalse(os.path.lexists(link))
        self.assertFalse(target.exists())
        self.assertEqual([e["kind"] for e in self.manifest()], ["link", "dir"])
        self.assertEqual(self.cli("unpark", "c")[0], 0)
        self.assertEqual(link.resolve(), target)
        self.assertTrue((link / "SKILL.md").is_file())

    def test_keep_mode(self):
        for name in "abc":
            write_skill(self.root, name, "example")
        self.assertEqual(self.cli("park", "--source", "claude-user", "--keep", "b", "--apply")[0], 0)
        self.assertCountEqual([e["name"] for e in self.manifest()], ["a", "c"])
        self.assertTrue((self.root / "b").is_dir())

    def test_keep_skips_hidden_archive(self):
        write_skill(self.agents / ".archive", "x", "")
        write_skill(self.agents, "z", "")
        self.assertEqual(self.cli("park", "--source", "agents-user", "--keep", "z"),
                         (0, "would park 0, refused 0\n"))

    def test_refusals(self):
        write_skill(self.cwd / ".agents/skills", "project", "")
        write_skill(self.home / ".codex/plugins/cache/m/p/v1/skills", "plugin", "")
        for root in (self.root, self.agents):
            write_skill(root, "dup", "identical")
        own = write_skill(self.root, "skill-selector", "")
        (own / "scripts").mkdir()
        (own / "scripts/selector.py").touch()
        write_skill(self.root, "collision", "")
        (self.parked / "claude-user/collision").mkdir(parents=True)
        write_skill(self.root, "stored", "")
        self.assertEqual(self.cli("park", "stored", "--apply")[0], 0)
        for name, reason in (("missing", "not-found"), ("plugin", "not-parkable"), ("project", "not-parkable"),
                             ("dup", "ambiguous"), ("skill-selector", "self"), ("collision", "destination-exists"),
                             ("stored", "already-parked")):
            with self.subTest(name=name):
                actions, refusals = self.s.plan_park(self.env, [name])
                self.assertEqual(actions, [])
                self.assertEqual(refusals, [{"name": name, "reason": reason}])

    def test_failed_move_leaves_consistent_manifest(self):
        rename = os.rename
        for name in "abc":
            write_skill(self.root, name, "example")

        def fail_second(src, dst):
            if Path(src).name == "b":
                raise OSError("move failed")
            return rename(src, dst)

        with patch.object(os, "rename", side_effect=fail_second):
            code, out = self.cli("park", "a", "b", "c", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("move failed", out)
        self.assertEqual([e["name"] for e in self.manifest()], ["a", "c"])
        self.assertTrue((self.root / "b/SKILL.md").is_file())

    def test_cross_device_park_keeps_original(self):
        path = write_skill(self.root, "x", "original")
        with patch.object(os, "rename", side_effect=OSError(errno.EXDEV, "x")):
            code, out = self.cli("park", "x", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("refused (cross-device) x", out)
        self.assertTrue((path / "SKILL.md").is_file())
        self.assertFalse((self.parked / "claude-user/x").exists())
        self.assertEqual(self.manifest(), [])

    def test_cross_device_unpark_keeps_parked_copy(self):
        path = write_skill(self.root, "x", "original")
        self.assertEqual(self.cli("park", "x", "--apply")[0], 0)
        before = self.manifest()
        with patch.object(os, "rename", side_effect=OSError(errno.EXDEV, "x")):
            code, out = self.cli("unpark", "x")
        self.assertEqual(code, 1)
        self.assertIn("refused (cross-device) x", out)
        self.assertTrue((self.parked / "claude-user/x/SKILL.md").is_file())
        self.assertFalse(path.exists())
        self.assertEqual(self.manifest(), before)

    def test_unpark_refuses_when_original_exists(self):
        path = write_skill(self.root, "x", "original")
        self.cli("park", "x", "--apply")
        before = self.manifest()
        path.symlink_to("missing")
        code, out = self.cli("unpark", "--all")
        self.assertEqual(code, 1)
        self.assertIn("original-exists", out)
        self.assertEqual(self.manifest(), before)
        self.assertTrue((self.parked / "claude-user/x/SKILL.md").is_file())
        self.assertEqual(os.readlink(path), "missing")

    def test_unpark_missing_entries_and_copy(self):
        write_skill(self.root, "x", "original")
        self.cli("park", "x", "--apply")
        (self.parked / "claude-user/x").rename(self.tmp / "elsewhere")
        restored, refused = self.s.unpark(self.env, ["x", "absent"])
        self.assertEqual(restored, [])
        self.assertEqual({r["reason"] for r in refused}, {"not-parked", "parked-copy-missing"})
        self.assertEqual(len(self.manifest()), 1)

    def test_keep_without_source_is_usage_error(self):
        with contextlib.redirect_stderr(StringIO()), self.assertRaises(SystemExit) as exc:
            self.cli("park", "--keep", "x")
        self.assertEqual(exc.exception.code, 2)

    def test_index_rebuilt_after_apply(self):
        write_skill(self.root, "x", "quartz")
        self.cli("index")
        for args, source in ((("park", "x", "--apply"), "parked"), (("unpark", "x"), "claude-user")):
            self.assertEqual(self.cli(*args)[0], 0)
            self.assertEqual(json.loads((self.state / "index.json").read_text())["sources"], {source: 1})
