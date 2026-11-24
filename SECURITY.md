# Security policy

## Report a vulnerability privately

Do not report security problems as public GitHub issues. Report them privately on GitHub:
open the repository's **Security** tab and select **Report a vulnerability**, or go straight to
<https://github.com/idea-statica/agent-skills/security/advisories/new>. Only the maintainers
see the report.

Please include:

- the plugin, the skill and its version (from `plugin.json`, or the release you installed);
- what an agent or a person could be made to do, and what it puts at risk;
- the steps, the prompt or the file that shows it.

## What belongs here

Anything in this repository that could make an agent act against its user, for example:

- instructions in a skill, a reference page or an example that lead an agent to run unsafe
  commands, send data anywhere other than the IDEA StatiCa service on the user's own computer,
  or weaken its permission settings;
- example code that is unsafe to run as written;
- a credential or other secret committed to the repository;
- a weakness in the repository's GitHub workflows, for example one that lets someone change a
  release.

If you are not sure where a problem belongs, report it here anyway. A problem in an IDEA
StatiCa application or service, such as the Connection REST API service, is passed on to the
IDEA StatiCa team responsible for it. A problem in Claude or Claude Code itself belongs to
Anthropic: see its [Responsible Disclosure Policy](https://www.anthropic.com/responsible-disclosure-policy).

## Supported versions

Only the latest release of each plugin receives fixes. Installations with automatic updates on
receive a fix without further action; see *How updates reach you* in the [README](README.md).

## What happens next

- We confirm that we received your report within five working days.
- We investigate it and keep you informed while we work on it.
- We release the fix as a new plugin version and then publish a security advisory on GitHub,
  naming you as the reporter if you wish.
