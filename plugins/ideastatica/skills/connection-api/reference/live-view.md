# Live view in the Connection desktop application

The user can watch the model you build or change in an IDEA StatiCa Connection window, which
updates after each of your runs. `scripts/live_view.py` opens that window and shows files in
it. It is optional: offer it, never force it, and never bring back a window the user closed.

## What the user gets, and what not

- **A viewer of the saved file, not of the service project.** The desktop application cannot
  patch an open model. Each update reopens the whole `.ideaCon` you just saved: 3 to 8 s, and
  the first open after the start takes longer. The window shows the last update, not every
  request.
- **One window, from the same installation as the service.** `start` launches
  `IdeaConnection.exe` from the installation folder whose `IdeaStatiCa.ConnectionRestApi.exe`
  has the version that the running service reports. An older desktop refuses a file that a
  newer service wrote. A Connection window that the user opened from the Start menu cannot be
  driven: `start` opens a second one, and the user's own window is left alone.
- **In that window, File > Open and File > New are disabled** (automation mode). Save writes to
  the file that was shown last.
- **After every update, the window comes to the front for a moment.** The helper then gives the
  keyboard back to the window the user was in. It does not stay on top. A window the user
  minimized is updated but stays minimized.
- **Side by side moves only two windows:** the Connection window, and the window the agent runs
  in (VS Code, the terminal, Claude Desktop), found through the helper's parent processes. It
  never moves the window of another application the user switched to while you work.
- Like any Connection window, it uses the user's IDEA StatiCa license while it is open.

## When to offer it

Offer it only when all of these hold:

1. You run commands on the user's Windows computer, where the service runs (Claude Code in the
   terminal, VS Code, JetBrains or the Code tab of Claude Desktop). In a cloud sandbox,
   do not offer it.
2. The request builds or changes a model that the user will look at: a new project, members,
   plates, bolts, cuts, load effects, a design parameter. Do not offer it for a script the
   user asked to write and run later, for batch reports, or for reading results only.
3. `python scripts/live_view.py status` reports `"window"` other than `"open"`.
4. The remembered choice (`"preference"."mode"` in the same output) is `ask`.

Ask once per conversation, just before the first run that changes the model, not at the
start of the conversation. If the user declines, do not ask again in this conversation.

| remembered `mode` | what you do |
|---|---|
| `ask` | ask (below) |
| `always` | `start` without asking, and say one line: *"Opening the live view in IDEA StatiCa Connection, as you chose to remember. Say "stop the live view" to change that."* |
| `never` | do not offer or mention it |

Whatever is remembered, an explicit request (*"show it in Connection"*, *"ukaž mi to v
aplikaci"*) starts the live view.

## The question

Ask in the user's language. Use your agent's question tool where it has one (Claude Code:
AskUserQuestion), so the user answers with one click; otherwise ask in plain text and wait for
the answer. Ask both questions together, in one dialog:

1. *"Do you want to watch the changes in IDEA StatiCa Connection while I work?"*
   - **Yes, side by side (recommended)**: Connection takes the right 60 % of this screen, and
     the window we talk in moves to the left 40 %.
   - **Yes, in its own window**: no window is moved; place it where you like, for example on a
     second monitor.
   - **No**: I work through the API only; ask for the live view whenever you want it.
2. *"Remember this choice?"*
   - **Ask me next time**
   - **Remember it**: I will not ask again; say "start the live view" or "stop the live view"
     to change it.

Then:

| answer | commands |
|---|---|
| yes, remembered | `live_view.py remember always --layout side-by-side` (or `window`), then `start` |
| yes, not remembered | `live_view.py start --layout side-by-side` (or `window`) |
| no, remembered | `live_view.py remember never` |
| no, not remembered | nothing |

When the user later says to stop or start the live view for good, run `remember never` or
`remember always`. `remember ask` brings the question back.

## Running it

```
python scripts/live_view.py start --service http://localhost:5000 --layout side-by-side
python scripts/live_view.py show C:\path\to\model.ideaCon
```

- Run `start` before the first script that changes the model. A cold start takes 30 to 60 s,
  so tell the user once that Connection is starting. `start` places the windows when the
  layout is `side-by-side`, but not on a monitor narrower than 1600 px; tell the user when it
  says so.
- After every run that changed the model, save it (`GET .../projects/{projectId}/download`) to
  the `.ideaCon` you work on, then `show` that file. Update once per request, not after every
  API call.
- `show` never opens a window; only `start` does. Read its exit code:

| exit | meaning | what you do |
|---|---|---|
| 0 | shown | nothing to say |
| 3 | no window: the user closed it, or it was never started | say once: *"The Connection window is closed, so I am no longer updating it. Say "show it in Connection" when you want it back."* Do not run `start` again until the user asks, and do not change the remembered choice: closing the window is not "never". |
| 4 | the window holds edits that the user has not saved | ask the user: save them in the window first, or replace them. Replace only after they agree: `show --replace-edited` (the window then still asks whether to save) |
| 1 | error | report the message; the live view is optional, so carry on with the API work |

- **Edits made in the window.** The window is a viewer: what the user changes there does not
  reach the project open in the service. When the user says they changed and saved something
  in the window, reopen that file in the service (`POST /api/5/projects/open`) before your next
  change; otherwise your next update replaces their edits.
- When the user asks to put the windows side by side again (they moved or maximized one), run
  `live_view.py arrange`. Never rearrange windows without being asked.
- **Leave the window open when the work is done.** The user closes it. Run `stop` only when the
  user asks you to close it.

## Troubleshooting

| what you see | cause and fix |
|---|---|
| `start`: no installation has the service's version | the service runs from a folder outside `C:\Program Files\IDEA StatiCa`; `start --install <that folder>` |
| `start`: did not report ready within 240 s | a license or first-run dialog waits in the Connection window; the user answers it, then `start` again |
| `start`: `IdeaConnection.exe exited during start-up` | the installation is damaged or the license is refused; ask the user to open Connection from the Start menu once and read its message |
| `show`: did not confirm the open | a dialog waits in the window (often whether to save edits); usually the file opened anyway |
| `the live view needs the grpcio package` | `pip install grpcio` in the Python that runs the helper |

The helper stores the remembered choice and the window it started in
`%LOCALAPPDATA%\IDEA StatiCa agent skills\connection-live-view.json`. Deleting the file brings
the question back.

## How it works

`IdeaConnection.exe -cmd:automation-<id> -grpcPort:<port> user-mode 0` starts the application
as a gRPC server on `localhost:<port>`; it signals the named event `IdeaStatiCaEvent<id>` when
ready. The helper calls the application's automation methods (`OpenProjectAsync`,
`GetIsEdited`, `Shutdown`) by reflection over `/GrpcService/ConnectAsync`, the channel that
IDEA StatiCa Checkbot uses; the contract is `IdeaStatiCa.Plugin` in
[ideastatica-public](https://github.com/idea-statica/ideastatica-public). It is not a
documented API of its own: if a later version changes it, the live view stops working while
the REST API work goes on. `OpenProjectAsync` returns before the open finishes; the helper
waits for the application's log line `... runs in command mode` in
`%TEMP%\IdeaStatica\Logs\IdeaConnection*.log`.
