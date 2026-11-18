from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from helpers import SCRIPT, SelectorCase, load_selector, write_skill


class PackTests(SelectorCase):
    def setUp(self):
        super().setUp()
        self.env.skill_dir = SCRIPT.parents[1]
        self.out = self.tmp / "export"

    def test_pack_layout(self):
        first = write_skill(self.root, "one", "amethyst")
        second = write_skill(self.root, "two", "quartz")
        (first / "scripts").mkdir()
        (first / "scripts/run.py").write_bytes(b"print(1)")
        for name in ("node_modules", "__pycache__", ".git"):
            (second / name).mkdir()
            with (second / name / "large").open("wb") as stream:
                stream.truncate(6 * 1024 * 1024)
        (second / ".DS_Store").touch()
        (second / "cache-alias").symlink_to("node_modules")
        code, out = self.cli("pack", "one", "two", "--out", str(self.out))
        archive = self.out / "skill-selector-pack.zip"
        self.assertEqual(code, 0)
        self.assertIn("packed 2 skills into %s (" % archive, out)
        self.assertIn(" KB)", out)
        with ZipFile(archive) as z:
            self.assertCountEqual(z.namelist(), ["skill-selector/" + p for p in (
                "SKILL.md", "scripts/selector.py", "library/one/SKILL.md",
                "library/one/scripts/run.py", "library/two/SKILL.md")])
            self.assertEqual(z.read("skill-selector/library/one/scripts/run.py"), b"print(1)")
            self.assertEqual(z.read("skill-selector/scripts/selector.py"), SCRIPT.read_bytes())

    def test_packed_skill_finds_library_skill(self):
        write_skill(self.root, "quartz", "calibrate oscillator")
        archive, refused = self.s.pack(self.env, ["quartz"], self.out)
        self.assertEqual(refused, [])
        with ZipFile(archive) as z:
            z.extractall(self.tmp / "upload")
        installed = load_selector(self.tmp / "upload/skill-selector/scripts/selector.py")
        home = self.tmp / "empty"
        home.mkdir()
        with patch.dict(os.environ, {"HOME": str(home), "SKILL_SELECTOR_HOME": str(home / "state"),
                                     "CODEX_HOME": str(home / "codex")}):
            buf = StringIO()
            self.assertEqual(installed.main(["search", "oscillator", "--json"], stdout=buf), 0)
            row, = json.loads(buf.getvalue())
            self.assertEqual((row["name"], row["source"]), ("quartz", "library"))
            self.assertTrue(Path(row["path"]).is_file())

    def test_pack_counts_distinct_skills(self):
        for name in ("a", "b"):
            write_skill(self.root, name, "")
        code, out = self.cli("pack", "a", "a", "b", "--out", str(self.out))
        self.assertEqual(code, 0)
        self.assertIn("packed 2 skills into ", out)

    def test_too_large_refused_and_force(self):
        directory = write_skill(self.root, "huge", "assets")
        with (directory / "asset.bin").open("wb") as f:
            f.truncate(6 * 1024 * 1024)
        result, refused = self.s.pack(self.env, ["huge"], self.out)
        self.assertIsNone(result)
        self.assertEqual(refused, [{"name": "huge", "reason": "too-large"}])
        self.assertFalse((self.out / "skill-selector-pack.zip").exists())
        self.assertEqual(self.cli("pack", "huge", "--force", "--out", str(self.out))[0], 0)
        with ZipFile(self.out / "skill-selector-pack.zip") as z:
            self.assertEqual(z.getinfo("skill-selector/library/huge/asset.bin").file_size, 6 * 1024 * 1024)

    def test_ambiguous_and_name_at_source(self):
        write_skill(self.root, "dup", "first")
        second = write_skill(self.home / ".agents/skills", "dup", "second")
        self.assertEqual(self.s.pack(self.env, ["dup"], self.out),
                         (None, [{"name": "dup", "reason": "ambiguous"}]))
        path, refused = self.s.pack(self.env, ["dup@agents-user"], self.out)
        self.assertEqual(refused, [])
        with ZipFile(path) as z:
            self.assertEqual(z.read("skill-selector/library/dup/SKILL.md"), (second / "SKILL.md").read_bytes())
        self.assertEqual(self.cli("pack", "dup@claude-user", "dup@agents-user", "--out", str(self.out))[0], 1)

    def test_refusal_writes_no_archive(self):
        write_skill(self.root, "one", "first")
        for name, reason in (("missing", "not-found"), ("skill-selector", "self")):
            code, output = self.cli("pack", "one", name, "--out", str(self.out))
            self.assertEqual(code, 1)
            self.assertIn(reason, output)
            self.assertFalse((self.out / "skill-selector-pack.zip").exists())

    def test_pack_rejects_external_file_link_without_replacing_archive(self):
        directory = write_skill(self.root, "one", "first")
        path, refused = self.s.pack(self.env, ["one"], self.out)
        self.assertEqual(refused, [])
        before = path.read_bytes()
        outside = self.tmp / "outside"
        outside.write_bytes(b"private")
        (directory / "linked").symlink_to(outside)
        self.assertEqual(self.cli("pack", "one", "--force", "--out", str(self.out))[0], 1)
        self.assertEqual(path.read_bytes(), before)

    def test_skill_md_still_valid(self):
        text = (self.env.skill_dir / "SKILL.md").read_text()
        self.assertEqual(set(self.s.parse_frontmatter(text)[0]), {"name", "description", "license"})
        self.assertLess(len(text.splitlines()), 60)
        self.assertIn("Results with source `parked`", text)
