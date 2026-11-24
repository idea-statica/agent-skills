# IDEA StatiCa agent skills

Agent skills and Claude plugins from [IDEA StatiCa](https://www.ideastatica.com) that teach AI
agents to automate IDEA StatiCa products through their APIs.

All skills ship in one plugin, [`ideastatica`](plugins/ideastatica). Install it once; skills
for further IDEA StatiCa APIs arrive with its updates.

| Skill | Call it as | What it does | Works with |
|---|---|---|---|
| `connection-api` | `/ideastatica:connection-api` | Write and debug code that drives the Connection REST API over HTTP | Connection REST API service 26.1.1, `/api/5` |

Each skill follows the open [Agent Skills](https://agentskills.io) format, so it works in
Claude and in other agents that read `SKILL.md` skills.

## Install

### Claude Code

Add the marketplace once, then install the plugin:

```
/plugin marketplace add idea-statica/agent-skills
/plugin install ideastatica@ideastatica-skills
```

To receive updates automatically, open `/plugin`, go to **Marketplaces**, select
`ideastatica-skills` and turn on auto-update. Without it, update with
`claude plugin update ideastatica@ideastatica-skills`.

### claude.ai, Claude Desktop and Cowork

1. Open **Customize > Plugins** and select **Add > Add marketplace**.
2. Enter `idea-statica/agent-skills`.
3. Turn on **Sync automatically** for the marketplace so updates arrive by themselves.
4. Add the **IDEA StatiCa** plugin.

A plugin added on claude.ai also loads in Claude Code when you sign in with the same account.

### Other agents (GitHub Copilot, Cursor, Codex and others)

With the [`skills`](https://github.com/vercel-labs/skills) command-line tool:

```
npx skills add idea-statica/agent-skills
```

Update later with `npx skills update`.

### Manual installation

Each [release](https://github.com/idea-statica/agent-skills/releases) carries a ZIP of every
skill. Upload it in **Customize > Skills** on claude.ai, or unzip it into the skills folder of
your agent, for example `~/.claude/skills/` for Claude Code. A manually installed skill does
not update itself.

## How updates reach you

| Where you installed from | Updates |
|---|---|
| Claude Code, this marketplace | Automatic after you turn on auto-update for the marketplace; otherwise `claude plugin update` |
| claude.ai, Claude Desktop, Cowork | Automatic with **Sync automatically** on; otherwise **Check for updates** |
| `npx skills` | `npx skills update` |
| ZIP from a release | Download the new release |

## Requirements

- The IDEA StatiCa product and service the skill is written for, running on your computer.
  For the Connection API that is the Connection REST API service; calculations need a valid
  IDEA StatiCa license.
- An agent that runs code on the same computer as the service, such as Claude Code or Cowork
  in Claude Desktop. In claude.ai chat, code runs in a cloud sandbox that cannot reach a
  service on your computer; the skill still helps you write the code there.

## Privacy and data

The plugins contain instructions, reference pages and example code only: no hooks, no MCP
servers and no programs that run on their own. Example code talks only to the IDEA StatiCa
service on your own computer. Nothing is sent to IDEA StatiCa or to anyone else.

## Support

Report problems and suggestions as
[GitHub issues](https://github.com/idea-statica/agent-skills/issues). Maintainers: see
[MAINTAINING.md](MAINTAINING.md).

## License

MIT, see [LICENSE](LICENSE).
