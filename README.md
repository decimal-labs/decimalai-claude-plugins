# decimalai-claude-plugins

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) for [DecimalAI](https://decimal.ai) — the skills registry that ranks skills by **measured effectiveness** (verified A/B benchmark lift, live pass rates, safety scans), not download counts.

## Install

```
/plugin marketplace add decimal-labs/decimalai-claude-plugins
/plugin install decimalai@decimalai
```

## Commands

| Command | What it does |
|---|---|
| `/decimalai:search <query>` | Search the public registry; each result shows the exact `/decimalai:install` line, the folder it lands in, SkillScore, verified benchmark lift and safety band |
| `/decimalai:install <url_slug>` | Write a skill's folder exactly as the registry renders it (SKILL.md plus its scripts, references, templates and assets, each sha256-checked and given its mode) into `.claude/skills/<install_name>/`, after a trust check: blocked skills are never installed, and `caution` or `unreviewed` ones need your yes |
| `/decimalai:check` | Set up the [regression-check GitHub Action](https://github.com/decimal-labs/regression-check): manifest-driven impact analysis on every PR, no eval cases required |

All commands use DecimalAI's public registry API — no account or API key needed to search and install. The regression-check Action needs a `DECIMAL_API_KEY` (free at [app.decimal.ai](https://app.decimal.ai/settings)). Search and install need `python3` (standard library only) and `curl`.

**What install writes.** The registry renders a public skill's folder, and `/decimalai:install` writes those bytes unchanged. It is the same folder that `decimalai skills pull` writes and the skill's raw `SKILL.md` link serves. Before anything touches disk the plugin checks every file against the sha256 the registry declared, refuses any path outside the skill's folder or a second `SKILL.md`, and applies each file's mode (scripts are `0755`). The folder is `install_name`, the registry's folder name for the skill: a namespaced `owner/skill` lands in `.claude/skills/owner-skill/`. An existing folder with other contents is replaced only after you say yes, and it is moved to `.claude/decimalai-backup/` first. The copy is unmanaged: nothing records or updates it. For a pinned install that `decimalai skills update` and `decimalai skills verify` look after, use the CLI: `pip install "decimalai>=0.15"`, then `decimalai skills add <url_slug>`.

**Full documentation:** [Use skills without the SDK → Claude Code plugin](https://docs.decimal.ai/guides/use-skills-without-the-sdk#claude-code-plugin) — what each command writes, how the provenance stamp works, and where the plugin sits among the other four routes from the registry to disk.

**What leaves your machine:** the search query and the skill's url_slug or id, sent to `api.decimal.ai` as anonymous GETs with the user agent `decimalai-claude-plugin/<version>`. No account is created and nothing is stored against you; those requests appear in server logs as described in §1.4 of the [privacy policy](https://app.decimal.ai/privacy). The folder request is labelled `channel=plugin&purpose=pull`, and the registry counts it as one fetch of that skill for that day, with nothing that identifies you. The plugin sends no telemetry of its own. Fetch counts are kept apart from a skill's measured effectiveness, so a local install does not change it.

## Why this registry?

Every public skill on DecimalAI carries a safety-scan verdict, an LLM intent review, and — where benchmarked — a **verified lift** against a no-skill baseline ("+12 pts pass rate on gemini-3.5-flash", re-benchmarked when the skill changes). `/decimalai:search` surfaces that evidence next to every result, so you install what's proven to work, not what's most downloaded.

## Repo layout

```
.claude-plugin/marketplace.json     ← marketplace catalog
plugins/decimalai/
  .claude-plugin/plugin.json        ← plugin manifest
  commands/search.md                ← /decimalai:search
  commands/install.md               ← /decimalai:install
  commands/check.md                 ← /decimalai:check
  scripts/registry.py               ← what search and install run (python3 stdlib + curl)
```

## Local development

```
/plugin marketplace add /path/to/decimalai-claude-plugins
/plugin install decimalai@decimalai
```

`scripts/registry.py` also runs on its own: `echo "<url_slug>" | python3 plugins/decimalai/scripts/registry.py install --project /tmp/some-project`. Set `DECIMALAI_PLUGIN_API_URL` to point it at a local registry (an `https://` origin, or `http://` on localhost only). Its docstring lists the checks and exit codes.

Bump `version` in both `plugin.json` and the marketplace entry on every release — users only receive updates when it changes.

## License

MIT
