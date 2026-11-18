from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build(repo_root: Path, out_dir: Path) -> dict[str, Path]:
    skill = repo_root / "skills/skill-selector"
    skill_files = [skill / "SKILL.md", skill / "scripts/selector.py"]
    plugin_files = [repo_root / name for name in (
        ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json", "hooks/claude-codex-hooks.json", "README.md", "LICENSE", "assets/icon.png")]
    for path in skill_files + plugin_files:
        if not path.is_file():
            raise FileNotFoundError(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    archives = {"skill": out_dir / "skill-selector.zip", "plugin": out_dir / "skill-selector.plugin"}
    for kind, base, paths in (("skill", skill.parent, skill_files), ("plugin", repo_root, plugin_files + skill_files)):
        with ZipFile(archives[kind], "w", compression=ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, path.relative_to(base))
    return archives


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args()
    for path in build(Path(__file__).resolve().parents[1], args.out).values():
        print(path)
