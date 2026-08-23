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
| `/decimalai:search <query>` | Search the public registry; results show SkillScore, verified benchmark lift, and safety band |
| `/decimalai:install <slug>` | Fetch a skill's SKILL.md + attachments (scripts/references) into `.claude/skills/<slug>/` — with a trust check first (blocked skills are never installed) |
| `/decimalai:check` | Set up the [regression-check GitHub Action](https://github.com/decimal-labs/regression-check): manifest-driven impact analysis on every PR, no eval cases required |

All commands use DecimalAI's public registry API — no account or API key needed to search and install. The regression-check Action needs a `DECIMAL_API_KEY` (free at [app.decimal.ai](https://app.decimal.ai/settings)).

**Full documentation:** [Use skills without the SDK → Claude Code plugin](https://docs.decimal.ai/guides/use-skills-without-the-sdk#claude-code-plugin) — what each command writes, how the provenance stamp works, and where the plugin sits among the other four routes from the registry to disk.

**What leaves your machine:** the search query and the skill slug, sent to `api.decimal.ai` as anonymous GETs. No account is created and nothing is stored against you; those requests appear in server logs as described in §1.4 of the [privacy policy](https://app.decimal.ai/privacy). The plugin sends no telemetry of its own — DecimalAI has no record that you installed anything, which is also why a local install does not affect a skill's measured effectiveness.

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
```

## Local development

```
/plugin marketplace add /path/to/decimalai-claude-plugins
/plugin install decimalai@decimalai
```

Bump `version` in both `plugin.json` and the marketplace entry on every release — users only receive updates when it changes.

## License

MIT
