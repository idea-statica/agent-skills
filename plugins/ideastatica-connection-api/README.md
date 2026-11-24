# IDEA StatiCa Connection API

Teaches your AI coding agent to write and debug code that drives the
**IDEA StatiCa Connection REST API** over HTTP: open or create a connection project, model
members, plates, welds, bolt and anchor grids, cuts and other operations, define load
effects, run the CBFEM calculation synchronously or as a background job, and read the
results, reports and the updated `.ideaCon` file.

The plugin contains one skill, `rest-api`. Your agent loads it on its own when a task mentions
the Connection REST API, or you can call it by name: `/ideastatica-connection-api:rest-api`.

## Install

In Claude Code:

```
/plugin install ideastatica-connection-api --marketplace idea-statica/agent-skills
```

For claude.ai, Claude Desktop, Cowork and other agents, see the
[repository README](https://github.com/idea-statica/agent-skills#install).

## What is inside

- `skills/rest-api/SKILL.md`: the workflow, the rules that prevent the
  most common failures, and pointers to the reference pages.
- `reference/`: one page per area (endpoints, request and response shapes, members, plates,
  welds, cuts, grids, operations, parameters, cross-sections, raw results, diagnostics).
- `examples/`: runnable Python and C# examples (quickstart, asynchronous calculation, load
  effects, parameters, detailed and raw results, batch reports, typed operations).

## Requirements

- The IDEA StatiCa Connection REST API service running on your computer. The skill assumes
  the default address `http://localhost:5000` and the `/api/5` routes.
- A valid IDEA StatiCa license to run calculations.
- An agent that can run code on the same computer as the service, such as Claude Code or
  Cowork in Claude Desktop. In claude.ai chat, code runs in a cloud sandbox that cannot reach
  a service on your computer; the skill still helps you write the code there.

## Compatibility

| Plugin version | Connection REST API service | Routes |
|---|---|---|
| 1.0.0 | 26.1.1 | `/api/5` |

The service's own Swagger (`/index.html` on the running service) is the source of truth.
Where it and the skill disagree, the skill tells the agent to follow the Swagger.

## Privacy and data

The plugin contains instructions, reference pages and example code only. It has no hooks, no
MCP servers and no programs that run on their own. The example code talks only to the
Connection REST API service on your own computer. The plugin sends nothing to IDEA StatiCa or
to anyone else.

## Support

Report problems and suggestions as
[GitHub issues](https://github.com/idea-statica/agent-skills/issues).

## License

MIT, see [LICENSE](LICENSE).
