---
description: Search the DecimalAI skills registry (ranked by measured effectiveness)
argument-hint: <query> [--category <cat>] [--sort recommended|lift|popular|top_rated]
allowed-tools: Bash(curl:*), Bash(python3:*)
---

Search the public DecimalAI skills registry for: **$ARGUMENTS**

The registry ranks skills by measured effectiveness — verified A/B benchmark lift against a no-skill baseline, live pass rates, and AI-rater scores — not by download counts. No API key is needed.

Steps:

1. Parse `$ARGUMENTS`: the free text is the query; honor `--category <cat>` and `--sort <axis>` flags if present (default sort: `recommended`).
2. Run (URL-encode the query):

```bash
curl -s "https://api.decimal.ai/api/v1/registry/skills?q=<QUERY>&sort=<SORT>&limit=10"
```

   Add `&category=<CATEGORY>` if a category flag was given.

3. From the JSON `items` array, present a compact table with these columns, in ranking order:
   - `url_slug` — **the install identifier.** Print this, never `name`. A registry `name` may be
     namespaced (`a5c-ai/appimage-builder`) and a `/` in it resolves as neither a URL path segment
     nor a directory name, so a `name` handed to `/decimalai:install` cannot work. `url_slug` is
     the slash-free identifier the registry addresses skills by. Show `name` as well only when it
     differs and the owner prefix is useful context — labelled as the author's name for the skill,
     not as something to type.
   - `description` (truncate ~100 chars)
   - SkillScore: `effectiveness.skill_score` (0–1; blank/`New` when null — never invent a number)
   - Benchmark lift: `benchmark_summary.pass_rate_delta_pts` as `+N pts` (blank when null)
   - Safety: `skill_safety` (passed / caution / blocked / unreviewed)
   - Adoption: `install_agents`, rendered as `on N agents` (blank when null or 0)

   **A `blocked` row is not an ordinary result.** The registry returns blocked skills in normal
   search responses — one plain query for `sql` comes back with a second-order SQL-injection skill
   among the top 100 — so filtering is this command's job, not the API's. Do not render a blocked
   skill as an installable row. List it last, under a separate `Blocked — will not install` heading,
   with its `url_slug` and the reason from `safety_status` / `intent_status`, and say plainly that
   `/decimalai:install` refuses it. Never present it as a candidate and never suggest a workaround.
   Dropping it silently would be worse than showing it: the user searched for something and is
   entitled to know a match exists and why it is withheld.

   Do **not** display `install_count`. It counts fork *events*, is never decremented when someone
   uninstalls, and on the live registry is overwhelmingly automated evaluation copies — it is not
   adoption and reporting it as adoption overstates every row. `install_agents` is the measured
   number the registry itself ranks by: agent setups the skill is currently installed on.

4. End with: which result best matches the user's need and why (one sentence), then remind them: install with `/decimalai:install <url_slug>`, or view at `https://app.decimal.ai/skills/<url_slug>`.

If the request fails or returns no items, say so plainly and suggest a broader query — do not fabricate results.
