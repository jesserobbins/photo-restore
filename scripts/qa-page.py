#!/usr/bin/env python3
"""Build a review page for a photo restoration: slider comparison, callout crops,
one verdict per photo, notes per callout.

The page is the instrument for the visual half of the QA checklist. It does not
judge anything; it collects a judgement and records it where an agent can read it.

Responses go to `qa/verdicts.jsonl`, append-only, one JSON object per line, so a
second pass adds to the record instead of replacing it.

Modes:
  --serve   (default) serve the page and accept verdicts over HTTP
  --static  write one self-contained HTML file and accept no network at all

Everything is embedded as base64. A run leaves two artifacts, the page and the
verdict log; nothing else, so cleanup has an unambiguous list.

Exit codes:
  0  page served and closed, or file written
  1  the review ended without a verdict being recorded
  2  usage or environment error -- nothing was written
"""

import argparse
import base64
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION = "2.1"

# A review page for a 460 MP archival upscale is the intended use, not a
# decompression bomb. Pillow would refuse it at ~179 MP.
from PIL import Image as _PIL

_PIL.MAX_IMAGE_PIXELS = None
PROG = f"photo-restore {VERSION}"
VERDICTS = "verdicts.jsonl"
FILES_MANIFEST = ".qa-page-files"
VERDICT_CHOICES = ("approve", "needs-work", "reject")
DISPLAY_WIDTH = 1400
CALLOUT_WIDTH = 360


def die(message):
    """Environment or usage failure: nothing was written. Exit code 2."""
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


HUMAN = sys.stdout  # swapped to stderr when --json owns stdout


def say(*args):
    print(*args, file=HUMAN)


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #

def slug(text):
    """Stable callout id: `Left eye` -> `left-eye`."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def parse_crop(spec):
    """Parse `LABEL:L,T,R,B` or `PHOTO:LABEL:L,T,R,B`."""
    parts = spec.split(":")
    if len(parts) == 2:
        photo, label, box = None, parts[0], parts[1]
    elif len(parts) == 3:
        photo, label, box = parts
    else:
        die(f"--crop wants LABEL:L,T,R,B or PHOTO:LABEL:L,T,R,B, got {spec!r}")
    coords = box.split(",")
    if len(coords) != 4:
        die(f"--crop box wants four comma-separated integers, got {box!r}")
    try:
        box = tuple(int(c) for c in coords)
    except ValueError:
        die(f"--crop box must be integers, got {box!r}")
    label = label.strip()
    if not label:
        die(f"--crop needs a label, got {spec!r}")
    if not slug(label):
        die(f"--crop label {label!r} has no usable characters for an id")
    return {"photo": photo.strip() if photo else None,
            "label": label, "id": slug(label), "box": box}


def resolve_entry_path(entry, project):
    """Find a manifest path without guessing twice about its base.

    finalize.py records whatever it was given, so an entry may be absolute, relative
    to the project, or relative to the project's parent. Trying the candidates in
    order beats prefixing blindly, which turns `grandma/source/x.jpg` into
    `grandma/grandma/source/x.jpg`.
    """
    path = Path(entry)
    if path.is_absolute():
        return path if path.exists() else None
    project = project.resolve()
    # The project first: a cwd-relative file that happens to share a name must not
    # win, or reviewing project B can show project A's photographs.
    bases = [project, project.parent, *project.parents]
    for base in bases:
        candidate = base / path
        if candidate.exists():
            return candidate
    cwd_candidate = path.resolve()
    try:
        cwd_candidate.relative_to(project)
    except ValueError:
        return None          # outside the project: not ours to trust
    return cwd_candidate if cwd_candidate.exists() else None


def pairs_from_manifest(project):
    """Pair each source with the outputs the finalizer recorded for it."""
    manifest = project / "manifest.json"
    if not manifest.exists():
        die(f"{manifest} not found; pass --pair SOURCE RENDER instead")
    try:
        data = json.loads(manifest.read_text())
    except ValueError as exc:
        die(f"{manifest} is not readable JSON: {exc}")

    pairs, seen = [], set()
    for asset in data.get("assets", []):
        source, output = asset.get("source"), asset.get("output")
        if not source or not output:
            continue
        if asset.get("verification") == "fail":
            # A failed verification is not something to review as a candidate.
            continue
        src, out = resolve_entry_path(source, project), resolve_entry_path(output, project)
        if not src or not out:
            continue
        key = (str(src.resolve()), str(out.resolve()))
        if key in seen:
            continue
        seen.add(key)
        pairs.append({"photo": out.name, "source_stem": src.stem,
                      "source": src, "render": out,
                      "note": asset.get("verification", "")})
    if not pairs:
        die(
            "no reviewable pairs in the manifest (no successful finalize entries, or "
            "the files are gone). Run finalize.py first, or pass --pair."
        )
    return pairs


def resolve_pairs(args):
    pairs = []
    for spec in args.pair or []:
        if len(spec) != 2:
            die("--pair takes exactly two paths: SOURCE RENDER")
        src, out = Path(spec[0]), Path(spec[1])
        if not src.exists():
            die(f"source not found: {src}")
        if not out.exists():
            die(f"render not found: {out}")
        pairs.append({"photo": out.name, "source_stem": src.stem,
                      "source": src, "render": out, "note": ""})
    if pairs:
        return pairs
    if args.project:
        return pairs_from_manifest(args.project)
    die("nothing to review: pass --project DIR or --pair SOURCE RENDER")


def pair_key(pair):
    """A verdict key derived from the pair alone.

    It must not depend on which other pairs are in the run: reviewing `a/render.png`
    today and `b/render.png` tomorrow would otherwise hand the same key to different
    photographs, so one would inherit the other's verdict and notes.

    A project writes its results to `output/`, so the filename alone is unique and
    readable there. Anywhere else the directory is part of the key, which keeps
    `a/render.png` and `b/render.png` apart without depending on what else is in the
    run.
    """
    render = Path(pair["render"]).resolve()
    if render.parent.name == "output":
        return render.name
    return f"{render.parent.name}/{render.name}"


def assign_keys(pairs):
    for pair in pairs:
        pair["photo"] = pair_key(pair)
    return pairs


def callouts_for(crops, pairs):
    """Attach callouts to photo keys, expanding the bare form to every photo.

    A crop may name the source stem, which fans out to every output of that source,
    or the output stem, which selects one variant.
    """
    keys = [pair["photo"] for pair in pairs]
    alias = {}
    for pair in pairs:
        alias.setdefault(pair["source_stem"], []).append(pair["photo"])
        alias.setdefault(pair["photo"], []).append(pair["photo"])
        alias.setdefault(Path(pair["photo"]).stem, []).append(pair["photo"])
    by_photo = {}
    for crop in crops:
        if crop["photo"]:
            targets = alias.get(crop["photo"])
            if not targets:
                die(f"--crop names photo {crop['photo']!r}, which is not in this run")
        else:
            targets = list(keys)
        for photo in targets:
            entry = dict(crop, photo=photo)
            bucket = by_photo.setdefault(photo, {})
            if entry["id"] in bucket and bucket[entry["id"]]["box"] != entry["box"]:
                die(
                    f"two callouts for {photo} slug to the same id {entry['id']!r} with "
                    "different boxes; label them differently"
                )
            bucket[entry["id"]] = entry
    return by_photo


# --------------------------------------------------------------------------- #
# images
# --------------------------------------------------------------------------- #

def displayed_size(path):
    """Dimensions as a viewer shows them.

    Pillow's TIFF plugin already swaps the reported size for orientations 5-8, so
    applying the orientation again would read a portrait scan as landscape. Every
    other format reports raw dimensions and needs the swap.
    """
    from PIL import Image

    with Image.open(path) as im:
        raw = (im.width, im.height)
        orientation = im.getexif().get(274)
        if (im.format or "").upper() == "TIFF":
            return raw
    if orientation in (5, 6, 7, 8):
        return raw[1], raw[0]
    return raw


def readable_image(path, workdir):
    """A path Pillow can open, decoding HEIC through a system tool if needed."""
    from PIL import Image

    try:
        with Image.open(path):
            return path
    except Exception:
        pass
    if path.suffix.lower() not in {".heic", ".heif", ".hif", ".avif"}:
        raise SystemExit(f"cannot read {path}")
    import hashlib

    digest = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:8]
    target = workdir / f"{slug(path.stem)}-{digest}.png"
    for tool, argv in (
        ("magick", ["magick", str(path), str(target)]),
        ("sips", ["sips", "-s", "format", "png", str(path), "--out", str(target)]),
    ):
        if shutil.which(tool) and subprocess.run(argv, capture_output=True).returncode == 0 \
                and target.exists():
            return target
    raise SystemExit(
        f"cannot read {path.name}: Pillow has no HEIC decoder and neither ImageMagick "
        "nor sips is available"
    )


def open_display(path, box=None):
    """Yield (bytes, width, height) for display, cropping box in source pixels."""
    from PIL import Image, ImageOps

    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if box:
            # Callout crops are shown nearest-neighbour at an integer scale: a
            # smooth resample invents detail, which is the thing being reviewed.
            l, t, r, b = box
            if not (0 <= l < r <= im.width and 0 <= t < b <= im.height):
                return None
            crop = im.crop(box)
            factor = max(1, CALLOUT_WIDTH // max(1, crop.width))
            crop = crop.resize((crop.width * factor, crop.height * factor),
                               Image.Resampling.NEAREST)
            return encode_png(crop), crop.width, crop.height
        if im.width > DISPLAY_WIDTH:
            height = round(im.height * DISPLAY_WIDTH / im.width)
            im = im.resize((DISPLAY_WIDTH, height), Image.Resampling.LANCZOS)
        return encode_png(im), im.width, im.height


def encode_png(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_pairs(pairs, callouts, prior, workdir):
    from PIL import Image

    built = []
    for pair in pairs:
        src, out = readable_image(pair["source"], workdir), readable_image(pair["render"], workdir)
        a_disp = displayed_size(src)
        b_disp = displayed_size(out)
        # Relative difference, not absolute: comparing raw ratios rejects a correct
        # wide pair while waving through a tall one that differs by more than 0.5%.
        a_ratio = a_disp[0] / a_disp[1]
        b_ratio = b_disp[0] / b_disp[1]
        if abs(a_ratio / b_ratio - 1) > 0.005:
            die(
                f"{src.name} and {out.name} differ in aspect ratio by more than 0.5%; "
                "that is a crop, and the slider would compare different frames"
            )
        source_img = open_display(src)
        render_img = open_display(out)
        if not source_img or not render_img:
            die(f"could not read one of {src} / {out}")
        scale = b_disp[0] / a_disp[0]

        tiles = []
        for callout in callouts.get(pair["photo"], {}).values():
            l, t, r, b = callout["box"]
            render_box = (round(l * scale), round(t * scale),
                          round(r * scale), round(b * scale))
            before = open_display(src, (l, t, r, b))
            after = open_display(out, render_box)
            if not before or not after:
                die(
                    f"callout {callout['id']!r} box {callout['box']} falls outside "
                    f"{src.name} ({a_disp[0]}x{a_disp[1]})"
                )
            tiles.append({
                "id": callout["id"],
                "label": callout["label"],
                "box": list(callout["box"]),
                "before": before[0],
                "after": after[0],
                "before_note": f"{callout['box'][2] - callout['box'][0]}x"
                               f"{callout['box'][3] - callout['box'][1]} px of source",
            })

        built.append({
            "photo": pair["photo"],
            "anchor": slug(pair["photo"]) or "photo",
            "source_name": src.name,
            "render_name": out.name,
            "verification": pair.get("note", ""),
            "source": source_img[0],
            "render": render_img[0],
            "prior": prior.get(pair["photo"]),
            "callouts": tiles,
        })
    return built


# --------------------------------------------------------------------------- #
# verdict log
# --------------------------------------------------------------------------- #

def verdict_path(out_dir):
    return Path(out_dir) / VERDICTS


def read_verdicts(path):
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            print(f"warning: {path}:{number} is not valid JSON; skipped", file=sys.stderr)
    return records


def order_key(record):
    """Pass first, then timestamp.

    Sorting on timestamp alone lets an older approval outrank a newer rejection
    when a record arrives without one, and mixed timezone offsets sort wrongly as
    strings. Pass is the reviewer's own ordering and is always an integer.
    """
    stamp = record.get("ts")
    when = 0.0
    if isinstance(stamp, str):
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            # Compare instants, not strings: 10:00-07:00 is later than 16:00Z, and
            # string order says the opposite.
            when = parsed.timestamp() if parsed.tzinfo else parsed.replace(
                tzinfo=datetime.now().astimezone().tzinfo).timestamp()
        except ValueError:
            when = 0.0
    return (record.get("pass") or 0, when)


def latest_by_photo(records):
    """Most recent verdict per photo, ordered by pass then time."""
    latest = {}
    for record in sorted(records, key=order_key):
        photo = record.get("photo")
        if isinstance(photo, str) and record.get("verdict") in VERDICT_CHOICES:
            latest[photo] = record
    return latest


def validate_record(record, line_no=None):
    where = f"line {line_no}: " if line_no else ""
    if not isinstance(record, dict):
        return f"{where}not a JSON object"
    photo = record.get("photo")
    if not isinstance(photo, str) or not photo.strip():
        return f"{where}photo must be a non-empty string"
    if "ts" in record and not isinstance(record.get("ts"), str):
        return f"{where}ts must be a string when present"
    if record.get("pass") is not None and not isinstance(record.get("pass"), int):
        return f"{where}pass must be an integer"
    if record.get("verdict") not in VERDICT_CHOICES:
        return f"{where}verdict must be one of {', '.join(VERDICT_CHOICES)}"
    callouts = record.get("callouts") or {}
    if not isinstance(callouts, dict):
        return f"{where}callouts must be an object keyed by id"
    for key, value in callouts.items():
        if not isinstance(value, str):
            return f"{where}callout {key!r} must be a string"
    return None


def append_record(path, record):
    """Append one line under an exclusive lock. Never rewrites what is there."""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0, os.SEEK_END)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle, fcntl.LOCK_UN)
    return record


def next_pass(records):
    passes = [r.get("pass") for r in records if isinstance(r.get("pass"), int)]
    return max(passes, default=0) + 1


def stamp(photo, verdict, notes, pass_no):
    record = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pass": pass_no,
        "photo": photo,
        "verdict": verdict,
    }
    notes = {k: v.strip() for k, v in (notes or {}).items() if v and v.strip()}
    if notes:
        record["callouts"] = notes
    return record


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--ink:#1b1b1b;--muted:#6b6b6b;--line:#d8d8d8;--bg:#faf9f7;--card:#fff;
--ok:#1a7f37;--warn:#9a6700;--bad:#b42318;--accent:#8a5a00}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif}
header{max-width:1500px;margin:0 auto 20px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px}
nav{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5;
border-bottom:1px solid var(--line);margin-bottom:16px}
nav a{color:var(--accent);text-decoration:none;margin-right:14px;font-size:13px}
.card{max-width:1500px;margin:0 auto 28px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:16px}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.photo{font-weight:650}
.meta{color:var(--muted);font-size:12px}
.slider{position:relative;margin:12px 0 6px;border-radius:8px;overflow:hidden;
background:#111;user-select:none;cursor:ew-resize;line-height:0}
.slider img{display:block;width:100%;height:auto}
.slider .after{position:absolute;inset:0;clip-path:inset(0 0 0 50%)}
.handle{position:absolute;top:0;bottom:0;width:2px;background:#fff;left:50%;
box-shadow:0 0 0 1px rgba(0,0,0,.35)}
.handle::after{content:"";position:absolute;top:50%;left:50%;width:26px;height:26px;
margin:-13px 0 0 -13px;border-radius:50%;background:#fff;border:1px solid rgba(0,0,0,.35)}
.tag{position:absolute;top:8px;font-size:11px;letter-spacing:.04em;text-transform:uppercase;
background:rgba(0,0,0,.62);color:#fff;padding:2px 7px;border-radius:4px}
.tag.l{left:8px}.tag.r{right:8px}
input[type=range]{width:100%;margin:0 0 4px}
.callouts{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px}
.tile{border:1px solid var(--line);border-radius:8px;padding:10px;background:#fcfcfb;
flex:1 1 340px;max-width:520px}
.tile h3{margin:0 0 2px;font-size:13px}
.tile .id{color:var(--muted);font-size:11px;font-family:ui-monospace,monospace}
.pair{display:flex;gap:8px;margin:8px 0 6px}
.pair figure{margin:0;flex:1}
.pair img{width:100%;height:auto;border-radius:4px;image-rendering:pixelated;
background:#111;display:block}
.pair figcaption{font-size:11px;color:var(--muted);margin-top:3px}
.tile textarea{width:100%;min-height:42px;resize:vertical;font:13px/1.4 inherit;
border:1px solid var(--line);border-radius:6px;padding:6px}
.actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px}
button{font:14px inherit;padding:7px 13px;border-radius:7px;border:1px solid var(--line);
background:#fff;cursor:pointer}
button:hover{background:#f2f0ec}
button.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
button.primary:hover{background:#000}
.verdicts{display:flex;gap:6px;flex-wrap:wrap}
.verdicts label{display:flex;align-items:center;gap:5px;padding:5px 10px;border:1px solid var(--line);
border-radius:999px;cursor:pointer;font-size:13px;background:#fff}
.verdicts input{accent-color:var(--accent)}
.verdicts label[data-v=approve]{color:var(--ok)}
.verdicts label[data-v=needs-work]{color:var(--warn)}
.verdicts label[data-v=reject]{color:var(--bad)}
.prior{font-size:12px;color:var(--muted);margin-top:8px}
.status{font-size:12px;color:var(--muted)}
textarea.log{width:100%;min-height:120px;font:12px/1.4 ui-monospace,monospace;
border:1px solid var(--line);border-radius:8px;padding:8px;margin-top:8px}
footer{max-width:1500px;margin:0 auto;padding:18px 0 60px;border-top:1px solid var(--line)}
.done{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.hint{color:var(--muted);font-size:12px}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="sub">__SUBMIT__</div>
</header>
<nav>__NAV__</nav>
<main id="cards">__CARDS__</main>
<footer>
  <div class="done">
    __DONE__
    <span class="hint">__HINT__</span>
  </div>
  <textarea class="log" id="log" readonly aria-label="Recorded verdicts"></textarea>
</footer>
<script>
const MODE = "__MODE__";
const TOKEN = "__TOKEN__";
const PASS = __PASS__;
let inFlight = 0;      // record requests still open
const failed = new Map();  // photo -> the line the server never accepted
const NEWLINE = String.fromCharCode(10);  // avoids escape nesting in this template

function renderLog(){
  document.getElementById('log').value = Array.from(failed.values()).join(NEWLINE);
}

function setSlider(root, ratio){
  ratio = Math.min(1, Math.max(0, ratio));
  const after = root.querySelector('.after');
  const handle = root.querySelector('.handle');
  after.style.clipPath = `inset(0 0 0 ${ratio * 100}%)`;
  handle.style.left = `${ratio * 100}%`;
  const range = root.querySelector('input[type=range]');
  if (range) range.value = Math.round(ratio * 1000);
  else console.warn('slider has no range input');
}

document.querySelectorAll('.slider').forEach(root => {
  const range = root.querySelector('input[type=range]');
  const paint = clientX => {
    const box = root.getBoundingClientRect();
    setSlider(root, (clientX - box.left) / box.width);
  };
  let dragging = false;
  root.addEventListener('pointerdown', e => { dragging = true; root.setPointerCapture(e.pointerId); paint(e.clientX); });
  root.addEventListener('pointermove', e => { if (dragging) paint(e.clientX); });
  root.addEventListener('pointerup', () => { dragging = false; });
  root.addEventListener('pointercancel', () => { dragging = false; });
  if (range) range.addEventListener('input', () => setSlider(root, range.value / 1000));
  // Arrow keys work because the range input is focusable; the visual follows it.
  setSlider(root, 0.5);
});

function payloadFor(card){
  const photo = card.dataset.photo;
  const checked = card.querySelector('.verdicts input:checked');
  const notes = {};
  card.querySelectorAll('.tile').forEach(tile => {
    const value = tile.querySelector('textarea').value.trim();
    if (value) notes[tile.dataset.id] = value;
  });
  return {photo, verdict: checked ? checked.value : null, callouts: notes};
}

function showStatus(card, text){
  card.querySelector('.status').textContent = text;
}

async function record(card){
  const payload = payloadFor(card);
  if (!payload.verdict){
    showStatus(card, 'choose approve, needs-work, or reject first');
    return;
  }
  const record = {ts: new Date().toISOString(), pass: PASS, photo: payload.photo,
                  verdict: payload.verdict};
  if (Object.keys(payload.callouts).length) record.callouts = payload.callouts;
  const line = JSON.stringify(record);

  if (MODE === 'serve'){
    inFlight++;
    try {
      const response = await fetch(`/${TOKEN}/verdicts`, {method:'POST',
        headers:{'Content-Type':'application/json'}, body: line});
      if (!response.ok) throw new Error(await response.text());
      // Acknowledged lines are already on disk; only failures need the log, or the
      // page would later claim its own recorded verdicts were never sent.
      showStatus(card, `recorded ${payload.verdict} (pass ${PASS})`);
      // Only the line that just succeeded is cleared: an older pending request
      // failing afterwards must not resurrect a stale recovery line either.
      if (failed.get(payload.photo) === line) { failed.delete(payload.photo); renderLog(); }
    } catch (err) {
      showStatus(card, 'could not record: ' + err.message + ' -- the line is in the log below');
      // One line per photo, so a retry that succeeds supersedes the stale failure.
      failed.set(payload.photo, line);
      renderLog();
    } finally {
      inFlight--;
    }
  } else {
    showStatus(card, `copied ${payload.verdict} to the log below; save it when done`);
    failed.set(payload.photo, line);
    renderLog();
  }
}

function copyLog(){
  const log = document.getElementById('log');
  if (!log.value) return;
  log.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  if (!ok && navigator.clipboard) {
    navigator.clipboard.writeText(log.value).catch(() => {});
  }
  log.setSelectionRange(0, log.value.length);
}

function downloadLog(){
  const log = document.getElementById('log');
  if (!log.value) return;
  const blob = new Blob([log.value + '\\n'], {type:'application/x-ndjson'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'verdicts.jsonl';
  a.click();
  URL.revokeObjectURL(a.href);
}

async function done(){
  const log = document.getElementById('log');
  const hint = document.querySelector('.hint');
  // A verdict posted a moment before Done must not be lost to a closing server.
  const deadline = Date.now() + 5000;
  while (inFlight > 0 && Date.now() < deadline){
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (inFlight > 0){
    hint.textContent = 'a verdict is still being sent; press Done again in a moment';
    return;
  }
  if (MODE === 'serve'){
    let closed = false;
    try {
      const response = await fetch(`/${TOKEN}/done`, {method:'POST'});
      closed = response.ok;
    } catch (e) { closed = false; }
    if (closed && failed.size === 0){
      document.body.innerHTML = '<p style="padding:40px;font:16px system-ui">Review closed. ' +
        'The terminal has the summary.</p>';
    } else if (!closed){
      // The server never heard us. Keep the page and the log: the textarea may be
      // the only copy of a verdict.
      log.scrollIntoView({behavior:'smooth'});
      log.select();
      hint.textContent =
        'Could not reach the server. The log below is the only copy: copy or download it, ' +
        'then import it with --import.';
    } else {
      log.scrollIntoView({behavior:'smooth'});
      hint.textContent =
        'Some lines were not sent to the server. Copy or download them, then import.';
    }
  } else {
    log.scrollIntoView({behavior:'smooth'});
  }
}

// Someone reading four photographs carefully may not click for a while. A pulse
// every minute keeps the server's idle timeout from closing a live review.
if (MODE === 'serve') setInterval(() => { fetch(`/${TOKEN}/ping`).catch(() => {}); }, 60000);

document.querySelectorAll('[data-action=record]').forEach(b =>
  b.addEventListener('click', () => record(b.closest('.card'))));
document.querySelectorAll('[data-action=copy]').forEach(b => b.addEventListener('click', copyLog));
document.querySelectorAll('[data-action=download]').forEach(b => b.addEventListener('click', downloadLog));
document.querySelectorAll('[data-action=done]').forEach(b => b.addEventListener('click', done));
</script>
</body>
</html>
"""

CARD = """<section class="card" id="p-__ANCHOR__" data-photo="__PHOTO__">
  <div class="head">
    <div>
      <div class="photo">__PHOTO__</div>
      <div class="meta">__SRC__ → __OUT__ __VERIFIED__</div>
    </div>
  </div>
  <div class="slider">
    <img class="before" src="__BEFORE__" alt="source: __SRC__">
    <img class="after" src="__AFTER__" alt="restored: __OUT__">
    <span class="tag l">source</span>
    <span class="tag r">restored</span>
    <div class="handle"></div>
    <input type="range" min="0" max="1000" value="500" aria-label="comparison position">
  </div>
  <div class="callouts">__TILES__</div>
  <div class="actions">
    <div class="verdicts">
      <label data-v="approve"><input type="radio" name="__GROUP__" value="approve"> approve</label>
      <label data-v="needs-work"><input type="radio" name="__GROUP__" value="needs-work"> needs work</label>
      <label data-v="reject"><input type="radio" name="__GROUP__" value="reject"> reject</label>
    </div>
    <button data-action="record">Record</button>
    <span class="status"></span>
  </div>
  <div class="prior">__PRIOR__</div>
</section>"""

TILE = """<div class="tile" data-id="__ID__">
  <h3>__LABEL__</h3>
  <div class="id">__ID__ · __BEFORE_NOTE__</div>
  <div class="pair">
    <figure><img src="__BEFORE__" alt="source detail: __LABEL__"><figcaption>source</figcaption></figure>
    <figure><img src="__AFTER__" alt="restored detail: __LABEL__"><figcaption>restored</figcaption></figure>
  </div>
  <textarea placeholder="what changed, if anything" aria-label="note for __ID__">__NOTE__</textarea>
</div>"""


def render_page(title, pairs, mode, token, pass_no, submit_line, hint):
    cards, nav = [], []
    for index, pair in enumerate(pairs):
        tiles = []
        for tile in pair["callouts"]:
            prior_note = ""
            if pair.get("prior"):
                prior_note = (pair["prior"].get("callouts") or {}).get(tile["id"], "")
            tiles.append(
                TILE.replace("__ID__", escape(tile["id"]))
                    .replace("__LABEL__", escape(tile["label"]))
                    .replace("__BEFORE_NOTE__", tile["before_note"])
                    .replace("__BEFORE__", tile["before"])
                    .replace("__AFTER__", tile["after"])
                    .replace("__NOTE__", escape(prior_note))
            )
        prior = "no verdict recorded yet"
        if pair.get("prior"):
            verdict = pair["prior"].get("verdict")
            when = pair["prior"].get("ts", "")[:16].replace("T", " ")
            count = len(pair["prior"].get("callouts") or {})
            prior = (f"previous pass ({escape(when)}): <strong>{escape(verdict)}</strong>"
                     + (f", {count} callout note{'s' if count != 1 else ''}" if count else ""))
        verified = f"· finalizer said {pair['verification']}" if pair["verification"] else ""
        card = CARD.replace("__PHOTO__", escape(pair["photo"]))
        # Every value that reaches the markup is escaped: a filename is data, not
        # HTML. An unescaped name would let a photo label run script in a page that
        # holds the owner's photographs.
        card = (card.replace("__ANCHOR__", escape(pair["anchor"]))
                    .replace("__GROUP__", f"v{index}")
                    .replace("__SRC__", escape(pair["source_name"]))
                    .replace("__OUT__", escape(pair["render_name"]))
                    .replace("__VERIFIED__", escape(verified))
                    .replace("__BEFORE__", pair["source"])
                    .replace("__AFTER__", pair["render"])
                    .replace("__TILES__", "".join(tiles) or
                             '<div class="hint">no callouts for this photo</div>')
                    .replace("__PRIOR__", prior))
        cards.append(card)
        nav.append(f'<a href="#p-{escape(pair["anchor"])}">{escape(pair["photo"])}</a>')

    # Copy and Download belong in both modes: a failed POST leaves the log as the
    # only copy of a verdict, and serve mode must be able to hand it back.
    done_button = ('<button data-action="download">Download verdicts.jsonl</button>'
                   '<button data-action="copy">Copy to clipboard</button>'
                   '<button class="primary" data-action="done">'
                   + ("Done — close review" if mode == "serve" else "Finish")
                   + "</button>")

    return (PAGE.replace("__TITLE__", escape(title))
                .replace("__SUBMIT__", escape(submit_line))
                .replace("__NAV__", " ".join(nav))
                .replace("__CARDS__", "\n".join(cards))
                .replace("__DONE__", done_button)
                .replace("__HINT__", escape(hint))
                .replace("__MODE__", mode)
                .replace("__TOKEN__", token)
                .replace("__PASS__", str(pass_no)))


def escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# --------------------------------------------------------------------------- #
# serving
# --------------------------------------------------------------------------- #

class ReviewServer:
    def __init__(self, html, token, out_dir, pass_no, host, port, idle_timeout):
        self.html = html
        self.token = token
        self.out_dir = Path(out_dir)
        self.pass_no = pass_no
        self.host = host
        self.port = port
        self.idle_timeout = idle_timeout
        self.recorded = []
        self.finished = threading.Event()
        self.last_activity = time.time()
        self.server = None

    def build(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass  # keep the terminal useful for the summary

            def _authorised(self):
                return urlparse(self.path).path.startswith(f"/{outer.token}/")

            def _send(self, code, body=b"", content_type="text/plain; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self):
                path = urlparse(self.path).path
                outer.last_activity = time.time()
                if not self._authorised():
                    self._send(404, b"not found")
                    return
                if path.rstrip("/") == f"/{outer.token}":
                    self._send(200, outer.html.encode(), "text/html; charset=utf-8")
                elif path == f"/{outer.token}/ping":
                    self._send(200, b"pong")
                elif path == f"/{outer.token}/verdicts":
                    body = json.dumps(outer.recorded).encode()
                    self._send(200, body, "application/json")
                else:
                    self._send(404, b"not found")

            def do_POST(self):
                path = urlparse(self.path).path
                outer.last_activity = time.time()
                if not self._authorised():
                    self._send(404, b"not found")
                    return
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode() if length else ""
                if path == f"/{outer.token}/done":
                    self._send(200, b"closing")
                    outer.finished.set()
                    return
                if path != f"/{outer.token}/verdicts":
                    self._send(404, b"not found")
                    return
                try:
                    record = json.loads(raw)
                except ValueError:
                    self._send(400, b"not JSON")
                    return
                problem = validate_record(record)
                if problem:
                    self._send(400, problem.encode())
                    return
                record["pass"] = outer.pass_no
                record["ts"] = (record.get("ts") or
                                datetime.now().astimezone().isoformat(timespec="seconds"))
                append_record(verdict_path(outer.out_dir), record)
                outer.recorded.append(record)
                self._send(200, b"recorded")

        try:
            self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        except OSError as exc:
            die(f"cannot listen on {self.host}:{self.port}: {exc}")
        self.port = self.server.server_address[1]
        return self.server

    def run(self):
        if self.server is None:
            self.build()
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        try:
            while not self.finished.is_set():
                if self.idle_timeout and time.time() - self.last_activity > self.idle_timeout:
                    print("idle timeout reached; closing the review", file=sys.stderr)
                    break
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("interrupted; closing the review", file=sys.stderr)
        finally:
            self.server.shutdown()
            self.server.server_close()
        return self.recorded


def lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            return probe.getsockname()[0]
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# cleanup
# --------------------------------------------------------------------------- #

def write_files_manifest(out_dir, page_path):
    """Accumulate, so a second pass does not orphan the first pass's page."""
    listing = Path(out_dir) / FILES_MANIFEST
    generated = []
    if listing.exists():
        try:
            generated = list(json.loads(listing.read_text()).get("generated", []))
        except ValueError:
            generated = []
    absolute = str(Path(page_path).resolve())
    if absolute not in generated:
        generated.append(absolute)
    listing.write_text(json.dumps({"generated": generated, "version": PROG}, indent=2) + "\n")


def clean(out_dir, include_verdicts):
    out_dir = Path(out_dir)
    listing = out_dir / FILES_MANIFEST
    removed = []
    if listing.exists():
        try:
            for path in json.loads(listing.read_text()).get("generated", []):
                p = Path(path)
                if p.exists():
                    p.unlink()
                    removed.append(str(p))
        except ValueError:
            print(f"warning: {listing} is unreadable; not removing anything", file=sys.stderr)
        listing.unlink()
    if include_verdicts:
        target = verdict_path(out_dir)
        if target.exists():
            target.unlink()
            removed.append(str(target))
    elif verdict_path(out_dir).exists():
        say(f"kept {verdict_path(out_dir)} (pass --verdicts to remove it too)")
    if not removed:
        say("nothing to remove")
    for path in removed:
        say(f"removed {path}")
    return removed


def import_file(path, out_dir, records):
    path = Path(path)
    if not path.exists():
        die(f"--import file not found: {path}")
    pass_no = next_pass(records)
    # Validate every line before writing any of them: a half-imported file would
    # leave the log in a state nobody asked for.
    staged = []
    explicit = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            die(f"{path}:{number} is not valid JSON")
        problem = validate_record(record, number)
        if problem:
            die(f"{path}: {problem}")
        record["pass"] = pass_no
        staged.append(record)
        if record.get("ts"):
            explicit.append((len(staged), record["ts"]))
    # An unstamped record must sit where the file puts it. Stamping it "now" lets
    # it outrank an explicit older timestamp that follows it, turning a correction
    # into the stale verdict.
    for index, record in enumerate(staged, 1):
        if record.get("ts"):
            continue
        later = next((ts for pos, ts in explicit if pos > index), None)
        if later:
            try:
                record["ts"] = (datetime.fromisoformat(later.replace("Z", "+00:00"))
                                - timedelta(microseconds=index)).isoformat()
                continue
            except ValueError:
                pass
        earlier = next((ts for pos, ts in reversed(explicit) if pos < index), None)
        try:
            base = (datetime.fromisoformat(earlier.replace("Z", "+00:00"))
                    if earlier else datetime.now().astimezone())
            record["ts"] = (base + timedelta(microseconds=index)).isoformat()
        except ValueError:
            record["ts"] = datetime.now().astimezone().isoformat()
    for record in staged:
        append_record(verdict_path(out_dir), record)
    added = len(staged)
    say(f"imported {added} verdict{'s' if added != 1 else ''} into {verdict_path(out_dir)}")
    return added


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--project", type=Path,
                   help="Project directory; pairs are read from its manifest.json")
    p.add_argument("--pair", action="append", nargs=2, metavar=("SOURCE", "RENDER"),
                   help="Review one pair; repeatable, and ignores the manifest")
    p.add_argument("--crop", action="append", default=[], metavar="SPEC",
                   help="LABEL:L,T,R,B (all photos) or PHOTO:LABEL:L,T,R,B. "
                        "Coordinates are source pixels")
    p.add_argument("--out-dir", type=Path, help="Where the page and verdicts live "
                                               "(default: <project>/qa or ./qa)")
    p.add_argument("--static", action="store_true",
                   help="Write a self-contained HTML file instead of serving")
    p.add_argument("--host", default="127.0.0.1",
                   help="Bind address (default 127.0.0.1; use 0.0.0.0 for Codex's browser)")
    p.add_argument("--port", type=int, default=0, help="Port (default: pick a free one)")
    p.add_argument("--open", action="store_true", help="Open the page in a browser if one is available")
    p.add_argument("--idle-timeout", type=int, default=1800,
                   help="Close an abandoned review after N seconds (default 1800, 0 disables)")
    p.add_argument("--import", dest="import_from", type=Path, metavar="FILE",
                   help="Validate and append verdicts downloaded in static mode")
    p.add_argument("--clean", action="store_true", help="Remove files this script generated")
    p.add_argument("--verdicts", action="store_true",
                   help="With --clean, also remove verdicts.jsonl (ask first)")
    p.add_argument("--json", action="store_true", help="Emit a summary as JSON")
    p.add_argument("--version", action="version", version=PROG)
    return p


def main():
    # An agent reads this output through a pipe, where Python would otherwise hold
    # the URL in a buffer until the blocking server exits.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    args = build_parser().parse_args()
    global HUMAN
    if args.json:
        HUMAN = sys.stderr  # stdout belongs to the JSON document

    out_dir = args.out_dir or (args.project / "qa" if args.project else Path("qa"))
    records = read_verdicts(verdict_path(out_dir))

    if args.clean:
        removed = clean(out_dir, args.verdicts)
        if args.json:
            print(json.dumps({"mode": "clean", "removed": removed}, indent=2))
        return 0

    if args.import_from:
        added = import_file(args.import_from, out_dir, records)
        if args.json:
            print(json.dumps({"mode": "import", "imported": added,
                              "verdicts": str(verdict_path(out_dir))}, indent=2))
        return 0 if added else 1

    pairs = assign_keys(resolve_pairs(args))
    callouts = callouts_for([parse_crop(spec) for spec in args.crop], pairs)
    prior = latest_by_photo(records)
    out_dir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(dir=out_dir, prefix=".qa-page-"))
    try:
        built = build_pairs(pairs, callouts, prior, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    pass_no = next_pass(records)
    token = secrets.token_urlsafe(12)
    title = f"Review · pass {pass_no}"

    if args.static:
        submit_line = ("No server: Record copies a line into the log below. "
                       "Download it, then `--import verdicts.jsonl`.")
        hint = "Static page: nothing is sent anywhere."
        html = render_page(title, built, "static", token, pass_no, submit_line, hint)
        page = out_dir / f"review-pass{pass_no}.html"
        page.write_text(html)
        write_files_manifest(out_dir, page)
        summary = {"mode": "static", "page": str(page), "pairs": len(built),
                   "pass": pass_no, "callouts": sum(len(p["callouts"]) for p in built),
                   "verdicts": str(verdict_path(out_dir))}
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            say(f"page: {page}")
            say(f"pairs: {len(built)}  callouts: {summary['callouts']}  pass: {pass_no}")
            say(f"open it, then import what you record: "
                f"--import {out_dir / 'verdicts.jsonl'}")
        if args.open and shutil.which("open"):
            subprocess.run(["open", str(page)], check=False)
        return 0

    submit_line = f"Recording to {verdict_path(out_dir)} as pass {pass_no}."
    hint = "Record each photo, then press Done to hand control back."
    html = render_page(title, built, "serve", token, pass_no, submit_line, hint)
    server = ReviewServer(html, token, out_dir, pass_no, args.host,
                          args.port, args.idle_timeout)
    server.build()  # bind before writing: exit 2 means nothing was written

    # The page is written as well as served, so it is a record of what was reviewed
    # and the generated-file list points at something that exists.
    page = out_dir / f"review-pass{pass_no}.html"
    page.write_text(html)
    write_files_manifest(out_dir, page)

    local = f"http://127.0.0.1:{server.port}/{token}/"
    say(f"review page: {local}")
    if args.host == "0.0.0.0":
        address = lan_address()
        if address:
            say(f"on the network: http://{address}:{server.port}/{token}/")
        say("for Codex: bind is 0.0.0.0; open that URL in Codex's browser")
    say(f"pairs: {len(built)}  callouts: {sum(len(p['callouts']) for p in built)}  "
        f"pass: {pass_no}")
    say(f"verdicts: {verdict_path(out_dir)}")

    if args.open:
        webbrowser.open(local)

    recorded = server.run()

    for record in recorded:
        notes = record.get("callouts") or {}
        suffix = f" ({len(notes)} note{'s' if len(notes) != 1 else ''})" if notes else ""
        say(f"  {record['photo']}: {record['verdict']}{suffix}")
    if not recorded:
        say("no verdicts recorded")

    if args.json:
        print(json.dumps({
            "mode": "serve", "pass": pass_no, "pairs": len(built),
            "recorded": recorded, "verdicts": str(verdict_path(out_dir)),
        }, indent=2))

    say(f"\nread them back with: cat {verdict_path(out_dir)}")
    say(f"clean up with: python {Path(sys.argv[0]).name} --out-dir {out_dir} --clean")
    return 0 if recorded else 1


if __name__ == "__main__":
    sys.exit(main())
