# Changelog

All notable changes to the `ideastatica` plugin. Versions follow
[Semantic Versioning](https://semver.org/); see `MAINTAINING.md` at the repository root for
what each part of the version means here.

## 1.0.1 - 2026-11-24

- `connection-api`: the agent never restarts or stops a Connection REST API service the user
  started. When it started the service itself, with the user's consent, it stops it again
  when the work is done, because a running service holds a license seat.

## 1.0.0 - 2026-11-24

- First public release, with the `connection-api` skill written for the Connection REST API
  service 26.1.1 (`/api/5`).
