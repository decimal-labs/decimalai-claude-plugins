# Contributing to decimalai-claude-plugins

Thanks for your interest. This repo is a Claude Code plugin marketplace, which shapes everything
below: there is no build step and no test runner. The deliverable is **prompt text** in
`plugins/decimalai/commands/*.md` plus two JSON manifests, and the only way to know a change works
is to install it locally and run it.

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
  `/decimalai:install`, run it against a namespaced skill (a `name` containing `/`) and against a
  skill with `attachment_count > 0`; those are the two shapes that have broken before.
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
- **Never invent a number.** If a field is null, render it blank or `New`. Every metric these
  commands display is a measurement, and a plausible-looking guess is worse than a gap.

## Reporting bugs

Open an issue with the exact command you ran and what it did. For anything security-related see
[SECURITY.md](SECURITY.md) — please do not open a public issue.
