from __future__ import annotations

import json
import shlex
from pathlib import Path
from zipfile import ZipFile

from helpers import REPO, SCRIPT, SelectorCase, load_selector, write_skill


class PackageTests(SelectorCase):
    def archives(self):
        builder = load_selector(REPO / "tools/build_release.py")
        return builder.build(REPO, self.tmp / "release")

    def test_manifests_parse_and_reference_existing_paths(self):
        for filename in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                         ".codex-plugin/plugin.json", ".agents/plugins/marketplace.json"):
            with self.subTest(filename=filename):
                manifest = json.loads((REPO / filename).read_text())
                self.assertEqual(manifest["name"], "skill-selector")
                if filename.endswith("/plugin.json"):
                    self.assertTrue((REPO / manifest["hooks"]).is_file())
                    if filename.startswith(".codex"):
                        self.assertTrue((REPO / manifest["skills"]).is_dir())
                else:
                    source = manifest["plugins"][0]["source"]
                    self.assertEqual(source if isinstance(source, str) else source["path"], "./")

    def test_hook_commands_point_at_the_script(self):
        hooks = json.loads((REPO / "hooks/claude-codex-hooks.json").read_text())["hooks"]
        for groups in hooks.values():
            command = groups[0]["hooks"][0]["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(REPO))
            script = Path(shlex.split(command)[1])
            self.assertEqual(script, SCRIPT)
            self.assertTrue(script.is_file())

    def test_no_top_level_bin(self):
        self.assertFalse((REPO / "bin").exists())

    def test_skill_md_frontmatter_whitelist(self):
        text = (SCRIPT.parents[1] / "SKILL.md").read_text()
        meta, _ = self.s.parse_frontmatter(text)
        self.assertEqual(set(meta), {"name", "description", "license"})
        self.assertEqual(meta["name"], "skill-selector")
        self.assertLessEqual(len(meta["description"]), 1024)
        self.assertLess(len(text.splitlines()), 60)

    def test_release_archives(self):
        release = self.archives()
        self.assertEqual(release["skill"].name, "skill-selector.zip")
        self.assertEqual(release["plugin"].name, "skill-selector.plugin")
        with ZipFile(release["skill"]) as archive:
            self.assertCountEqual(archive.namelist(), ["skill-selector/SKILL.md", "skill-selector/scripts/selector.py"])
        with ZipFile(release["plugin"]) as archive:
            names = set(archive.namelist())
            self.assertTrue({".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".codex-plugin/plugin.json",
                             ".agents/plugins/marketplace.json", "skills/skill-selector/SKILL.md", "README.md", "LICENSE",
                             "hooks/claude-codex-hooks.json", "skills/skill-selector/scripts/selector.py"} <= names)
            for name in names:
                self.assertFalse(set(Path(name).parts) & {"tests", "docs", "tools", "__pycache__", "dist", ".git", ".DS_Store"})

    def test_skill_runs_from_extracted_zip(self):
        with ZipFile(self.archives()["skill"]) as archive:
            archive.extractall(self.tmp / "upload")
        skill = self.tmp / "upload/skill-selector"
        installed = load_selector(skill / "scripts/selector.py")
        write_skill(skill / "library", "quartz", "reconcile supplier invoices")
        from io import StringIO
        out = StringIO()
        self.assertEqual(installed.main(["search", "supplier invoices", "--json"], stdout=out), 0)
        row, = json.loads(out.getvalue())
        self.assertEqual((row["name"], row["source"]), ("quartz", "library"))
