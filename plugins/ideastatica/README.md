# IDEA StatiCa

Skills that teach your AI agent to automate IDEA StatiCa products through their APIs. You
describe the task in plain words; the agent picks the matching skill, writes the script and,
in Claude Code, runs it. You can also call a skill by name.

| Skill | Call it as | What it does | Written for |
|---|---|---|---|
| `connection-api` | `/ideastatica:connection-api` | Scripts (Python, C#, any language) that open, build, change, calculate and report on IDEA StatiCa Connection projects (`.ideaCon`) | IDEA StatiCa 26.1 |

Skills for further IDEA StatiCa APIs arrive with plugin updates; you do not install anything
again.

The agent only orchestrates. Every calculation and every check result comes from IDEA StatiCa
itself, from the same CBFEM solver as the desktop application, whose
[verification and validation](https://www.ideastatica.com/support-center/cbfem-how-it-works-code-compliance-validation-and-verification)
has been carried out together with universities. The agent passes on what IDEA StatiCa reports;
it does not calculate or check the connection itself.

## Before you start

- **Windows with IDEA StatiCa 26.1** and a license that includes the API: for `connection-api`,
  Steel, Complete or Enterprise (Trial and Educational licenses also work, but not for
  commercial use).
- **The Connection REST API service running**: start `IdeaStatiCa.ConnectionRestApi.exe` from
  the installation folder, by default `C:\Program Files\IDEA StatiCa\StatiCa <version>`, and
  check that <http://localhost:5000> shows its API description.
- **Claude Code**, so that scripts run on the computer where the service runs. In a chat on
  claude.ai or in the Claude apps, Claude can write the scripts but not run them against the
  service.

The [repository README](https://github.com/idea-statica/agent-skills#readme) walks through each
step, including other ports, other agents and troubleshooting.

## Install

Type these two commands at the Claude Code prompt, where you write your requests:

```
/plugin marketplace add idea-statica/agent-skills
/plugin install ideastatica@ideastatica-skills
```

For claude.ai, the Claude apps and other agents, see the
[repository README](https://github.com/idea-statica/agent-skills#2-install-the-plugin).

## `connection-api`

Teaches your agent to automate **IDEA StatiCa Connection** through its REST API: open or create
a connection project, model members, plates, welds, bolt and anchor grids, cuts and other
operations, define load effects and design parameters, run the CBFEM calculation, and read the
check results, PDF reports and the updated `.ideaCon` file.

Try for example:

- *"Write a Python script that opens C:\Projects\frame.ideaCon, calculates every connection and
  prints which checks fail."*
- *"Save the PDF report of every connection in frame.ideaCon into a reports folder."*

When the agent builds or changes a model on your computer, it offers once to show the changes
in an IDEA StatiCa Connection window, side by side with the window you work in or on its own,
and can remember your answer. If you close that window, the agent does not open it again until
you ask. The window reopens a preview copy of each saved version, so saving in it never changes
your project file; before an update would replace edits you made there, the agent asks.

Composite operations created in the desktop application, such as an end plate or base plate
assembly, are read-only through the API. Change them through design parameters, or have the
agent build the same design from basic operations: the same plates, cuts, welds and bolts, but
as separate operations instead of one composite operation.

What is inside `skills/connection-api/`:

- `SKILL.md`: the workflow, the rules that prevent the most common failures, and pointers to
  the reference pages.
- `reference/`: one page per area (endpoints, request and response shapes, members, plates,
  welds, cuts, grids, operations, parameters, cross-sections, raw results, diagnostics, live
  view).
- `examples/`: runnable Python and C# examples (quickstart, asynchronous calculation, load
  effects, parameters, detailed and raw results, batch reports, typed operations).
- `scripts/live_view.py`: the helper the agent runs for the live view in the desktop
  application (Windows, Python with `grpcio`).

## Compatibility

| Plugin version | Skill | IDEA StatiCa | Service build checked | API |
|---|---|---|---|---|
| 1.1.0 | `connection-api` | 26.1 | 26.1.1.2809 | `/api/5` |
| 1.0.1 | `connection-api` | 26.1 | 26.1.1.2809 | `/api/5` |
| 1.0.0 | `connection-api` | 26.1 | 26.1.1.2809 | `/api/5` |

## Privacy and data

The plugin itself sends nothing anywhere. It contains instructions, reference pages, example
code and one helper script, with no hooks, no MCP servers and no programs that run on their
own. Its example code talks only to the IDEA StatiCa service on your own computer. The live
view helper runs only when the agent starts it. It asks the service on your computer for its
version, starts and talks to the Connection application there, reads that application's log
files and keeps your answer to the live view question, the window it started and the preview
copies in `%LOCALAPPDATA%\IDEA StatiCa agent skills`. The Connection window it starts stays open
until you close it. What the agent reads while it
works, such as your requests, model data and script output, is part of your conversation with
it and is handled under the terms of your plan with its provider.

## Support

Report problems and suggestions as
[GitHub issues](https://github.com/idea-statica/agent-skills/issues). For questions about the
APIs themselves, see the [IDEA StatiCa developer documentation](https://developer.ideastatica.com/).

## License

MIT, see [LICENSE](LICENSE).
