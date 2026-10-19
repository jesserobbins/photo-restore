#!/usr/bin/env python3
"""Scaffold a restoration project directory.

A project keeps the target, its identity references, the outputs, and the QA
sheets together, and records in manifest.json what was done to each asset.

    <project>/
      source/      the photo(s) to restore -- read-only, never written to
      refs/face/   identity constraints: bone structure, hairline, marks
      refs/body/   silhouette and proportion constraints
      output/      suffixed results, metadata intact
      qa/          compare.py sheets
      manifest.json

References are separated by role on purpose. The skill forbids importing a
reference's smile, gaze, age, or expression, so a face reference constrains
stable identity features and a body reference constrains silhouette and
proportion. Putting them in differently named directories makes that
constraint structural rather than something to remember.

A project is optional. For a single photo, call finalize.py with plain paths.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
SUBDIRS = ("source", "refs/face", "refs/body", "output", "qa")

README = """# {name}

Restoration project scaffolded {date} by photo-upscale-enhance.

- `source/` -- the photograph(s) to restore. Read-only: nothing writes here.
- `refs/face/` -- identity references. Bone structure, feature proportions,
  hairline, distinctive marks. These constrain *who*, never expression, gaze,
  or apparent age.
- `refs/body/` -- silhouette and proportion references. These constrain
  *shape*, never posture or clothing.
- `output/` -- results, named `<source-stem>_upscale.<ext>`.
- `qa/` -- comparison sheets from the skill's `compare.py`.
- `manifest.json` -- what was done to each asset, written by `finalize.py`.

## Workflow

1. Put the target in `source/` and any references in `refs/face/` or `refs/body/`.
2. Restore, writing the raw render somewhere temporary.
3. Finalize it, running the skill's `finalize.py` from wherever the skill lives
   and pointing `--out-dir` at `output/` so nothing is written into `source/`:

    python <skill>/scripts/finalize.py source/IMG_1234.jpg render.png \\
      --project . --out-dir output --suffix _upscale

4. Check the fidelity checklist, then deliver.

Nothing in this directory is published. If a reference is sensitive, it stays
on your machine and in whatever backup you already run.
"""


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", type=Path, help="Project directory to create")
    p.add_argument("--name", help="Human label (default: directory name)")
    p.add_argument("--force", action="store_true",
                   help="Scaffold into a non-empty directory")
    p.add_argument("--source", type=Path, action="append", default=[],
                   help="Copy a file into source/ (repeatable)")
    p.add_argument("--face", type=Path, action="append", default=[],
                   help="Copy a file into refs/face/ (repeatable)")
    p.add_argument("--body", type=Path, action="append", default=[],
                   help="Copy a file into refs/body/ (repeatable)")
    p.add_argument("--master", type=Path, action="append", default=[],
                   help="Copy the unedited master alongside source/, for reference")
    return p


def read_manifest(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write_manifest(root, path, data):
    """Merge under the same lock finalize.py uses.

    Without the lock, a finalize run that appends an asset between this read and
    this write would have its entry overwritten by the scaffolder's stale copy.
    """
    import fcntl

    lock = root / ".manifest.lock"
    with open(lock, "w") as lockfh:
        fcntl.flock(lockfh, fcntl.LOCK_EX)
        current = read_manifest(path)
        if current:
            # Recompute against what is on disk now, not what we read earlier.
            data["assets"] = current.get("assets", data.get("assets", []))
            data["sources"] = merge_list(current.get("sources"), data.get("sources"))
            data["masters"] = merge_list(current.get("masters"), data.get("masters"))
            prev_refs = current.get("references") or {}
            for role in ("face", "body"):
                data["references"][role] = merge_list(
                    prev_refs.get(role), data["references"].get(role)
                )
            data["created"] = current.get("created") or data.get("created")
        fd, tmp = tempfile.mkstemp(dir=root, prefix=".manifest-", suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        fcntl.flock(lockfh, fcntl.LOCK_UN)


def merge_list(old, new):
    out = list(old or [])
    for item in new:
        if item not in out:
            out.append(item)
    return out


def copy_in(files, dest, project, rename=None, role="file"):
    """Copy files in without ever clobbering something already there."""
    placed = []
    for f in files:
        if not f.exists():
            raise SystemExit(f"Not found: {f}")
        name = f"{f.stem}{rename}{f.suffix}" if rename else f.name
        target = dest / name
        if target.exists() and target.resolve() != f.resolve():
            # source/ is read-only evidence. Replacing a file there would silently
            # swap the thing being restored, which is the worst possible outcome.
            raise SystemExit(
                f"{target.relative_to(project)} already exists. Rename the incoming "
                f"{role} or use a different project; refusing to overwrite evidence."
            )
        if not target.exists():
            shutil.copy2(f, target)
            # A sidecar carries metadata that exists nowhere else. Copying the
            # image alone loses the caption and keywords the restore should keep.
            sidecar = f.with_name(f.name + ".xmp")
            if sidecar.exists():
                shutil.copy2(sidecar, dest / (name + ".xmp"))
        placed.append(str(target.relative_to(project)))
    return placed


def main():
    a = build_parser().parse_args()
    root = a.path
    name = a.name or root.name

    if root.exists() and any(root.iterdir()) and not a.force:
        # Refuse rather than scatter directories into a folder that already has
        # a life of its own -- usually a sign that the path is wrong.
        raise SystemExit(
            f"{root} already exists and is not empty. Pass --force if that is "
            "really the project directory. --force merges into the existing "
            "manifest rather than replacing it."
        )

    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)

    placed_source = copy_in(a.source, root / "source", root, role="source")
    # Masters are renamed on the way in, so a master can never land on top of the
    # restoration source it exists to be compared against.
    placed_master = copy_in(a.master, root / "source", root, rename="_master", role="master")
    placed_face = copy_in(a.face, root / "refs" / "face", root, role="face reference")
    placed_body = copy_in(a.body, root / "refs" / "body", root, role="body reference")

    manifest_path = root / "manifest.json"
    previous = read_manifest(manifest_path)

    data = {
        "schema": SCHEMA,
        "name": name,
        "created": previous.get("created") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "photo-upscale-enhance 2.0",
        "sources": merge_list(previous.get("sources"), placed_source),
        "masters": merge_list(previous.get("masters"), placed_master),
        "references": {
            "face": merge_list((previous.get("references") or {}).get("face"), placed_face),
            "body": merge_list((previous.get("references") or {}).get("body"), placed_body),
        },
        "assets": previous.get("assets", []),
        "notes": [
            "source/ is read-only evidence; nothing writes to it.",
            "Masters are copied as <stem>_master.<ext> so they cannot collide with a source.",
            "Refs constrain identity and proportion only -- never expression, "
            "gaze, apparent age, or clothing.",
            "finalize.py appends one entry per asset, including the metadata "
            "verification result.",
        ],
    }
    write_manifest(root, manifest_path, data)

    readme = root / "README.md"
    if not readme.exists() or a.force:
        readme.write_text(
            README.format(name=name, date=datetime.now().strftime("%Y-%m-%d"))
        )

    missing = []
    if not placed_source:
        missing.append("no target photo in source/")
    if not placed_face:
        missing.append("no face reference in refs/face/ (optional, but the skill "
                       "cannot constrain identity without one)")

    print(f"created {root}")
    for sub in SUBDIRS:
        print(f"  {sub}/")
    print(f"  manifest.json  (schema {SCHEMA})")
    if placed_source:
        print(f"targets:    {len(placed_source)}")
    if placed_face:
        print(f"face refs:  {len(placed_face)}")
    if placed_body:
        print(f"body refs:  {len(placed_body)}")
    for m in missing:
        print(f"note: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
