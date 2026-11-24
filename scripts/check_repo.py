#!/usr/bin/env python3
"""Check the marketplace, its plugins and their skills before a release.

Run from anywhere inside the repository:

    python scripts/check_repo.py                    # content checks
    python scripts/check_repo.py --base origin/main # also require a version bump for every
                                                    # plugin that changed since the base

Exits 1 and lists every problem when a check fails. Requires PyYAML.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_SH = ROOT / "skills.sh.json"

# Agent Skills specification: https://agentskills.io/specification
SKILL_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SKILL_NAME_MAX = 64
DESCRIPTION_MAX = 1024
SKILL_MD_LINES_RECOMMENDED = 500

# Anthropic directory pre-submission checklist: larger or binary files hold a version for review.
TEXT_FILE_MAX_BYTES = 256 * 1024
PLUGIN_FILES_MAX = 512
README_MIN_WORDS = 40
IMAGE_AND_FONT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".woff", ".woff2", ".ttf", ".otf",
}
FORBIDDEN_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", "__MACOSX", "__pycache__"}
FORBIDDEN_SUFFIXES = {".pyc"}
WINDOWS_DEVICE_NAMES = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {
    f"lpt{i}" for i in range(1, 10)
}
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

problems: list[str] = []
notes: list[str] = []


def problem(message: str) -> None:
    problems.append(message)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problem(f"{rel(path)}: missing")
    except json.JSONDecodeError as error:
        problem(f"{rel(path)}: invalid JSON ({error})")
    return None


def version_tuple(version: str) -> tuple[int, int, int] | None:
    match = VERSION.match(version or "")
    return tuple(int(part) for part in match.groups()) if match else None


def check_marketplace() -> list[tuple[str, Path]]:
    marketplace = load_json(MARKETPLACE)
    if marketplace is None:
        return []
    for key in ("name", "owner", "plugins"):
        if key not in marketplace:
            problem(f"{rel(MARKETPLACE)}: missing '{key}'")

    plugins: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for index, entry in enumerate(marketplace.get("plugins", [])):
        where = f"{rel(MARKETPLACE)} plugins[{index}]"
        name = entry.get("name")
        source = entry.get("source")
        if not name:
            problem(f"{where}: missing 'name'")
            continue
        if name in seen:
            problem(f"{where}: duplicate plugin name '{name}'")
        seen.add(name)
        if "version" in entry:
            problem(f"{where}: set 'version' in plugin.json only, not in the marketplace entry")
        if not isinstance(source, str) or not source.startswith("./plugins/"):
            problem(f"{where}: 'source' must be a path under ./plugins/")
            continue
        plugin_dir = (ROOT / source).resolve()
        if not plugin_dir.is_dir():
            problem(f"{where}: source folder {source} does not exist")
            continue
        plugins.append((name, plugin_dir))
    return plugins


def check_plugin(name: str, plugin_dir: Path) -> None:
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = load_json(manifest_path)
    if manifest is None:
        return
    where = rel(manifest_path)
    if manifest.get("name") != name:
        problem(f"{where}: name '{manifest.get('name')}' differs from the marketplace entry '{name}'")
    version = manifest.get("version", "")
    if version_tuple(version) is None:
        problem(f"{where}: 'version' must be MAJOR.MINOR.PATCH, found '{version}'")
    for key in ("description", "author", "license", "repository"):
        if not manifest.get(key):
            problem(f"{where}: missing '{key}'")

    check_readme(plugin_dir / "README.md")
    if not (plugin_dir / "LICENSE").is_file():
        problem(f"{rel(plugin_dir)}: missing LICENSE")
    check_changelog(plugin_dir / "CHANGELOG.md", version)

    skills_dir = plugin_dir / "skills"
    skill_dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir()) if skills_dir.is_dir() else []
    if not skill_dirs:
        problem(f"{rel(plugin_dir)}: no skills under skills/")
    for skill_dir in skill_dirs:
        check_skill(skill_dir)
    check_files(plugin_dir)


def check_readme(path: Path) -> None:
    if not path.is_file():
        problem(f"{rel(path)}: missing")
        return
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    words = len(re.findall(r"\w+", text))
    if words < README_MIN_WORDS:
        problem(f"{rel(path)}: {words} words outside code blocks, the directory needs {README_MIN_WORDS}")


def check_changelog(path: Path, version: str) -> None:
    if not path.is_file():
        problem(f"{rel(path)}: missing")
        return
    if not re.search(rf"^## {re.escape(version)}\b", path.read_text(encoding="utf-8"), flags=re.M):
        problem(f"{rel(path)}: no '## {version}' section for the version in plugin.json")


def check_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        problem(f"{rel(skill_dir)}: missing SKILL.md")
        return
    text = skill_md.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if not match:
        problem(f"{rel(skill_md)}: no YAML frontmatter between '---' lines")
        return
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        problem(f"{rel(skill_md)}: frontmatter is not valid YAML ({error})")
        return

    name = frontmatter.get("name")
    if name != skill_dir.name:
        problem(f"{rel(skill_md)}: name '{name}' must match the folder name '{skill_dir.name}'")
    if not isinstance(name, str) or not SKILL_NAME.match(name) or len(name) > SKILL_NAME_MAX:
        problem(f"{rel(skill_md)}: name must be lowercase letters, digits and single hyphens, "
                f"at most {SKILL_NAME_MAX} characters")

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        problem(f"{rel(skill_md)}: description must be a non-empty string")
    elif len(description) > DESCRIPTION_MAX:
        problem(f"{rel(skill_md)}: description has {len(description)} characters, "
                f"the limit is {DESCRIPTION_MAX}")

    lines = text.count("\n")
    if lines > SKILL_MD_LINES_RECOMMENDED:
        notes.append(f"{rel(skill_md)}: {lines} lines, the Agent Skills guidance is under "
                     f"{SKILL_MD_LINES_RECOMMENDED}")


def committed_line_endings() -> dict[str, str]:
    """Line endings of tracked files as git stores them, keyed by repository path.

    Users receive the committed content, so that is what has to be LF. A working copy on
    Windows with core.autocrlf=true has CRLF even though the repository holds LF.
    """
    try:
        output = git("ls-files", "--eol", "-z")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    endings: dict[str, str] = {}
    for record in output.split("\0"):
        if "\t" in record:
            info, path = record.split("\t", 1)
            endings[path] = info.split()[0].removeprefix("i/")
    return endings


def working_copy_converts_crlf() -> bool:
    try:
        return git("config", "--get", "core.autocrlf").strip().lower() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_files(plugin_dir: Path) -> None:
    committed = committed_line_endings()
    autocrlf = working_copy_converts_crlf()
    file_count = 0
    lowered: dict[str, Path] = {}
    for path in sorted(plugin_dir.rglob("*")):
        where = rel(path)
        key = where.lower()
        if key in lowered:
            problem(f"{where}: differs from {rel(lowered[key])} only by capitalization")
        lowered[key] = path
        if path.is_symlink():
            problem(f"{where}: symbolic links are not allowed in a plugin")
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix in FORBIDDEN_SUFFIXES:
            problem(f"{where}: system or build file, remove it")
        if path.name.split(".")[0].lower() in WINDOWS_DEVICE_NAMES:
            problem(f"{where}: Windows device name")
        if re.search(r'[:<>"|?*]', path.name) or path.name.endswith((".", " ")):
            problem(f"{where}: name is not valid on Windows")
        if not path.is_file():
            continue
        file_count += 1
        if path.suffix.lower() in IMAGE_AND_FONT_SUFFIXES:
            continue
        data = path.read_bytes()
        if len(data) > TEXT_FILE_MAX_BYTES:
            problem(f"{where}: {len(data) // 1024} KiB, keep text files under "
                    f"{TEXT_FILE_MAX_BYTES // 1024} KiB")
        if where in committed:
            if committed[where] in ("crlf", "mixed"):
                problem(f"{where}: committed with CRLF line endings, commit it with LF")
        elif b"\r\n" in data and not autocrlf:
            problem(f"{where}: CRLF line endings, use LF")
        if data.startswith(b"\xef\xbb\xbf"):
            problem(f"{where}: starts with a UTF-8 byte order mark")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            problem(f"{where}: not UTF-8 text; only text, images and fonts belong in a plugin")
    if file_count > PLUGIN_FILES_MAX:
        problem(f"{rel(plugin_dir)}: {file_count} files, keep it at {PLUGIN_FILES_MAX} or fewer")


def check_skills_sh(plugins: list[tuple[str, Path]]) -> None:
    config = load_json(SKILLS_SH)
    if config is None:
        return
    paths = set(config.get("paths", []))
    for name, plugin_dir in plugins:
        expected = f"./{rel(plugin_dir / 'skills')}"
        if expected not in paths:
            problem(f"{rel(SKILLS_SH)}: add '{expected}' to 'paths' so npx skills finds '{name}'")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def check_version_bumps(base: str, plugins: list[tuple[str, Path]]) -> None:
    merge_base = git("merge-base", base, "HEAD").strip()
    for name, plugin_dir in plugins:
        folder = rel(plugin_dir)
        if not git("diff", "--name-only", merge_base, "--", folder).strip():
            continue
        manifest = f"{folder}/.claude-plugin/plugin.json"
        try:
            old = json.loads(git("show", f"{merge_base}:{manifest}")).get("version", "")
        except subprocess.CalledProcessError:
            continue  # the plugin is new on this branch
        new = json.loads((ROOT / manifest).read_text(encoding="utf-8")).get("version", "")
        old_tuple, new_tuple = version_tuple(old), version_tuple(new)
        if old_tuple and new_tuple and new_tuple <= old_tuple:
            problem(f"{name}: files changed since {base} but version {new} is not higher than {old}; "
                    "users would not receive the change")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", help="git ref to compare against for the version bump check")
    args = parser.parse_args()

    plugins = check_marketplace()
    for name, plugin_dir in plugins:
        check_plugin(name, plugin_dir)
    check_skills_sh(plugins)
    if args.base:
        check_version_bumps(args.base, plugins)

    for note in notes:
        print(f"note: {note}")
    if problems:
        for message in problems:
            print(f"error: {message}")
        print(f"\n{len(problems)} problem(s) found.")
        return 1
    print(f"OK: {len(plugins)} plugin(s) checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
