# Contributing to decimalai-claude-plugins

Thanks for your interest. This repo is a Claude Code plugin marketplace, which shapes everything
below: there is no build step and no test runner. The deliverable is **prompt text** in
`plugins/decimalai/commands/*.md`, the standard-library script `plugins/decimalai/scripts/registry.py`
that search and install run, and two JSON manifests. The only way to know a prompt change works is
to install it locally and run it. The script also runs on its own, and `DECIMALAI_PLUGIN_API_URL`
points it at a local registry (see the README).

## Before you open a PR

```bash
claude plugin validate .                      # marketplace manifest
claude plugin validate plugins/decimalai      # plugin manifest
```

Then install the working copy and exercise every command you touched:

```
/plugin marketplace add /path/to/decimalai-claude-plugins
/plugin install decimalai@decimalai
```

## What a PR is expected to contain

- **Both manifests validating.** `claude plugin validate` must pass on the marketplace root and on
  the plugin directory.
- **A real transcript.** Paste what the command actually did — the request, the output, the files
  written. Prompt changes cannot be unit-tested, so the transcript is the evidence. If you changed
  `/decimalai:install` or `scripts/registry.py`, run it against a namespaced skill (a `name`
  containing `/`) and against a skill with attachments; those are the two shapes that have broken
  before. Show that the files on disk hash to the sha256 the registry served.
- **A `version` bump in *both* `plugins/decimalai/.claude-plugin/plugin.json` and the matching
  entry in `.claude-plugin/marketplace.json`.** They must stay equal. Users only receive an update
  when the version changes, so a fix with no bump ships to nobody.
- **No new tool in `allowed-tools` without saying why.** The `allowed-tools` frontmatter on each
  command is a security boundary, not a convenience list. Widening it needs a sentence in the PR
  explaining what could not be done within the existing surface.

## House rules for command prompts

- **Identify skills by `url_slug`, never by `name`.** A registry `name` may be namespaced
  (`owner/skill`); it is the skill's identity and belongs in frontmatter, but it is not one path
  component and it does not resolve as a URL path segment. `url_slug` is the slash-free identifier
  for both.
- **Refuse, do not sanitise.** When a value that will become a path is unsafe, stop and tell the
  user why. Silently rewriting it hides a hostile record.
- **Skill files are the registry's bytes.** The script writes them; a prompt never asks Claude to
  write, edit or retype a skill's files.
- **Arguments reach the script on standard input**, inside a quoted heredoc, never inside a shell
  word or a URL. Command markdown must contain no `$` followed by a digit (Claude Code substitutes
  it with a positional argument) and no `!` followed by a backtick (Claude Code runs that as a
  shell command when the command loads).
- **Never invent a number.** If a field is null, render it blank or `New`. Every metric these
  commands display is a measurement, and a plausible-looking guess is worse than a gap.

## Reporting bugs

Open an issue with the exact command you ran and what it did. For anything security-related see
[SECURITY.md](SECURITY.md) — please do not open a public issue.
