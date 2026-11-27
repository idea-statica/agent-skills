# Live view in the Connection desktop application

The user can watch the model you build or change in an IDEA StatiCa Connection window, which
updates after each of your runs. `scripts/live_view.py` in this skill's folder opens that window
and shows files in it. It is optional: offer it, never force it, and never bring back a window
the user closed.

## What the user gets, and what not

- **A viewer of the saved file, not of the service project.** The desktop application cannot
  patch an open model. Each update copies the `.ideaCon` you saved to a preview copy in
  `%LOCALAPPDATA%\IDEA StatiCa agent skills\live-view\` and reopens that copy: 5 to 16 s. The
  window shows the last update, not every request.
- **Saving in the window writes to the preview copy**, never to your file or the user's
  project. Before an update would replace edits made in the window, saved or not, the helper
  stops (exit 4) and you ask the user.
- **One window, from the same installation as the service.** `start` launches
  `IdeaConnection.exe` from the installation folder whose `IdeaStatiCa.ConnectionRestApi.exe`
  has the version the service at `--service` reports; an older desktop refuses a file that a
  newer service wrote. A Connection window the user opened from the Start menu cannot be driven:
  `start` opens a second one and leaves the user's own window alone.
- **In that window, File > Open and File > New are disabled** (automation mode).
- **After every update the window comes to the front for a moment**; when it takes the keyboard,
  the helper gives it back to the window the user was in. A window the user minimized is updated
  but stays minimized.
- **Side by side moves two windows only:** Connection, and the window the agent runs in (VS Code,
  the terminal, Claude Desktop), found through the helper's parent processes. Never another
  application's window.
- Like any Connection window, it uses the user's IDEA StatiCa license while it is open.

## When it applies, then what the remembered choice says

**First, is the live view relevant at all?** Only when all of these hold:

1. You run commands on the user's Windows computer, where the service runs (Claude Code in the
   terminal, VS Code, JetBrains or the Code tab of Claude Desktop). Not in a cloud sandbox.
2. The model is what the user will look at: you build or change a project for them now (a new
   project, members, plates, bolts, cuts, load effects, a design parameter). Not when the script
   is the product (a script to run later, batch reports, reading results only).

**Then** run `live_view.py status`. When `"window"` is `"open"`, just keep it updated. Otherwise
follow `"preference"."mode"`, once per conversation, just before the first run that changes the
model:

| `mode` | what you do |
|---|---|
| `ask` | ask (below). After a "no", do not ask again in this conversation |
| `always` | `start --auto` without asking, and say one line: *"Opening the live view in IDEA StatiCa Connection, as you asked me to remember."* Exit 3 means the user closed the window earlier in this session: say nothing and do not open it |
| `never` | do not offer or mention it |

An explicit request (*"show it in Connection"*, *"ukaž mi to v aplikaci"*) starts it in every
mode: plain `start`, without `--auto`, then `show` the latest file you saved.

## The question

Ask in the user's language. Use your agent's question tool where it has one (Claude Code:
AskUserQuestion), so the user answers with one click; otherwise ask in plain text and wait for
the answer. Ask both questions together:

1. *"Do you want to watch the changes in IDEA StatiCa Connection while I work? The window uses
   your IDEA StatiCa license while it is open."*
   - **Yes, side by side (recommended)**: Connection takes the right 60 % of this screen, and the
     window we talk in moves to the left 40 %.
   - **Yes, in its own window**: no window is moved; place it where you like, for example on a
     second monitor.
   - **No**: I work through the API only; ask for the live view whenever you want it.
2. *"Remember this choice?"*
   - **Ask me next time**
   - **Remember it**: I will not ask again; you can change it at any time by telling me.

| answer | commands |
|---|---|
| yes, remembered | `remember always --layout side-by-side` (or `window`), then `start` |
| yes, not remembered | `start --layout side-by-side` (or `window`) |
| no, remembered | `remember never` |
| no, not remembered | nothing |
| a plain "yes" in text | side by side, not remembered |
| anything else | ask once more what they want |

## What the user may say later

| the user says, for example | command |
|---|---|
| "show it in Connection", "open the live view" | `start`, then `show` the latest file |
| "always open the live view" | `remember always`, and `start` if the window is not open |
| "don't offer the live view any more" | `remember never` (the open window stays; close it with `stop` only if they also ask) |
| "ask me about the live view again" | `remember ask` |
| "close the Connection window" | `stop` |
| "put the windows side by side again" | `arrange` |

## Running it

Call the helper by its absolute path in this skill's folder and quote every path: Git Bash drops
unquoted backslashes. Pass the base URL you use for the API:

```
python "<skill folder>/scripts/live_view.py" start --service http://localhost:5000 --layout side-by-side
python "<skill folder>/scripts/live_view.py" show "C:\path\to\model.ideaCon"
```

- `start` waits up to 100 s, inside the 120 s that agent shells usually allow a command. A cold
  start takes 10 to 60 s, so tell the user once that Connection is starting. If it reports that
  the window is still starting, run `start` again: it takes over that window instead of opening a
  second one. `start` places the windows for `side-by-side`, but not on a monitor narrower than
  1600 px at its display scaling; tell the user when it says so, and also when it falls back to
  the newest installation because no service answered.
- **Which file to show.** While the live view is on, after every run that changed the model,
  save the project (`GET .../projects/{projectId}/download`) and `show` that file. Save to the
  output path the user named. Without one, save to a working file of your own, never over the
  file the user gave you as input. A script that closes the project must download it before
  `close`. Update once per request, not after every API call.
- `show` never opens a window; only `start` does. Read its exit code:

| exit | meaning | what you do |
|---|---|---|
| 0 | shown | nothing to say |
| 3 | the user closed the window | say once: *"The Connection window is closed, so I am no longer updating it. Say "show it in Connection" when you want it back."* Do not run `start` again until the user asks. Do not change the remembered choice: closing the window is not "never" |
| 4 | the window holds edits that the update would replace: not saved yet, or saved into the preview copy | ask the user whether to continue from their edits or replace them. Continue: they save in the window if not saved yet, and you open the preview copy the message names (`POST /api/5/projects/open`) before your next change. Replace: `show --replace-edited` |
| 5 | the live view is not on | say nothing; it was never started, the user stopped it, or it is still starting (`start` first) |
| 6 | sent, but the window did not confirm the open | usually it opened anyway; a dialog may wait in the window. Mention it only if the user says the window did not change |
| 1 | error | report the message; the live view is optional, so carry on with the API work |

- **When the work is done, leave the window open** and mention once that it stays open and uses
  the license until the user closes it. Run `stop` only when the user asks.

## Troubleshooting

| what you see | cause and fix |
|---|---|
| `The live view needs the Python package grpcio` | ask the user, then `pip install grpcio` for the Python that runs the helper; `status` reports `"grpcio"` |
| `start`: no installation has the service's version | the service runs from a folder outside `C:\Program Files\IDEA StatiCa`; `start --install "<that folder>"` |
| `start`: still starting after 100 s | a license or first-run dialog waits in the Connection window; the user answers it, then `start` again |
| `start`: `IdeaConnection.exe exited during start-up` | the installation is damaged or the license is refused; ask the user to open Connection from the Start menu once and read its message |
| `stop` fails | the window does not answer yet; `start` (it takes the window over), then `stop` |

The helper keeps the remembered choice, the window it started (process id, port, executable,
the shown file) and the preview copies in `%LOCALAPPDATA%\IDEA StatiCa agent skills`. Deleting
the folder brings the question back.

## How it works

`IdeaConnection.exe -cmd:automation-<id> -grpcPort:<port> user-mode 0` starts the application
as a gRPC server on `localhost:<port>`; it signals the named event `IdeaStatiCaEvent<id>` when
ready. The helper calls the application's automation methods (`OpenProjectAsync`,
`GetIsEdited`, `Shutdown`) by reflection over `/GrpcService/ConnectAsync`, the channel that
IDEA StatiCa Checkbot uses; the contract is `IdeaStatiCa.Plugin` in
[ideastatica-public](https://github.com/idea-statica/ideastatica-public). It is not a documented
API of its own: if a later version changes it, the live view stops working while the REST API
work goes on. `OpenProjectAsync` returns before the open finishes; the helper waits for the
application's log line `... runs in command mode` in `%TEMP%\IdeaStatica\Logs\IdeaConnection*.log`.
`start --auto` remembers which agent process started the window, so a window the user closed is
not reopened in the same agent session, also after /clear or context compaction.
