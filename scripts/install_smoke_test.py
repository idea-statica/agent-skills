#!/usr/bin/env python3
"""Install every plugin of this marketplace with Claude Code and check that its skills load.

    python scripts/install_smoke_test.py

Adds the repository as a local marketplace, installs each plugin it lists and reads
`claude plugin details <plugin>`, which must name every skill folder of the plugin. Runs in a
temporary CLAUDE_CONFIG_DIR, so your own Claude Code settings stay untouched. Needs the
`claude` CLI on PATH. Where managed settings allow only approved marketplace sources, adding
the local marketplace is refused and the test cannot run.

Exits 1 and prints Claude Code's output when a step fails or a skill is missing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def claude(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["claude", *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300
    )


def report(step: str, result: subprocess.CompletedProcess) -> None:
    print(f"error: {step} failed (exit {result.returncode})")
    for stream in (result.stdout, result.stderr):
        if stream.strip():
            print(stream.rstrip())


def main() -> int:
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    marketplace_name = marketplace["name"]
    failures = 0

    with tempfile.TemporaryDirectory(prefix="claude-config-") as config_dir:
        env = dict(os.environ, CLAUDE_CONFIG_DIR=config_dir)

        added = claude(["plugin", "marketplace", "add", str(ROOT)], env)
        if added.returncode != 0:
            report(f"claude plugin marketplace add {ROOT}", added)
            return 1
        print(f"added marketplace {marketplace_name}")

        for entry in marketplace["plugins"]:
            name = entry["name"]
            plugin_id = f"{name}@{marketplace_name}"
            skills_dir = (ROOT / entry["source"]).resolve() / "skills"
            skills = sorted(d.name for d in skills_dir.iterdir() if d.is_dir()) if skills_dir.is_dir() else []

            installed = claude(["plugin", "install", plugin_id], env)
            if installed.returncode != 0:
                report(f"claude plugin install {plugin_id}", installed)
                failures += 1
                continue

            details = claude(["plugin", "details", name], env)
            if details.returncode != 0:
                report(f"claude plugin details {name}", details)
                failures += 1
                continue

            missing = [skill for skill in skills if skill not in details.stdout]
            if missing:
                print(f"error: {plugin_id} installed, but these skills are missing from its "
                      f"details: {', '.join(missing)}")
                print(details.stdout.rstrip())
                failures += 1
            else:
                print(f"OK: {plugin_id} installed with skills {', '.join(skills)}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
