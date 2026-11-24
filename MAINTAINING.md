# Maintaining this repository

This repository is a Claude plugin marketplace (`.claude-plugin/marketplace.json`, named
`ideastatica-skills`) and an Agent Skills catalog. Every push to `main` reaches users without
further action: Anthropic's directory, claude.ai marketplace sync and Claude Code auto-update
all read `main`.

## Rules

1. **`main` is what users get.** Change it only through a pull request with green checks.
2. **Document released behavior only.** A skill describes a publicly released service build.
   Draft and verify against unreleased builds internally, and open the pull request once that
   build is released.
3. **Never rename a plugin, a skill or the marketplace.** Users install by
   `<plugin>@ideastatica-skills`, and a rename breaks every install. To change what users see, set
   `displayName`. If a rename is unavoidable, add a `renames` entry to `marketplace.json`.
4. **Bump the version on every release.** Claude Code and claude.ai deliver a new copy only
   when the `version` in `plugin.json` changes. `scripts/check_repo.py --base` fails a pull
   request that changes a plugin without raising its version.
5. **Set `version` only in `plugin.json`**, never in the marketplace entry.

## Versioning

Each plugin has its own [semantic version](https://semver.org/), independent of the product
version. The compatibility table in the plugin's README maps plugin versions to service
versions.

| Part | Raise it when |
|---|---|
| MAJOR | A skill is removed or split, or the skill moves to a new API route version (for example `/api/6`) |
| MINOR | The skill covers a new service release, or gains a reference page or example |
| PATCH | Corrections and clarifications that keep the same service release |

## Release a new version

1. Update the skill under `plugins/<plugin>/skills/<skill>/`. Keep the service build it was
   checked against in the skill's "Service version" section.
2. Raise `version` in `plugins/<plugin>/.claude-plugin/plugin.json`.
3. Add a `## <version>` section at the top of `plugins/<plugin>/CHANGELOG.md`, and update the
   compatibility table in the plugin README if the service version changed.
4. Run the local checks (below), open a pull request and merge it once the checks pass.
5. Tag the release from an up-to-date `main`:

   ```
   claude plugin tag plugins/<plugin> --push
   ```

   This creates the tag `<plugin>--v<version>`. The `release` workflow then attaches ZIP files
   of the plugin and of each skill to a GitHub release, with the changelog section as notes.

Users then receive the release without further action from you: through Anthropic's directory
once the version is published there, through claude.ai marketplace sync, and in Claude Code
when auto-update is on.

## Local checks

```
pip install pyyaml
python scripts/check_repo.py
python scripts/check_repo.py --base origin/main
claude plugin validate --strict .
claude plugin validate --strict plugins/<plugin>
```

On Windows, run `git config core.autocrlf input` once in your clone so the working copy keeps
the LF line endings the repository uses.

`check_repo.py` checks the marketplace and plugin manifests, the Agent Skills rules for each
`SKILL.md` (name matches the folder, description at most 1,024 characters), the README word
count, the license, the changelog entry, file names, sizes and line endings, and with `--base`
the version bump. `claude plugin validate` checks what Claude Code itself loads.

To try a plugin in Claude Code before merging, add your working copy as a marketplace:

```
claude plugin marketplace add ./
claude plugin install <plugin>@ideastatica-skills
```

Remove it again with `claude plugin marketplace remove ideastatica-skills`. Where managed
settings allow only approved marketplace sources, use `claude --plugin-dir plugins/<plugin>`
instead, which loads the plugin for one session.

## Add a new plugin

1. Create `plugins/<plugin>/` with `.claude-plugin/plugin.json`, `README.md` (at least 40
   words outside code blocks), `LICENSE`, `CHANGELOG.md` and `skills/<skill>/SKILL.md`.
2. Add an entry to `.claude-plugin/marketplace.json` with the same `name` as `plugin.json`.
3. Add `./plugins/<plugin>/skills` to `paths` in `skills.sh.json`, so `npx skills` finds it.
4. Add a row to the table in the root README.
5. Submit the plugin folder to Anthropic's directory as a separate submission (below).

## Anthropic's directory (one-time setup per plugin)

The directory lists the plugin on claude.ai, in Cowork and in Claude Code, and delivers updates
automatically. Submitting needs a paid claude.ai plan; on Team and Enterprise plans, an
organization Owner submits, or on Enterprise a member whose role includes the Directory
permission. The GitHub account connected to claude.ai must be able to push to this repository.

1. Open the developer portal at <https://claude.ai/directory/manage>, select **Submit new** and
   then **Plugin bundle**.
2. Repository `idea-statica/agent-skills`, plugin path `plugins/<plugin>`, branch `main`.
3. Select **Validate** and fix every blocking finding.
4. Answer the data handling questions. For the current plugins: no personal data is read or
   stored, and no data is sent anywhere except to the IDEA StatiCa service on the user's own
   computer.
5. Keep **GitHub push webhook** selected and set it up after submitting (needs admin rights on
   the repository).

After the first version is published, merging to `main` is enough; the directory scans each new
commit and publishes it according to the plugin's publish setting.

## Repository settings (one-time)

- Branch protection on `main`: require a pull request and the `validate` check.
- Allow GitHub Actions to create releases (the `release` workflow uses `contents: write`).
