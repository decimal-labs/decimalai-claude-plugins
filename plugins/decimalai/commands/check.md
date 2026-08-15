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

2. Create the manifest-extraction entry point `scripts/init_for_decimal.py` (skip if the repo already has one — check first). The Action does **not** build the manifest itself: it diffs a *candidate manifest that a prior step uploaded*. Without this step the Action has nothing to compare and fails the first PR with `No candidate-manifest-id provided or discoverable`.

```python
"""Registers this agent's candidate manifest for DecimalAI's regression check.

Runs in CI under DECIMALAI_MODE=manifest_only: the SDK captures tools,
prompts and models from the real runtime objects — no source parsing, and
no LLM calls are issued.
"""
import decimalai
from myapp.agent import build_agent  # adjust to your agent factory

AGENT_NAME = "<AGENT_NAME>"  # must match decimalai.init()


def main() -> None:
    decimalai.init()  # picks up DECIMAL_API_KEY + DECIMALAI_MODE from env

    agent = build_agent()  # construct the agent exactly as production does

    result = decimalai.flush_manifest_for_ci(
        agent_name=AGENT_NAME,
        chain=agent,  # LangChain/LangGraph: introspects tools, prompts, models
    )
    print(f"Manifest registered: {result['manifest_id']} -> {result['output_path']}")


if __name__ == "__main__":
    main()
```

   Adapt the import and the factory call to the repo you're in. If the agent isn't a LangChain/LangGraph object, drop `chain=` and pass the components explicitly instead — `flush_manifest_for_ci(agent_name=..., tools=[...], prompts={...}, models={...}, output_schema={...})`. Anything passed explicitly wins over what introspection finds, so it's also the escape hatch when `chain=` picks up the wrong thing.

   Both calls are required: `decimalai.init()` configures the SDK, and `decimalai.flush_manifest_for_ci()` is what actually uploads the candidate manifest and writes its id (`decimal_manifest_id`) for the next step.

3. Create `.github/workflows/decimal-regression-check.yml` with:

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

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -e .

      - name: Manifest extraction
        id: decimal_manifest
        env:
          DECIMALAI_MODE: manifest_only
          DECIMAL_API_KEY: ${{ secrets.DECIMAL_API_KEY }}
          # Placeholders for keys your init code requires. Nothing is called:
          # manifest_only mode suppresses LLM calls.
          OPENAI_API_KEY: dummy_for_init
        run: python scripts/init_for_decimal.py

      - uses: decimal-labs/regression-check@v1
        with:
          api-key: ${{ secrets.DECIMAL_API_KEY }}
          agent-name: <AGENT_NAME>       # must match decimalai.init()
          candidate-manifest-id: ${{ steps.decimal_manifest.outputs.decimal_manifest_id }}
          fail-on: high                  # high | medium | none
```

   Replace `<AGENT_NAME>` (both files) with the detected or provided agent name, and `pip install -e .` with whatever installs this repo's dependencies. The `id:` on the extraction step is what makes `decimal_manifest_id` — written by `decimalai.flush_manifest_for_ci` to `$GITHUB_OUTPUT` — readable as `candidate-manifest-id` in the next step. If that wiring is left out, the Action falls back to discovering the id from `$GITHUB_OUTPUT` or `./decimal_manifest_id.txt`.

4. Explain the knobs briefly:
   - `fail-on`: `high` fails the check only on HIGH-RISK impacts (default); `medium` is stricter; `none` is report-only.
   - `comment-mode`: `update` (one comment, refreshed per push — default) or `new`.
   - `trace-window-days`: how far back to look for affected production traces (default 30).

5. Point to the full guide: https://docs.decimal.ai/guides/regression-check and the Action repo: https://github.com/decimal-labs/regression-check.

Do not invent inputs that the Action does not have; the complete input list is in the Action's `action.yml`.
