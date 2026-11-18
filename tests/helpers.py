from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills/skill-selector/scripts/selector.py"


def load_selector(path=SCRIPT):
    spec = importlib.util.spec_from_file_location("selector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(root, name, description, body="", raw_frontmatter=None):
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    header = raw_frontmatter
    if header is None:
        header = "---\nname: %s\ndescription: %s\n---" % (name, json.dumps(description, ensure_ascii=False))
    (directory / "SKILL.md").write_text(header + "\n" + body, encoding="utf-8")
    return directory


class IsolatedCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=str(REPO))
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.home = self.tmp / "home"
        self.cwd = self.tmp / "project"
        self.state = self.tmp / "state"
        self.home.mkdir()
        self.cwd.mkdir()
        env = {"HOME": str(self.home), "SKILL_SELECTOR_HOME": str(self.state),
               "CODEX_HOME": str(self.home / ".codex"),
               "SKILL_SELECTOR_SANDBOX_ROOT": str(self.tmp / "sandbox")}
        env_patch = patch.dict(os.environ, env, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.cwd)
        self.s = load_selector()


def make_env(tmp, **overrides):
    env = load_selector().Env.from_os({
        "HOME": str(tmp / "home"),
        "CODEX_HOME": str(tmp / "home/.codex"),
        "SKILL_SELECTOR_HOME": str(tmp / "state"),
        "SKILL_SELECTOR_SANDBOX_ROOT": str(tmp / "sandbox"),
    }, tmp / "project")
    env.skill_dir = tmp / "selector"
    for key, value in overrides.items():
        setattr(env, key, value)
    return env


class SelectorCase(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.env = make_env(self.tmp)
        self.root = self.home / ".claude/skills"

    def cli(self, *args, payload=""):
        buf = StringIO()
        code = self.s.main(list(args), env=self.env, stdin=StringIO(payload), stdout=buf)
        return code, buf.getvalue()
