---
description: Install a DecimalAI registry skill (SKILL.md + attachments) into this project
argument-hint: <url_slug or skill id>
allowed-tools: Bash(python3:*)
---

Install the DecimalAI registry skill **$ARGUMENTS** into this project's `.claude/skills/`, as an
unmanaged copy written byte for byte from the registry.

1. **Check the argument before running anything.** It must be one skill's `url_slug` or its id,
   matching `^[A-Za-z0-9][A-Za-z0-9._-]*$`, optionally followed by `--yes` or `--force`. If it does
   not, STOP and refuse: do not strip, escape or percent-encode it and retry. A registry `name`
   such as `owner/skill` is the skill's identity, not its address. Tell the user to run
   `/decimalai:search` and copy the line in its `install with` column. The script applies the same
   rule again, so a mistake here is refused, not run.

2. **Run the installer exactly as written.** The argument travels on standard input inside a
   quoted heredoc, so no shell ever parses it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/registry.py" install --project "${CLAUDE_PROJECT_DIR}" <<'DECIMALAI_ARGS'
$ARGUMENTS
DECIMALAI_ARGS
```

   It needs only `python3` (standard library) and `curl`, and sends two anonymous GETs to
   `https://api.decimal.ai`:
   - **The skill's record.** The script prints its `safety:` band and `benchmark:` line. A
     `blocked` skill stops here.
   - **The skill's folder**, `GET /api/v1/registry/skills/<id>/bundle?formats=1&channel=plugin&purpose=pull`.
     The answer lists every file with its exact text, sha256 and mode.

   Before writing anything, the script refuses a folder name no skill loader accepts, a path
   outside `scripts/`, `references/`, `templates/` or `assets/` (including `..`, absolute paths
   and backslashes), a second `SKILL.md` anywhere in the tree, a mode other than 0644 or 0755,
   and any file whose bytes do not hash to the sha256 the registry declared. It writes into a
   staging folder, reads each file back to re-check its hash and mode, and only then moves the
   folder to `.claude/skills/<install_name>/`. `install_name` is the registry's folder name for
   the skill, so a namespaced `owner/skill` lands in `.claude/skills/owner-skill/`.

3. **Act on the exit status.** Never write, edit or copy the skill's files yourself: no Write or
   Edit, and no retyping text from the output. The script writes the registry's bytes, and
   anything typed by hand is not those bytes.
   - **0**: installed, or already installed with exactly these bytes. Go to step 4.
   - **3**: the safety band is `caution`, `unreviewed` or missing. Show the user the `skill:`,
     `safety:` and `benchmark:` lines and ask whether to install anyway. Only after a clear yes,
     run the same command again with `--yes` added right after `install`. Never add `--yes` on
     your own.
   - **4**: the skill is blocked, or the registry withdrew the version. Stop. Do not suggest a
     workaround and do not look for another copy.
   - **5**: the folder already exists with other contents, and the message lists the files that
     differ. Ask the user whether to replace it. Only after a clear yes, run the same command
     again with `--force` added right after `install`; the current folder is moved to
     `.claude/decimalai-backup/` first. If the message names a symlink or a file in the way,
     stop and report it.
   - **6** or **7**: the registry's answer failed a check (an unsafe path, a bad name, a hash
     mismatch), and nothing was written. Stop and report the message. Do not retry with other
     flags, and do not fetch the files another way.
   - **2**: the argument was refused (see step 1). If python3 instead says it cannot open the
     script file, this Claude Code did not resolve the plugin's install path: ask the user to
     update Claude Code, and do not look for the script elsewhere.
   - **8**: the registry could not be reached or answered with an error. Report the message, and
     for "not found" suggest `/decimalai:search`.

4. **Confirm to the user.** Give the folder and every file written with its mode, any
   `not written:` line, any `registry note:` line, and the safety band and benchmark line.
   - `not written:` lines are binary attachments, which the registry does not store, and nested
     `SKILL.md` files, which would load as a second skill.
   - `registry note:` lines include the `allowed-tools` the registry dropped: a skill you did not
     author may pre-approve only `Read`, `Grep` and `Glob`.

   Then say plainly that this is an unmanaged copy. Nothing records it, and installing again
   replaces it after asking. For a managed install, pinned in `.decimal/skills.lock`, updated with
   `decimalai skills update` and checked with `decimalai skills verify`, the path is
   `pip install "decimalai>=0.15"` and then `decimalai skills add <url_slug>`. Claude Code reads
   skills from `.claude/skills/`. If `/<install_name>` is not available in this session, restart
   Claude Code.
