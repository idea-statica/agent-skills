#!/usr/bin/env python3
"""Build the release files for one plugin tag.

    python scripts/build_release.py ideastatica-connection-api--v1.0.0 --out dist

The tag has the form `<plugin>--v<version>`, as `claude plugin tag` creates it. Writes to the
output folder:

    <plugin>-<version>.zip         the plugin folder, for claude.ai "Upload plugin"
    <skill>-<version>.zip          one per skill, the skill folder at the top level, for
                                   claude.ai "Upload skill" and manual installs
    release-notes.md               the CHANGELOG section for the version

Fails when the tag does not match the version in plugin.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = re.compile(r"^(?P<plugin>[a-z0-9]+(?:-[a-z0-9]+)*)--v(?P<version>\d+\.\d+\.\d+)$")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # identical bytes for identical content


def write_zip(source: Path, archive: Path, top_level: str) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(f"{top_level}/{path.relative_to(source).as_posix()}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def changelog_section(changelog: Path, version: str) -> str:
    text = changelog.read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    if not match:
        raise SystemExit(f"error: {changelog} has no '## {version}' section")
    return match.group(1).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="release tag, <plugin>--v<version>")
    parser.add_argument("--out", default="dist", help="output folder (default: dist)")
    args = parser.parse_args()

    match = TAG.match(args.tag)
    if not match:
        raise SystemExit(f"error: tag '{args.tag}' is not <plugin>--v<MAJOR.MINOR.PATCH>")
    plugin, version = match["plugin"], match["version"]

    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next((e for e in marketplace["plugins"] if e["name"] == plugin), None)
    if entry is None:
        raise SystemExit(f"error: plugin '{plugin}' is not in marketplace.json")
    plugin_dir = (ROOT / entry["source"]).resolve()
    manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if manifest.get("version") != version:
        raise SystemExit(f"error: tag version {version} differs from plugin.json version "
                         f"{manifest.get('version')}")

    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    write_zip(plugin_dir, out / f"{plugin}-{version}.zip", plugin)
    for skill_dir in sorted(d for d in (plugin_dir / "skills").iterdir() if d.is_dir()):
        write_zip(skill_dir, out / f"{skill_dir.name}-{version}.zip", skill_dir.name)

    notes = changelog_section(plugin_dir / "CHANGELOG.md", version)
    (out / "release-notes.md").write_text(notes, encoding="utf-8", newline="\n")

    for path in sorted(out.iterdir()):
        print(f"{path.relative_to(ROOT).as_posix()}  {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
