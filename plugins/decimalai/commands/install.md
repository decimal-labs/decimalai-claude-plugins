---
description: Install a DecimalAI registry skill (SKILL.md + attachments) into this project
argument-hint: <url-slug>
allowed-tools: Bash(curl:*), Bash(python3:*), Bash(mkdir:*), Write, Read
---

Install the DecimalAI registry skill **$ARGUMENTS** into this project as a local skill.

Steps:

1. **Check the identifier, then fetch.** `$ARGUMENTS` must be a skill's `url_slug` — the
   slash-free identifier the registry addresses skills by. A registry `name` may be namespaced
   (`a5c-ai/appimage-builder`); that is the skill's identity, not its address, and it resolves as
   neither a URL path segment nor a directory name. If `$ARGUMENTS` contains `/` or `\`, is `.`
   or `..`, or begins with `/` or `~`, **STOP and refuse** — do not strip, escape, or percent-encode
   it and retry (`%2F` 404s too). Tell the user that looks like a skill `name` rather than a
   `url_slug`, and to run `/decimalai:search` and use the `url_slug` column.

   Then fetch the skill record (public endpoint, no key needed) and save it:

```bash
curl -sf "https://api.decimal.ai/api/v1/registry/skills/$ARGUMENTS" -o /tmp/decimalai-skill.json
```

   If curl exits non-zero (`-f` writes no file on an error status — a 404 exits 22 over HTTP/1.1
   and 56 over HTTP/2), the slug wasn't found — tell the user and suggest `/decimalai:search`
   first; do not proceed.

2. **Trust check before writing anything.** Report to the user:
   - `skill_safety` (unified band: passed / caution / blocked / unreviewed)
   - `safety_status` (scanner verdict) and `intent_status`
   - benchmark evidence: `benchmark_summary.verdict` and `pass_rate_delta_pts`

   If `skill_safety` is `blocked`, STOP and do not install. If it is `caution` or `unreviewed`, ask the user to confirm before proceeding.

3. Build the stamped SKILL.md content. Run this to print it (it adds provenance frontmatter — `source` pointing at the registry version and `source_sha256`, the first 12 hex chars of the SHA-256 of the exact `body_markdown` as fetched, computed *before* stamping; any stale top-level `source`/`source_sha256` keys are replaced):

```bash
python3 - <<'PY'
import json, hashlib, re, sys
rec = json.load(open("/tmp/decimalai-skill.json"))
if "name" not in rec:  # error shape, e.g. {"detail": "..."}
    sys.exit(f"registry error: {rec.get('detail') or rec}")
body = rec.get("body_markdown")
if not body:
    sys.exit(f"skill {rec['name']!r} has no body to install")
version = rec.get("latest_version_number") or 1
# ADDRESS from url_slug, IDENTITY from name. `name` may be namespaced ("owner/skill");
# it belongs in the frontmatter but cannot be one path component. Falling back
# to `name` keeps older records working, which is exactly why the guard below
# is not optional.
slug = rec.get("url_slug") or rec["name"]
# Refuse, never sanitise — mirrors _safe_skill_dirname() in the Python SDK
# (decimal-labs/decimalai-python). This value comes from a remote
# server and becomes a directory name; a quiet rewrite would hide a hostile
# record instead of surfacing it.
if (not slug or slug in (".", "..") or "\0" in slug
        or "/" in slug or "\\" in slug or slug.startswith(("~", "/"))):
    sys.exit(f"refusing to write outside the skill directory: unsafe skill directory name "
             f"{slug!r} (path traversal / absolute path). The skill source may be malicious.")
stamp_lines = [
    f"source: https://app.decimal.ai/s/{slug}@{version}/SKILL.md",
    f"source_sha256: {hashlib.sha256(body.encode()).hexdigest()[:12]}",
]
# Plain YAML scalar when safe, JSON-quoted otherwise — ':' is never
# safe-plain, it would start a nested mapping.
y = lambda v: v if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._/@-]*", v) else json.dumps(v, ensure_ascii=False)
# Frontmatter detection handles CRLF bodies, an EOF close, and an empty
# block — all merge instead of double-stamping.
m = re.match(r"---\r?\n(?:([\s\S]*?)\r?\n)?---(\r?\n|$)", body)
if m:
    kept = [l for l in re.split(r"\r?\n", m.group(1) or "")
            if l and not l.startswith(("source:", "source_sha256:"))]
    out = "---\n" + "\n".join(kept + stamp_lines) + "\n---" + ("\n" if m.group(2) else "") + body[m.end():]
else:
    desc = y((rec.get("description") or "").replace("\n", " "))
    out = f"---\nname: {y(rec['name'])}\ndescription: {desc}\n" + "\n".join(stamp_lines) + "\n---\n\n" + body
sys.stderr.write(f"install-dir: {slug}\n")
print(out, end="")
PY
```

   The script prints `install-dir: <slug>` on stderr. Create `.claude/skills/<slug>/` using
   **exactly** that value — never the `name` field — and write the printed stdout content verbatim
   to `.claude/skills/<slug>/SKILL.md`. If the script exited with the "refusing to write outside
   the skill directory" message, stop and report it; do not pick a different directory name.

4. **Fetch attachments** if the record shows `attachment_count > 0`. List them (public, metadata only):

```bash
curl -s "https://api.decimal.ai/api/v1/registry/skills/$ARGUMENTS/attachments"
```

   For each entry in the `attachments` array, fetch its content by `id`:

```bash
curl -s "https://api.decimal.ai/api/v1/registry/skills/$ARGUMENTS/attachments/<id>"
```

   and write the `content_text` field verbatim to `.claude/skills/<slug>/<file_path>` (paths look like `scripts/grade.py` or `references/spec.md`; create the subdirectory). Two guards per file, both non-negotiable:
   - Only write a `file_path` that is exactly `<dir>/<name>` where `<dir>` is one of `scripts`, `references`, `templates`, `assets` — skip and warn on anything else (absolute paths, `..`, extra depth).
   - Verify the SHA-256 hex of `content_text` **starts with** the listing's `content_hash` (the registry serves the full 64-hex digest on recent attachments and a 32-hex truncated digest on older imports). If `content_hash` is missing, shorter than 32 chars, or not a prefix of the computed digest, do NOT write the file, warn the user, and continue with the rest.

5. Confirm to the user: every file path written (SKILL.md plus each attachment), the skill's safety band, and its benchmark evidence. Note that the files are now a local copy — DecimalAI has no record of this install, so nothing here changes the skill's measured effectiveness. To feed real usage back into that measurement, trace the agent that loads the skill with the DecimalAI SDK (`pip install decimalai`, then `decimalai.init(...)` and `decimalai.log_skill_activation(name=...)`, which needs a free API key) — see https://docs.decimal.ai/guides/skills.
