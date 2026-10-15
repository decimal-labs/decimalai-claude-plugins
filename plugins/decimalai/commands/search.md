---
description: Search the DecimalAI skills registry (ranked by measured effectiveness)
argument-hint: <query> [--category <cat>] [--sort recommended|lift|popular|top_rated]
allowed-tools: Bash(python3:*)
---

Search the public DecimalAI skills registry for: **$ARGUMENTS**

The registry ranks skills by measured effectiveness: verified A/B benchmark lift against a
no-skill baseline, live pass rates and AI-rater scores, not download counts. No API key is needed.

1. **Run the search exactly as written.** The query travels on standard input inside a quoted
   heredoc, so no shell parses it. The script reads `--category <cat>` and `--sort <axis>`
   (default `recommended`), URL-encodes the rest as the query, and sends one anonymous GET to
   `https://api.decimal.ai/api/v1/registry/skills`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/registry.py" search <<'DECIMALAI_ARGS'
$ARGUMENTS
DECIMALAI_ARGS
```

2. **Show the user the table it prints, as printed.**
   - The first column, `install with`, is the exact command that installs each skill:
     `/decimalai:install <url_slug>`, or the skill's id when its url_slug cannot be typed.
     `lands in` is the folder that command writes.
   - Never present a registry `name` such as `owner/skill` as something to type. It appears in
     parentheses only as the author's name for the skill.
   - SkillScore `New` and a blank lift mean not measured yet; never fill them in.
   - Adoption is `install_agents`, the agent setups the skill is on now. `install_count` is
     deliberately absent: it counts fork events, is never decremented, and is mostly automated
     evaluation copies.
   - Blocked skills are listed apart, under "Blocked, will not install", with the scanner and
     intent-review verdicts. The registry returns them in ordinary results. Do not present one as
     a candidate or suggest a workaround, but do not hide it either: the user is entitled to know
     a match exists and why it is withheld.

3. **End with a recommendation.** Say which result best matches the user's need and why, in one
   sentence, followed by its install line.

If the script exits non-zero, report its message plainly and suggest a broader query; do not
fabricate results. Exit 8 means the registry could not be reached or refused the request; exit 2
means a bad `--sort` value. If python3 says it cannot open the script file, this Claude Code did
not resolve the plugin's install path: ask the user to update Claude Code.
