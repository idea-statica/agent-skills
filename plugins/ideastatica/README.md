# IDEA StatiCa

Skills that teach your AI agent to automate IDEA StatiCa products through their APIs. You
describe the task in plain words; the agent picks the matching skill, writes the script and,
in Claude Code, runs it. You can also call a skill by name.

| Skill | Call it as | What it does | Written for |
|---|---|---|---|
| `connection-api` | `/ideastatica:connection-api` | Scripts (Python, C#, any language) that open, build, change, calculate and report on IDEA StatiCa Connection projects (`.ideaCon`) | IDEA StatiCa 26.1 |

Skills for further IDEA StatiCa APIs arrive with plugin updates; you do not install anything
again.

## Before you start

- **Windows with IDEA StatiCa 26.1** and a Steel, Complete or Enterprise license (Trial and
  Educational licenses also work, but not for commercial use).
- **The Connection REST API service running**: start `IdeaStatiCa.ConnectionRestApi.exe` from
  the installation folder, by default `C:\Program Files\IDEA StatiCa\StatiCa <version>`, and
  check that <http://localhost:5000> shows its API description.
- **Claude Code**, so that scripts run on the computer where the service runs. In a chat on
  claude.ai or in the Claude apps, Claude can write the scripts but not run them against the
  service.

The [repository README](https://github.com/idea-statica/agent-skills#readme) walks through each
step, including other ports, other agents and troubleshooting.

## Install

Type these two commands in Claude Code:

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

Composite operations created in the desktop application, such as an end plate or base plate
assembly, are read-only through the API; change them through design parameters.

What is inside `skills/connection-api/`:

- `SKILL.md`: the workflow, the rules that prevent the most common failures, and pointers to
  the reference pages.
- `reference/`: one page per area (endpoints, request and response shapes, members, plates,
  welds, cuts, grids, operations, parameters, cross-sections, raw results, diagnostics).
- `examples/`: runnable Python and C# examples (quickstart, asynchronous calculation, load
  effects, parameters, detailed and raw results, batch reports, typed operations).

## Compatibility

| Plugin version | Skill | IDEA StatiCa | Service build checked | API |
|---|---|---|---|---|
| 1.0.0 | `connection-api` | 26.1 | 26.1.1.2809 | `/api/5` |

## Privacy and data

The plugin itself sends nothing anywhere. It contains instructions, reference pages and example
code only, with no hooks, no MCP servers and no programs that run on their own, and its example
code talks only to the IDEA StatiCa service on your own computer. What the agent reads while it
works, such as your requests, model data and script output, is part of your conversation with
it and is handled under the terms of your plan with its provider.

## Support

Report problems and suggestions as
[GitHub issues](https://github.com/idea-statica/agent-skills/issues). For questions about the
APIs themselves, see the [IDEA StatiCa developer documentation](https://developer.ideastatica.com/).

## License

MIT, see [LICENSE](LICENSE).
