# Photo Upscale & Enhance — Fidelity First

A reusable Agent Skills-compatible photo restoration workflow focused on **subject fidelity** rather than generative prettification.

- `SKILL.md`: skill metadata, non-negotiable fidelity constraints, restoration workflow, and validation rules.
- `references/prompt-templates.md`: prompts for normal images, same-person face references, archival scans, and group portraits.
- `references/qa-checklist.md`: acceptance criteria for faces, expressions, bodies, geometry, and visual quality.
- `references/metadata-and-naming.md`: what metadata travels, what gets corrected, the naming rule, format matrix, and verified exiftool gotchas.
- `references/macos-photos.md`: recovering the real original out of Photos.app, and importing the result back intact.
- `scripts/compare.py`: optional side-by-side visual QA sheet; needs Pillow (`python -m pip install Pillow`).
- `scripts/finalize.py`: names the output, carries the metadata forward, adds a provenance line, and verifies all of it against the actual pixels.
- `scripts/new-project.py`: scaffolds a project directory with role-separated references and a manifest.

## Metadata is part of fidelity

A restoration that returns clean pixels and no capture date, camera, place, or
caption improved the image and destroyed the archive. The default output format
follows the source container (JPEG in, JPEG out at q95) rather than always PNG,
for exactly this reason: consumer readers ignore PNG's metadata chunks.

**Verified behavior, tested with exiftool 13.55:**

- A single pass cannot copy *and* correct. `-TagsFromFile src -all:all
  -Orientation#=1` leaves the copied orientation in place; the correction needs a
  second pass.
- `-Orientation=1` is silently ignored. `-Orientation#=1` works.
- The writable dimension tags are `ExifImageWidth` / `ExifImageHeight`.
  `PixelXDimension` is rejected as undefined.

## Finalize a restore

```sh
python scripts/finalize.py source/IMG_1234.jpg render.png \
  --project grandma --out-dir grandma/output --suffix _upscale
```

Order is fixed: encode, copy, correct, verify. It exits non-zero and renames the
file `*_UNVERIFIED` if any metadata could not be preserved.

## Project layout

```sh
python scripts/new-project.py grandma --source target.jpg \
  --face face-ref.jpg --body body-ref.jpg
```

```
<project>/
  source/      read-only; the authoritative original
  refs/face/   identity constraints: bone structure, hairline, marks
  refs/body/   silhouette and proportion constraints
  output/      suffixed results, metadata intact
  qa/          compare.py sheets
  manifest.json
```

Face and body references are separated because their roles are not
interchangeable. Face references constrain *who*; body references constrain
*shape*; neither constrains expression, gaze, apparent age, or clothing. A
project is optional: for a single photo, pass plain paths to `finalize.py`.

## macOS and Apple Photos

If the photo came from Photos.app by drag-and-drop, it may be a re-encoded render
with metadata stripped. Preflight it with `exiftool`; if the capture date or
camera is missing, recover the real original by UUID:

```sh
osxphotos uuid                     # with the photo selected in Photos.app
osxphotos export ./source --uuid <UUID> --sidecar xmp
```

Import the result back as a new asset, filed at its capture date:

```sh
osxphotos import ./output/IMG_1234_upscale.jpg \
  --album "grandma restored" --skip-dups
```

Never run `osxphotos push-exif`. It writes metadata into the library's original
files, which is the one thing this skill must not do.

## Use in an Agent Skills-compatible environment

Place the `photo-upscale-enhance` folder under the agent's supported skill directory (for example a Codex project's `.agents/skills/` directory), then invoke it by name or describe the task. Keep the folder name identical to the frontmatter `name`.

For a ChatGPT Project where direct skill installation is not supported, paste the content of `SKILL.md` into the Project's instructions/knowledge, or upload the package as project reference material. This zip by itself does **not** silently install the skill in the current chat.

## Tool-agnostic, not capability-agnostic

The skill does not bundle an image upscaler, face model, or weights. It instructs
any available image editing or non-generative image processing tools to produce
fidelity-first results. It cannot recover information that was not recorded in
the original photograph.

Optional pieces, all of which degrade gracefully:

| Tool | Used for | If absent |
| --- | --- | --- |
| `exiftool` | copying, correcting, and verifying metadata | Pillow carries the raw EXIF blob and ICC only; the run reports `degraded` and names what was lost |
| ImageMagick or `sips` | decoding HEIC/HEIF, which Pillow cannot read | HEIC input is refused rather than half-processed |
| `osxphotos` | getting the real original out of Photos.app, and importing the result back | plain file-path workflow |

## Quick QA

```bash
python -m pip install Pillow
python scripts/compare.py original.jpg restored.png --out comparison.png
python scripts/compare.py original.jpg restored.png --out face-check.png --crop 120,100,300,330
```

The `--crop` coordinates refer to the original image (not the upscaled image). The comparison is for inspection, not a certified verification of identity.
