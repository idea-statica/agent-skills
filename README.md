# IDEA StatiCa agent skills

Skills that teach AI agents such as Claude to automate [IDEA StatiCa](https://www.ideastatica.com)
products through their APIs. With the `connection-api` skill, you describe what you want in
plain words, for example "open my project, calculate all connections and list the failing
checks", and Claude writes and runs the script for you.

https://github.com/user-attachments/assets/e180277a-87bf-4cdf-b79b-380e3e823158

*Claude writes and runs the script; IDEA StatiCa builds the model, calculates it and reports
the checks, and a recalculation in the desktop application gives the same numbers. The video
is sped up; it was recorded with IDEA StatiCa 26.1.*

| Skill | Call it as | What it does | Written for |
|---|---|---|---|
| `connection-api` | `/ideastatica:connection-api` | Scripts (Python, C#, any language) that open, build, change, calculate and report on IDEA StatiCa Connection projects (`.ideaCon`) | IDEA StatiCa 26.1 |

## IDEA StatiCa calculates, Claude orchestrates

Claude writes and runs the script that calls the API. Every change to the model, every
calculation and every check result comes from IDEA StatiCa itself: the API runs the same CBFEM
solver as the IDEA StatiCa Connection desktop application, whose
[verification and validation](https://www.ideastatica.com/support-center/cbfem-how-it-works-code-compliance-validation-and-verification)
has been carried out together with universities. Claude does not calculate or check the
connection; it passes on what IDEA StatiCa reports, and every project it saves opens in the
desktop application.

**The names in one sentence:** you add this repository, `idea-statica/agent-skills`, as a
plugin marketplace, which Claude then calls `ideastatica-skills`; the plugin in it is
`ideastatica` (shown as *IDEA StatiCa*), and it holds the skills. Skills for further IDEA
StatiCa APIs will arrive in the same plugin with its updates.

## What you need

- **Windows with IDEA StatiCa 26.1** installed. The skill is written for 26.1. On another
  version it makes Claude read the service's version and the service's own API description
  before relying on version-specific details.
- **A license that includes the API you automate.** For example, the Connection API needs a
  Steel, Complete or Enterprise license, and the concrete APIs will need a license that
  includes Concrete. Trial and Educational licenses also work, but their terms do not allow
  commercial use. Basic licenses cannot use the APIs.
- **Claude Code** ([install](https://code.claude.com/docs/en/setup)) in the terminal, VS Code,
  JetBrains or the Code tab of Claude Desktop. It runs scripts on your computer, where the
  service runs. In a chat on claude.ai or in the Claude apps, Claude can write the scripts but
  cannot run them against the service, because code there runs in a cloud sandbox; run them
  yourself.

## 1. Start the Connection REST API service

The service comes with IDEA StatiCa; you do not install anything extra.

1. Open the IDEA StatiCa installation folder. By default it is
   `C:\Program Files\IDEA StatiCa\StatiCa <version>`, for example `StatiCa 26.1`; if you chose
   another folder in the installer, look there. With several versions installed side by side,
   use the one you work with.
2. Run `IdeaStatiCa.ConnectionRestApi.exe` from that folder, by double-clicking it or from a
   terminal. Keep it running while you work. Like the desktop application, it takes a license
   seat while it runs.
3. Check it: open <http://localhost:5000> in a browser. The service's API description (Swagger)
   appears.

Port 5000 is the default. If it is taken, start the service on another one, for example
`IdeaStatiCa.ConnectionRestApi.exe -port=5001`, and tell Claude: "the service runs on
http://localhost:5001".

## 2. Install the plugin

### Claude Code

Type these two commands at the Claude Code prompt, where you write your requests to Claude:

```
/plugin marketplace add idea-statica/agent-skills
/plugin install ideastatica@ideastatica-skills
```

Or run the same from a terminal such as PowerShell:

```
claude plugin marketplace add idea-statica/agent-skills
claude plugin install ideastatica@ideastatica-skills
```

To receive updates automatically, open `/plugin`, go to **Marketplaces**, select
`ideastatica-skills` and turn on auto-update. Without it, update from a terminal with
`claude plugin update ideastatica@ideastatica-skills`.

### claude.ai and the Claude apps

1. Open **Customize > Plugins** and select **Add > Add marketplace**.
2. Enter `idea-statica/agent-skills`.
3. Turn on **Sync automatically** so that updates arrive by themselves.
4. Add the **IDEA StatiCa** plugin.

A plugin added there also loads in Claude Code when you sign in with the same account.

### Other agents (GitHub Copilot, Cursor, Codex and others)

In a terminal, with [Node.js](https://nodejs.org) installed:

```
npx skills add idea-statica/agent-skills
```

The skill is then called `connection-api`, without the `ideastatica:` prefix. Update later with
`npx skills update`.

### Manual installation

Each [release](https://github.com/idea-statica/agent-skills/releases) carries two ZIP files:

- `ideastatica-<version>.zip`, the whole plugin, for **Customize > Plugins > Add > Upload
  plugin** on claude.ai;
- `ideastatica-connection-api-<version>.zip`, the skill alone, for **Customize > Skills** on
  claude.ai, or to unzip into your agent's skills folder, for example `~/.claude/skills/` for
  Claude Code.

A manually installed plugin or skill does not update itself.

## 3. Check that it works

1. In Claude Code, `/plugin` lists **ideastatica** as installed, and typing `/ideastatica:`
   offers `connection-api`.
2. Ask Claude: *"Is the IDEA StatiCa Connection REST API service running? Tell me its
   version."* Claude answers with the service version, for example `26.1.1.2809`.

For a complete test with a sample project, see [TESTING.md](TESTING.md).

## 4. What to ask first

Name IDEA StatiCa Connection in your request, or start it with `/ideastatica:connection-api`,
so Claude picks the skill. For example:

- *"Write a Python script that opens C:\Projects\frame.ideaCon, calculates every connection and
  prints which checks fail."*
- *"Create a new IDEA StatiCa Connection project with an HEB300 column and an IPE300 beam
  bolted to its flange through an end plate, calculate it and save it as test.ideaCon."*
- *"Save the PDF report of every connection in frame.ideaCon into a reports folder."*
- *"List the design parameters of connection CON1 in frame.ideaCon, set the end plate thickness
  to 20 mm and recalculate."*

### What it can change in an existing project

Everything Claude builds through the API can be changed, and so can load effects, project
settings and the design parameters defined in the desktop application. Operations created in
the desktop application are not all editable: composite ones, such as an end plate or base
plate assembly, are read-only through the API. To change them, use design parameters, or have
Claude build the same design from basic operations: the same plates, cuts, welds and bolts, but
as separate operations instead of one composite operation.

## Watch the model in IDEA StatiCa Connection

When Claude builds or changes a model on your computer, it asks once whether you want to watch
the changes in IDEA StatiCa Connection. If you say yes, Claude opens a Connection window from
the same installation as the service and updates it after each change. The window opens either
side by side with the window you work in, taking the right 60 % of the screen, or on its own.
Claude does not click in that window: it changes the model through the API, saves it, and the
window reopens the saved file, which takes a few seconds.

- Claude can remember your answer and stop asking. To change it later, say for example
  *"always open the live view"*, *"don't offer the live view any more"* or *"ask me about the
  live view again"*.
- If you close the window, Claude stops updating it and opens it again only when you ask, for
  example *"show it in Connection"*.
- The window shows a preview copy, so saving in it never changes your project file. Before an
  update would replace edits you made in the window, Claude asks whether to continue from them.
- In that window, File > Open and New are disabled. Like any Connection window, it uses your
  license while it is open. The live view needs Python with the package `grpcio`
  (`pip install grpcio`).

## How updates reach you

| Where you installed from | Updates |
|---|---|
| Claude Code, this marketplace | Automatic after you turn on auto-update for the marketplace; otherwise `claude plugin update` |
| claude.ai and the Claude apps | Automatic with **Sync automatically** on; otherwise **Check for updates** |
| `npx skills` | `npx skills update` |
| ZIP from a release | Download the new release |

## Troubleshooting

| What you see | What to do |
|---|---|
| Connection refused, or nothing answers at `http://localhost:5000` | Start the service (step 1) and keep it running |
| Port 5000 is taken by another program | Start the service with `-port=5001` and tell Claude the address |
| The service closes at once with *"This API is disabled for Basic license type"* | Your license does not include the API. For example, the Connection API needs a Steel, Complete or Enterprise license (or Trial or Educational) |
| The service does not start at all | See *Troubleshooting* in the [Connection API getting started guide](https://developer.ideastatica.com/docs/api/connection-api/connection_api_getting_started.html) |
| *"blocked by enterprise policy"* when you add the marketplace in Claude Code | Your organization allows only approved marketplaces; ask your Claude administrator to allow `idea-statica/agent-skills` |
| Claude answers without using the skill | Mention IDEA StatiCa Connection in the request, or start it with `/ideastatica:connection-api` |

## Privacy and data

The plugin itself sends nothing anywhere. It contains instructions, reference pages, example
code and one helper script, with no hooks, no MCP servers and no programs that run on their
own. Its example code talks only to the IDEA StatiCa service on your own computer. The live view
helper runs only when Claude starts it. It asks the service on your computer for its version,
starts and talks to the Connection application there, reads that application's log files and
keeps your answer to the live view question, the window it started and the preview copies in
`%LOCALAPPDATA%\IDEA StatiCa agent skills`. The Connection window it starts stays open until
you close it. What Claude reads while it works, such as your
requests, model data and script output, is part of your Claude conversation and is handled
under the terms of your Claude plan.

## More about the APIs

- [IDEA StatiCa developer documentation](https://developer.ideastatica.com/), including the
  [Connection API getting started guide](https://developer.ideastatica.com/docs/api/connection-api/connection_api_getting_started.html)
  and the official Python and C# clients.
- [Developer forum](https://github.com/idea-statica/ideastatica-public/discussions) for
  questions about the APIs themselves.

## Support

Report problems with the skills and suggestions as
[GitHub issues](https://github.com/idea-statica/agent-skills/issues). Report security
vulnerabilities privately instead, as [SECURITY.md](SECURITY.md) describes. Maintainers: see
[MAINTAINING.md](MAINTAINING.md).

## License

MIT, see [LICENSE](LICENSE).
