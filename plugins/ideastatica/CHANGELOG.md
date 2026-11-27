# Changelog

All notable changes to the `ideastatica` plugin. Versions follow
[Semantic Versioning](https://semver.org/); see `MAINTAINING.md` at the repository root for
what each part of the version means here.

## 1.1.0 - 2026-11-27

- `connection-api`: live view in the IDEA StatiCa Connection desktop application. When the
  agent builds or changes a model on the user's Windows computer, it asks once whether the user
  wants to watch the changes in a Connection window, side by side with the window they work in
  or on its own, and whether to remember the answer. The window reopens a preview copy of each
  saved version of the model, so saving in the window never changes the project file. When the
  user closes the window, the agent does not open it again until asked, also with the answer
  remembered, and it does not replace edits made in the window without asking. When the user
  changes the model in the window, the agent continues from those changes with the next request
  and says so; results calculated in the window are not carried over. New helper `scripts/live_view.py` and reference page
  `reference/live-view.md`.
- `connection-api`: after opening a project, the agent checks which operations the API can only
  read, typically composite operations created in the desktop application such as an end plate,
  and tells the user before changing anything. New script `scripts/check_operations.py`.

## 1.0.1 - 2026-11-24

- `connection-api`: the agent never restarts or stops a Connection REST API service the user
  started. When it started the service itself, with the user's consent, it stops it again
  when the work is done, because a running service holds a license seat.

## 1.0.0 - 2026-11-24

- First public release, with the `connection-api` skill written for the Connection REST API
  service 26.1.1 (`/api/5`).
