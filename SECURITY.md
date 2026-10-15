# Security Policy

This repository is a **Claude Code plugin marketplace**. It ships no compiled code. The
deliverable is three slash-command prompts (`commands/*.md`), one standard-library Python script
that two of them run (`scripts/registry.py`), and two JSON manifests. The script fetches from the
public DecimalAI registry with `curl` and writes files into the user's project. That is the whole
trust boundary, and it is what this policy is about.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Two ways to reach us, either is fine:

- **GitHub private vulnerability reporting** — **Security → Report a vulnerability** on this
  repository. That opens a private advisory only maintainers can see.
- **Email** — [hello@decimal.ai](mailto:hello@decimal.ai). We do not publish a PGP key. If you
  would rather not put the details in cleartext email, use the GitHub channel above — the advisory
  is visible only to you and the maintainers.

Include what you have: what you found, how to reproduce it, which version of the plugin you had
installed (`version` in `plugins/decimalai/.claude-plugin/plugin.json`), and what an attacker
could actually do with it. The registry skill or query that triggers it is the most useful thing
you can send.

## Scope

The commands take two kinds of untrusted input: the argument the user types, and the JSON the
public registry returns. Both end up in a shell command, in a file path, or in a file's contents.
Anything that escapes those is in scope:

- **Writing outside `.claude/skills/<install_name>/`.** The install script takes the folder name
  and every file path from the registry's answer. A registry answer that causes a write to an
  absolute path, a parent directory, or anywhere else in the user's tree is the highest-severity
  bug this repo can have. So is a write through a symlink, or a second `SKILL.md` inside a skill's
  folder.
- **Command injection through `$ARGUMENTS`.** The user's argument reaches the script on standard
  input, inside a quoted heredoc, and is never interpolated into a URL or a shell word. An
  argument that ends up executing anything other than the script is in scope. One limit is known
  and documented. Claude Code substitutes `$ARGUMENTS` as plain text, so an argument containing a
  newline followed by the line `DECIMALAI_ARGS` ends the heredoc early. The command's first step
  refuses any argument outside the url_slug allowlist before anything runs. Claude Code's
  permission rules also match each line of a multi-line command separately (per its
  documentation), so the command's `Bash(python3:*)` does not pre-approve an injected line.
- **Trust-gate bypass.** `/decimalai:install` must refuse a skill whose `skill_safety` band is
  `blocked`, and must obtain explicit confirmation for `caution` and `unreviewed`. The script
  enforces this: it exits without fetching the folder until it is run with `--yes`. Any registry
  response shape (a missing field, an unexpected type, an error body) that results in a `blocked`
  skill being written, or a `caution` skill being written silently, is in scope.
- **Provenance integrity.** The plugin writes the registry's rendered `SKILL.md` unchanged. Its
  `metadata.decimalai-body-sha256` is what lets a reader re-fetch the skill and confirm the body;
  the registry's ETag for that `SKILL.md` starts with the same hash. A written file that differs
  from the bytes served defeats that.
- **File integrity.** Every file is written only after its bytes hash to the sha256 the registry
  declared, and is read back and re-checked, with its mode, before the folder is moved into
  place. A way to get an unverified or altered file onto disk is in scope.
- **Tool-surface widening.** Each command declares `allowed-tools`. A prompt that induces Claude
  to reach for a tool outside that declaration is in scope.

**Out of scope**

- The content of any individual skill in the registry. Skills are third-party material; the
  registry scans them and publishes a safety band, and `/decimalai:install` shows you that band
  before it writes anything. Report a malicious *skill* through the report link on its registry
  page, not here. A flaw in how this plugin *presents or enforces* that band is in scope.
- The DecimalAI hosted API (`api.decimal.ai`). Report those the same way, to the same address;
  they are just fixed elsewhere.
- Claude Code's own plugin loader, marketplace resolution, or permission system. Report those to
  Anthropic; tell us too if our manifests are what make the issue reachable.
- The fact that the commands make network requests to `api.decimal.ai`. That is what they are for,
  and it is documented. A request to any *other* host is in scope.
- Scanner output with no demonstrated impact.

## What happens next

We are a small team, so rather than publish a response time we cannot hold to, here is what we
actually do:

- We acknowledge a report once we have read it, and we say plainly if triage is going to take a
  while.
- We tell you whether we consider it in scope and what we intend to do.
- We follow coordinated disclosure. We agree a timeline with you rather than impose one, and we
  will not ask you to stay quiet indefinitely. Because Claude Code installs a plugin at a pinned
  version, a fix means both a `version` bump in `plugin.json` and the matching marketplace entry,
  and we will tell you when both have shipped.
- We are happy to credit you in the advisory and the release notes. Tell us how you would like to
  be named, or say that you would rather not be.

There is no paid bug bounty. That is a resourcing decision, not a judgment about the value of your
work.

## Safe harbour

If you make a good-faith effort to follow this policy, we will not pursue or support legal action
against you for your research. Good faith means avoiding privacy violations and service
degradation, only testing against projects and accounts you own or have permission to test, and
giving us a reasonable opportunity to fix the issue before you disclose it publicly.

If you are not sure whether what you found is a security issue, email
[hello@decimal.ai](mailto:hello@decimal.ai) and ask. That is always the right call.
