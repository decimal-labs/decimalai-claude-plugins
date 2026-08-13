---
description: Set up DecimalAI's regression-check GitHub Action for this repo
argument-hint: [agent-name]
allowed-tools: Read, Write, Bash(ls:*), Bash(git:*)
---

Help the user add DecimalAI's **regression-check** GitHub Action to this repository. The Action diffs the agent's candidate manifest against recorded production traces on every PR and posts an impact report — which traces would break, at what risk level — with **no eval cases required**.

Context: $ARGUMENTS (if provided, this is the agent name; it must match the `agent_name` used in `decimalai.init()` / the tracing handler).

Steps:

1. Explain the prerequisites, checking what you can in the repo:
   - The agent must already be traced with the DecimalAI SDK (`pip install decimalai`; look for `decimalai.init(` in the codebase to confirm and to find the real `agent_name`).
   - A `DECIMAL_API_KEY` must be added to the repo's GitHub Actions secrets (Settings → Secrets and variables → Actions). The user gets the key from https://app.decimal.ai/settings.

2. Create `.github/workflows/decimal-regression-check.yml` with:

```yaml
name: Decimal regression check
on: [pull_request]

permissions:
  contents: read
  pull-requests: write   # lets the Action post/update the impact comment

jobs:
  impact:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # If the PR changes the agent, export its candidate manifest here, e.g.:
      #   pip install decimalai && python -c "import decimalai, my_agent; decimalai.flush_manifest_for_ci()"
      - uses: decimal-labs/regression-check@v1
        with:
          api-key: ${{ secrets.DECIMAL_API_KEY }}
          agent-name: <AGENT_NAME>       # must match decimalai.init()
          fail-on: high                  # high | medium | none
```

   Replace `<AGENT_NAME>` with the detected or provided agent name. Keep the manifest-export comment — the Action reads the candidate manifest id from `$GITHUB_OUTPUT` (`decimal_manifest_id`) or `./decimal_manifest_id.txt`, both written by `decimalai.flush_manifest_for_ci`.

3. Explain the knobs briefly:
   - `fail-on`: `high` fails the check only on HIGH-RISK impacts (default); `medium` is stricter; `none` is report-only.
   - `comment-mode`: `update` (one comment, refreshed per push — default) or `new`.
   - `trace-window-days`: how far back to look for affected production traces (default 30).

4. Point to the full guide: https://docs.decimal.ai/guides/regression-check and the Action repo: https://github.com/decimal-labs/regression-check.

Do not invent inputs that the Action does not have; the complete input list is in the Action's `action.yml`.
