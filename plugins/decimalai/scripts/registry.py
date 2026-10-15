#!/usr/bin/env python3
"""The DecimalAI registry, for the decimalai Claude Code plugin's commands.

    registry.py install [--yes] [--force] [--project DIR]    < "<url_slug or skill id>"
    registry.py search                                        < "<query> [--category C] [--sort S]"

/decimalai:install and /decimalai:search run this file. It needs python3 (standard library
only) and curl, and talks to nothing but the public registry at https://api.decimal.ai.

The command's arguments arrive on standard input from a quoted heredoc, never on the command
line, so whatever was typed after the command name is never parsed by a shell.

install
    Writes a public skill's folder, exactly as the registry renders it, to
    <project>/.claude/skills/<install_name>/:

    1. Reads the skill's record and its safety band. ``blocked`` is refused. ``caution``,
       ``unreviewed`` or a missing band needs the user's yes first (``--yes``).
    2. Fetches GET /api/v1/registry/skills/<id>/bundle (by the id from step 1, so the folder
       is of the skill whose band was shown). The bundle lists every file with its text,
       sha256 and mode.
    3. Checks the bundle before writing anything. It must be format 1 and the foreign
       variant, with a folder name every skill loader accepts and exactly one SKILL.md. Every
       other path must sit under scripts/, references/, templates/ or assets/, with no '..',
       '.', empty segment, backslash, control character, absolute path or second SKILL.md.
       Modes must be 0644 or 0755, and each file's bytes must hash to its declared sha256.
       These are the rules the decimalai SDK applies to the same answer.
    4. Writes the files into a staging folder beside the target, in binary, with their modes,
       reads them back and re-checks each sha256 and mode. Only then is the staging folder
       moved into place.

    An existing folder holding exactly these bytes is left alone. One that differs is
    refused unless ``--force``, which first moves it to .claude/decimalai-backup/. A symlink
    or a file in the way is always refused.

search
    Prints the registry's best matches as a table whose first column is the exact
    /decimalai:install line for each skill. Blocked skills are listed apart.

Exit codes
    0  done (installed, already installed, or results printed)
    2  bad arguments (a reference that is not a url_slug or a skill id, an unknown flag)
    3  the skill's safety band needs the user's confirmation: run again with --yes
    4  refused: the skill is blocked, or the registry withdrew the version (HTTP 410)
    5  the folder already exists with other contents (run again with --force to replace it
       and keep a backup), or a symlink or a file is in the way
    6  the registry's answer breaks the bundle contract; nothing was written
    7  a file's bytes do not match the sha256 the registry declared; nothing was written
    8  the registry could not be reached or answered with an error (404, 429, 5xx)

DECIMALAI_PLUGIN_API_URL points the script at another registry (an https:// URL, or http://
to localhost only), for testing; the script says so when it is set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse

VERSION = "0.1.3"
USER_AGENT = f"decimalai-claude-plugin/{VERSION}"
API = "https://api.decimal.ai"
APP = "https://app.decimal.ai"
API_ENV = "DECIMALAI_PLUGIN_API_URL"

#: What /decimalai:install accepts: a url_slug or a skill id (a UUID matches too).
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
MAX_REF = 512
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

#: Folder names every skill loader accepts (skillfmt.is_valid_install_name).
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME_MAX = 64
#: Within NAME_RE's alphabet, the plain YAML 1.1 scalars that do not read back as a string
#: (`yes`, `404`, `0x1f`, `2020-01-01`): a loader would see a non-string `name:`.
YAML_NOT_A_STRING = re.compile(
    r"yes|no|true|false|on|off|null|0b[01]+|0[0-7]+|0|[1-9][0-9]*|0x[0-9a-f]+"
    r"|[0-9]{4}-[0-9]{2}-[0-9]{2}")

ATTACHMENT_DIRS = ("scripts", "references", "templates", "assets")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
MODE_RE = re.compile(r"0?[0-7]{3}")
MODES = (0o644, 0o755)
FORMATS = (1,)
#: OS clutter that does not make an installed folder differ from the registry's.
CLUTTER = {".DS_Store", "Thumbs.db", "desktop.ini"}
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
SORTS = ("recommended", "lift", "popular", "top_rated")

OK, USAGE, CONFIRM, REFUSED, EXISTS, CONTRACT, INTEGRITY, REGISTRY = 0, 2, 3, 4, 5, 6, 7, 8


class Stop(Exception):
    """End the run with this exit code and message."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def shown(value: object, limit: int = 120) -> str:
    """Text from the registry or the user, safe to print on one line."""
    text = value if isinstance(value, str) else repr(value)
    text = "".join(c if c.isprintable() else f"\\u{ord(c):04x}" for c in text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def say(line: str = "") -> None:
    print(line, flush=True)


# ── The registry ────────────────────────────────────────────────────────────────────


def registry_base() -> str:
    raw = os.environ.get(API_ENV, "").strip()
    if not raw:
        return API
    parts = urllib.parse.urlsplit(raw)
    loopback = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not (parts.scheme == "https" and parts.hostname or parts.scheme == "http" and loopback) \
            or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise Stop(USAGE, f"{API_ENV} must be an https:// origin, or http:// on localhost; "
                          f"it is {shown(raw)}")
    base = raw.rstrip("/")
    say(f"registry: {base} (from {API_ENV})")
    return base


def fetch(url: str) -> tuple:
    """GET ``url`` with curl: (HTTP status, body bytes)."""
    proto = "=https" if url.startswith("https://") else "=http"
    with tempfile.TemporaryDirectory(prefix="decimalai-") as tmp:
        body = os.path.join(tmp, "body")
        cmd = ["curl", "--silent", "--show-error", "--proto", proto,
               "--connect-timeout", "15", "--max-time", "60",
               "--max-filesize", str(MAX_RESPONSE_BYTES),
               "--user-agent", USER_AGENT, "--header", "Accept: application/json",
               "--output", body, "--write-out", "%{http_code}", url]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except FileNotFoundError:
            raise Stop(REGISTRY, "curl is not installed; /decimalai commands need curl") from None
        except subprocess.TimeoutExpired:
            raise Stop(REGISTRY, "the registry did not answer within 90 seconds") from None
        if done.returncode != 0:
            raise Stop(REGISTRY, f"could not reach the registry (curl exit {done.returncode}: "
                                 f"{shown(done.stderr.strip(), 200)})")
        status = int(done.stdout.strip() or 0)
        data = b""
        if os.path.exists(body):
            with open(body, "rb") as fh:
                data = fh.read()
        return status, data


def error_text(status: int, data: bytes) -> tuple:
    """(message, reason) from an error answer: structured JSON, a string detail, or text."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        doc = None
    detail = doc.get("detail") if isinstance(doc, dict) else None
    if isinstance(detail, dict):
        return shown(detail.get("message") or detail.get("code") or "", 300), detail.get("reason")
    if isinstance(detail, str):
        return shown(detail, 300), None
    text = data.decode("utf-8", "replace").strip()
    return shown(text or f"HTTP {status}", 200), None


def get_json(url: str, what: str) -> dict:
    status, data = fetch(url)
    if status != 200:
        message, reason = error_text(status, data)
        if status == 410:
            raise Stop(REFUSED, f"the registry withdrew {what}: {message}"
                                + (f" (reason: {shown(reason)})" if reason else ""))
        if status == 404:
            raise Stop(REGISTRY, f"not found: {message}. Run /decimalai:search to find the "
                                 "skill's url_slug.")
        if status == 429:
            raise Stop(REGISTRY, f"the registry is rate-limiting requests (HTTP 429: {message}); "
                                 "try again in a minute")
        raise Stop(REGISTRY, f"the registry answered HTTP {status} for {what}: {message}")
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Stop(CONTRACT, f"the registry's answer for {what} is not JSON") from None
    if not isinstance(doc, dict):
        raise Stop(CONTRACT, f"the registry's answer for {what} is not a JSON object")
    return doc


# ── The bundle contract (the same checks as the decimalai SDK's client) ───────────────


def valid_install_name(name: object) -> bool:
    return (isinstance(name, str) and len(name) <= NAME_MAX and bool(NAME_RE.fullmatch(name))
            and not YAML_NOT_A_STRING.fullmatch(name))


def path_problem(path: object):
    """Why a bundle path may not be written, or None (skillfmt rules F14 and F15)."""
    if not isinstance(path, str) or not path:
        return f"path {shown(path)} is not a non-empty string"
    if any(seg.casefold() == "skill.md" for seg in path.replace("\\", "/").split("/")):
        return f"{shown(path)} has a file or folder named SKILL.md, which would load as a second skill"
    segments = path.split("/")
    if "\\" in path or CONTROL_RE.search(path):
        return f"{shown(path)} contains a backslash or a control character"
    if path.startswith("/"):
        return f"{shown(path)} is absolute"
    if any(s in ("", ".", "..") for s in segments):
        return f"{shown(path)} has an empty, '.' or '..' segment"
    if len(segments) < 2 or segments[0] not in ATTACHMENT_DIRS:
        return f"{shown(path)} is not under {', '.join(d + '/' for d in ATTACHMENT_DIRS)}"
    return None


def contract(message: str) -> Stop:
    return Stop(CONTRACT, f"refused: the registry's bundle {message}. Nothing was written.")


def file_mode(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        mode = value
    elif isinstance(value, str) and MODE_RE.fullmatch(value):
        mode = int(value, 8)
    else:
        mode = -1
    return mode


def check_paths(paths: list) -> None:
    count = sum(1 for p in paths if p == "SKILL.md")
    if count != 1:
        raise contract("has no SKILL.md" if count == 0 else "has SKILL.md twice")
    seen: dict = {}
    for path in paths:
        if path == "SKILL.md":
            continue
        why = path_problem(path)
        if why:
            raise contract(f"names a file it may not: {why}")
        key = path.casefold()
        if key in seen:
            raise contract(f"has {shown(seen[key])} and {shown(path)}, one file on a "
                           "case-insensitive disk")
        seen[key] = path
    for key, path in seen.items():
        parts = key.split("/")
        for i in range(1, len(parts)):
            parent = "/".join(parts[:i])
            if parent in seen:
                raise contract(f"has {shown(seen[parent])} as a file and as the folder of "
                               f"{shown(path)}")


def parse_bundle(doc: dict, skill_id: str) -> dict:
    """The folder to write, after every check; raises Stop(CONTRACT or INTEGRITY)."""
    name = doc.get("install_name")
    if not valid_install_name(name):
        raise contract(f"names a folder no skill loader accepts: {shown(name)}")
    render = doc.get("render")
    if not isinstance(render, dict):
        raise contract("has no `render`")
    fmt = render.get("format")
    if isinstance(fmt, bool) or fmt not in FORMATS:
        raise contract(f"is format {shown(fmt)}; this plugin reads format "
                       f"{', '.join(map(str, FORMATS))} (update the plugin)")
    if render.get("variant") != "foreign":
        raise contract(f"is the {shown(render.get('variant'))} variant, not `foreign`")
    if doc.get("skill_id") != skill_id:
        raise contract(f"is of skill {shown(doc.get('skill_id'))}, not {skill_id}")
    version_id = doc.get("version_id")
    if not isinstance(version_id, str) or not version_id:
        raise contract("has no `version_id`")
    rows = doc.get("files")
    if not isinstance(rows, list):
        raise contract("has no `files` list")

    files = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise contract("has a `files` entry that is not an object")
        path = raw.get("path")
        if not isinstance(path, str) or not path:
            raise contract(f"has a file with no path: {shown(path)}")
        declared = raw.get("sha256")
        declared = declared.lower() if isinstance(declared, str) else ""
        if not SHA256_RE.fullmatch(declared):
            raise contract(f"declares {shown(path)} with sha256 {shown(raw.get('sha256'))}")
        mode = file_mode(raw.get("mode"))
        if mode not in MODES:
            raise contract(f"gives {shown(path)} mode {shown(raw.get('mode'))}; a file is "
                           "0644 or 0755")
        if raw.get("encoding") != "utf-8":
            raise contract(f"serves {shown(path)} as {shown(raw.get('encoding'))}, not utf-8")
        content = raw.get("content")
        if not isinstance(content, str):
            raise contract(f"serves {shown(path)} without text content")
        try:
            data = content.encode("utf-8")
        except UnicodeEncodeError:
            raise contract(f"serves {shown(path)} as text that is not valid UTF-8") from None
        files.append({"path": path, "sha256": declared, "mode": mode, "data": data})
    check_paths([f["path"] for f in files])

    bad = [f for f in files if hashlib.sha256(f["data"]).hexdigest() != f["sha256"]]
    if bad:
        detail = "; ".join(
            f"{shown(f['path'])}: received {hashlib.sha256(f['data']).hexdigest()[:12]}..., "
            f"declared {f['sha256'][:12]}..." for f in bad)
        raise Stop(INTEGRITY, "refused: the bytes received do not match the sha256 the "
                              f"registry declared ({detail}). Nothing was written.")
    skill_md = next(f for f in files if f["path"] == "SKILL.md")
    if not skill_md["data"].startswith(f"---\nname: {name}\n".encode("utf-8")):
        raise contract(f"has a SKILL.md whose `name:` is not its folder name {name}")

    unavailable = []
    for entry in doc.get("unavailable") or []:
        if isinstance(entry, dict):
            unavailable.append((shown(entry.get("path")), shown(entry.get("reason"), 200)))
    notes = [shown(n, 400) for n in doc.get("policy_notes") or [] if isinstance(n, str)]
    return {"install_name": name, "version_id": version_id, "files": files,
            "body_sha256": doc.get("body_sha256"), "unavailable": unavailable, "notes": notes}


# ── The folder on disk ──────────────────────────────────────────────────────────────


def executable(mode: int) -> bool:
    return bool(mode & 0o111)


def existing_entry(root: str, name: str):
    """The entry in ``root`` that is ``name`` on this disk (case-insensitively), or None."""
    try:
        entries = os.listdir(root)
    except FileNotFoundError:
        return None
    if name in entries:
        return name
    folded = [e for e in entries if e.casefold() == name.casefold()]
    return folded[0] if folded else None


def compare(folder: str, files: list) -> tuple:
    """(changed, missing, extra) between a folder on disk and the files to write."""
    want = {f["path"]: f for f in files}
    have: dict = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for n in list(dirnames):
            full = os.path.join(dirpath, n)
            if os.path.islink(full):
                have[os.path.relpath(full, folder).replace(os.sep, "/")] = None
        for n in filenames:
            if n in CLUTTER or n.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, n)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            if os.path.islink(full) or not os.path.isfile(full):
                have[rel] = None
                continue
            with open(full, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            have[rel] = (digest, executable(os.stat(full).st_mode))
    changed = []
    for path in sorted(set(want) & set(have)):
        f = want[path]
        got = have[path]
        if got is None or got[0] != f["sha256"] or (
                os.name != "nt" and got[1] != executable(f["mode"])):
            changed.append(path)
    return changed, sorted(set(want) - set(have)), sorted(set(have) - set(want))


def dir_mode() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return 0o777 & ~mask


def stage(staging: str, files: list) -> None:
    """Write the files into the (new, empty) staging folder and check them on disk."""
    real = os.path.realpath(staging)
    for f in files:
        full = os.path.join(staging, *f["path"].split("/"))
        if not os.path.realpath(full).startswith(real + os.sep):
            raise contract(f"names {shown(f['path'])}, which resolves outside the folder")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0))
        fd = os.open(full, flags, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(f["data"])
        os.chmod(full, f["mode"])
    for f in files:
        full = os.path.join(staging, *f["path"].split("/"))
        with open(full, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        if digest != f["sha256"]:
            raise Stop(INTEGRITY, f"refused: {shown(f['path'])} hashes to {digest[:12]}... on "
                                  "disk after writing. Nothing was installed.")
        if os.name != "nt" and stat.S_IMODE(os.stat(full).st_mode) != f["mode"]:
            raise Stop(INTEGRITY, f"refused: {shown(f['path'])} did not keep mode "
                                  f"{f['mode']:04o} on disk. Nothing was installed.")
    mode = dir_mode()
    for dirpath, _, _ in os.walk(staging):
        os.chmod(dirpath, mode)


def backup_path(project: str, entry: str) -> str:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = os.path.join(project, ".claude", "decimalai-backup", f"{entry}-{stamp}")
    path, n = base, 1
    while os.path.lexists(path):
        n += 1
        path = f"{base}-{n}"
    return path


# ── install ─────────────────────────────────────────────────────────────────────────


def parse_install_args(argv: list, text: str) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="registry.py install", add_help=False)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--project", default="")
    args, unknown = ap.parse_known_args(argv)
    if unknown:
        raise Stop(USAGE, f"unknown option {shown(unknown[0])}")
    refs = []
    for token in text.split():
        if token == "--yes":
            args.yes = True
        elif token == "--force":
            args.force = True
        else:
            refs.append(token)
    if not refs:
        raise Stop(USAGE, "usage: /decimalai:install <url_slug>  (find one with /decimalai:search)")
    if len(refs) > 1:
        raise Stop(USAGE, "one skill at a time: /decimalai:install <url_slug>")
    ref = refs[0]
    if len(ref) > MAX_REF or not REF_RE.fullmatch(ref):
        raise Stop(USAGE, f"refused: {shown(ref)} is not a url_slug or a skill id (letters, "
                          "digits, '.', '_' and '-', starting with a letter or digit). A "
                          "registry name such as owner/skill is not one; /decimalai:search "
                          "shows the url_slug to use.")
    args.ref = ref
    return args


def project_dir(raw: str) -> str:
    raw = raw.strip()
    if not raw or "${" in raw:
        raw = os.getcwd()
    if not os.path.isabs(raw) or not os.path.isdir(raw):
        raise Stop(USAGE, f"the project directory {shown(raw)} does not exist")
    return os.path.abspath(raw)


def trust_lines(rec: dict) -> list:
    bench = rec.get("benchmark_summary") if isinstance(rec.get("benchmark_summary"), dict) else {}
    lift = bench.get("pass_rate_delta_pts")
    lift = number(lift)
    lift_text = f"{lift:+g} pts pass rate" if lift is not None else "no measured lift"
    verdict = bench.get("verdict")
    return [
        f"skill: {shown(rec.get('name'))} (url_slug {shown(rec.get('url_slug'))}, id {rec['id']})",
        f"safety: {shown(rec.get('skill_safety') or 'unknown')} (scanner: "
        f"{shown(rec.get('safety_status') or 'unknown')}, intent review: "
        f"{shown(rec.get('intent_status') or 'unknown')})",
        f"benchmark: {shown(verdict) + ', ' if verdict else ''}{lift_text}",
    ]


def install(argv: list, text: str) -> int:
    args = parse_install_args(argv, text)
    project = project_dir(args.project)
    base = registry_base()
    root = os.path.join(project, ".claude", "skills")

    rec = get_json(f"{base}/api/v1/registry/skills/{urllib.parse.quote(args.ref, safe='')}",
                   f"skill {args.ref}")
    skill_id = rec.get("id")
    if not isinstance(skill_id, str) or not UUID_RE.fullmatch(skill_id):
        raise Stop(CONTRACT, "refused: the registry's record has no skill id. Nothing was written.")
    for line in trust_lines(rec):
        say(line)
    band = rec.get("skill_safety")
    if band == "blocked":
        raise Stop(REFUSED, "refused: the registry has blocked this skill. It will not be "
                            "installed.")
    if band != "passed" and not args.yes:
        raise Stop(CONFIRM, f"needs confirmation: the safety band is "
                            f"{shown(band or 'missing')}, not passed. Install only if the user "
                            "says yes (run again with --yes).")

    query = urllib.parse.urlencode({"formats": ",".join(map(str, FORMATS)),
                                    "channel": "plugin", "purpose": "pull"})
    doc = get_json(f"{base}/api/v1/registry/skills/{skill_id}/bundle?{query}",
                   f"the folder of {shown(rec.get('name'))}")
    folder = parse_bundle(doc, skill_id)
    name = folder["install_name"]
    target = os.path.join(root, name)

    for path in (os.path.join(project, ".claude"), root):
        if os.path.lexists(path) and not os.path.isdir(path):
            raise Stop(EXISTS, f"refused: {path} is not a directory")
    entry = existing_entry(root, name) if os.path.isdir(root) else None
    if entry is not None:
        current = os.path.join(root, entry)
        if os.path.islink(current) or not os.path.isdir(current):
            raise Stop(EXISTS, f"refused: {current} is a symlink or a file, not a skill "
                               "folder. Move it away first.")
        changed, missing, extra = compare(current, folder["files"])
        if entry == name and not (changed or missing or extra):
            say(f"already installed: {target}{os.sep} holds exactly these bytes; nothing changed.")
            return OK
        if not args.force:
            parts = [f"{label} {', '.join(shown(p) for p in paths[:8])}"
                     for label, paths in (("changed:", changed), ("missing:", missing),
                                          ("extra:", extra)) if paths]
            if entry != name:
                parts.insert(0, f"it is named {shown(entry)}")
            raise Stop(EXISTS, f"refused: {current}{os.sep} already exists and differs from "
                               f"the registry's folder ({'; '.join(parts)}). To replace it, "
                               "run again with --force: the current folder is moved to "
                               ".claude/decimalai-backup/ first.")

    created = [p for p in (os.path.join(project, ".claude"), root) if not os.path.lexists(p)]
    os.makedirs(root, exist_ok=True)
    staging, backup, done = None, None, False
    try:
        staging = tempfile.mkdtemp(prefix=f".{name}.partial-", dir=root)
        stage(staging, folder["files"])
        if entry is not None:
            backup = backup_path(project, entry)
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.move(os.path.join(root, entry), backup)
        try:
            os.rename(staging, target)
        except OSError as exc:
            if backup:
                shutil.move(backup, os.path.join(root, entry))
                backup = None
            raise Stop(EXISTS, f"refused: could not move the new folder into place ({exc}). "
                               "Nothing was installed.") from None
        done = True
    finally:
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        if not done:
            for path in reversed(created):      # only folders this run made, and only if empty
                try:
                    os.rmdir(path)
                except OSError:
                    pass

    say(f"installed: {target}{os.sep}  (version id {folder['version_id']})")
    width = max(len(f["path"]) for f in folder["files"])
    for f in folder["files"]:
        say(f"  {f['path'].ljust(width)}  {f['mode']:04o}  sha256 {f['sha256']}")
    for path, reason in folder["unavailable"]:
        say(f"not written: {path} ({reason})")
    for note in folder["notes"]:
        say(f"registry note: {note}")
    if backup:
        say(f"the previous folder was moved to {backup}{os.sep}")
    if isinstance(folder["body_sha256"], str):
        say(f"provenance: SKILL.md's metadata.decimalai-body-sha256 is {folder['body_sha256']}; "
            "the registry's ETag for this SKILL.md starts with the same hash")
    slug = install_ref(rec) or skill_id
    if os.path.exists(os.path.join(project, ".decimal", "skills.lock")) or \
            os.path.exists(os.path.join(project, ".decimal", "skills.toml")):
        say("note: this project manages skills with the decimalai CLI (.decimal/). This copy "
            f"is not in its lock; `decimalai skills add {slug}` installs it managed.")
    if os.path.isdir(os.path.join(project, ".agents", "skills", name)):
        say(f"note: .agents/skills/{name}/ holds this skill too; a session started with "
            "`claude --plugin-dir .agents` would load it twice.")
    say("This is an unmanaged copy: nothing records or updates it. For a locked install that "
        "`decimalai skills update` and `decimalai skills verify` look after, use "
        f"`decimalai skills add {slug}` (decimalai 0.15 or later).")
    return OK


# ── search ──────────────────────────────────────────────────────────────────────────


def cell(value: object, limit: int = 100) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = "".join(" " if unicodedata.category(c)[0] in "CZ" and c != " " else c for c in text)
    text = re.sub(r"\s+", " ", text).strip().replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def number(value: object):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def parse_search_args(text: str) -> tuple:
    tokens = text.split()
    words, category, sort = [], None, "recommended"
    i = 0
    while i < len(tokens):
        token = tokens[i]
        for flag in ("--category", "--sort"):
            if token == flag and i + 1 < len(tokens):
                value, i = tokens[i + 1], i + 1
                break
            if token.startswith(flag + "="):
                value = token[len(flag) + 1:]
                break
        else:
            words.append(token)
            i += 1
            continue
        if flag == "--category":
            category = value
        else:
            sort = value
        i += 1
    if sort not in SORTS:
        raise Stop(USAGE, f"--sort is one of {', '.join(SORTS)}, not {shown(sort)}")
    return " ".join(words), category, sort


def install_ref(item: dict):
    slug, sid = item.get("url_slug"), item.get("id")
    if isinstance(slug, str) and REF_RE.fullmatch(slug) and len(slug) <= MAX_REF:
        return slug
    if isinstance(sid, str) and UUID_RE.fullmatch(sid):
        return sid
    return None


def search(text: str) -> int:
    query, category, sort = parse_search_args(text)
    base = registry_base()
    params = {"q": query, "sort": sort, "limit": "10"}
    if category:
        params["category"] = category
    doc = get_json(f"{base}/api/v1/registry/skills?{urllib.parse.urlencode(params)}", "the search")
    items = [i for i in doc.get("items") or [] if isinstance(i, dict)]
    label = f"for {shown(query)}" if query else "(no query)"
    if not items:
        say(f"No skills matched {label}. Try a broader query.")
        return OK
    open_rows, blocked = [], []
    for item in items:
        (blocked if item.get("skill_safety") == "blocked" else open_rows).append(item)
    say(f"DecimalAI registry, {len(items)} result(s) {label}, sort {sort}"
        + (f", category {shown(category)}" if category else "") + ":")
    say()
    say("| install with | lands in | what it does | SkillScore | lift | safety | adoption |")
    say("|---|---|---|---|---|---|---|")
    for item in open_rows:
        ref = install_ref(item)
        name = item.get("install_name")
        desc = cell(item.get("description"))
        if isinstance(item.get("name"), str) and item.get("name") != item.get("url_slug"):
            desc = f"({cell(item.get('name'), 80)}) {desc}"
        eff = item.get("effectiveness") if isinstance(item.get("effectiveness"), dict) else {}
        score = number(eff.get("skill_score"))
        bench = item.get("benchmark_summary") if isinstance(item.get("benchmark_summary"), dict) else {}
        lift = number(bench.get("pass_rate_delta_pts"))
        agents = number(item.get("install_agents"))
        say("| " + " | ".join([
            f"`/decimalai:install {ref}`" if ref else "(not installable by name)",
            f"`.claude/skills/{name}/`" if valid_install_name(name) else "",
            desc,
            f"{score:.2f}" if score is not None else "New",
            f"{lift:+g} pts" if lift is not None else "",
            cell(item.get("skill_safety") or "unknown", 20),
            f"on {agents:g} agent{'s' if agents != 1 else ''}" if agents else "",
        ]) + " |")
    if blocked:
        say()
        say("Blocked, will not install (/decimalai:install refuses these):")
        for item in blocked:
            say(f"- {cell(item.get('url_slug') or item.get('name'), 80)}: scanner "
                f"{cell(item.get('safety_status') or 'unknown', 40)}, intent review "
                f"{cell(item.get('intent_status') or 'unknown', 40)}")
    say()
    say(f"View a skill at {APP}/skills/<url_slug>.")
    return OK


def main(argv: list) -> int:
    if not argv or argv[0] not in ("install", "search"):
        say(__doc__.strip().split("\n\n")[0] if __doc__ else "")
        return USAGE
    text = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
    try:
        return install(argv[1:], text) if argv[0] == "install" else search(text)
    except Stop as stop:
        say(stop.message)
        return stop.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
