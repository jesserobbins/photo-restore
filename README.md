# Photo Upscale & Enhance — Fidelity First

A reusable Agent Skills-compatible photo restoration workflow focused on **subject fidelity** rather than generative prettification.

- `SKILL.md`: skill metadata, non-negotiable fidelity constraints, restoration workflow, and validation rules.
- `references/prompt-templates.md`: prompts for normal images, same-person face references, archival scans, and group portraits.
- `references/qa-checklist.md`: acceptance criteria for faces, expressions, bodies, geometry, and visual quality.
- `references/film-grain.md`: the grain questions to ask, what grain actually is, stock character, and the one case where synthesizing it is allowed.
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

Order is fixed: encode, copy, correct, verify. Exit codes are part of the contract:

| Code | Meaning |
| --- | --- |
| 0 | Verified, or `degraded` with the shortfall named |
| 1 | Verification failed — file renamed `*_UNVERIFIED`, do not deliver |
| 2 | Bad invocation or environment — nothing was written |

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

Place the `photo-restore` folder under the agent's supported skill directory (for example a Codex project's `.agents/skills/` directory), then invoke it by name or describe the task. Keep the folder name identical to the frontmatter `name`.

For a ChatGPT Project where direct skill installation is not supported, paste the content of `SKILL.md` into the Project's instructions/knowledge, or upload the package as project reference material. This zip by itself does **not** silently install the skill in the current chat.

## Preferred image models

The pixel work goes to an image model, and they do not behave the same way on a
restoration. The image models reachable through **Gemini** and **Codex** have held
up best; prefer them where a choice exists, and use their image-*editing* path
with the source passed in rather than a text-to-image prompt that describes it.
Any other editing-capable model is acceptable under the same constraints and the
same verification — the models execute, the fidelity rules and checks are what
make the result a restoration.

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

## Film grain is a decision, not a default

Grain is the one texture this skill may add, and only under disclosure. Grain is
in the negative; a print shows that same grain enlarged, and adds paper surface
texture at a different frequency. The era predicts grain size well enough to
**check the file**, which is the honest use of "era-appropriate."

| Source grain | Action | Recorded as |
| --- | --- | --- |
| Visible and intact | Preserve; denoise before the upscale | `preserved` |
| Attenuated but present in flat areas | Recover from the source's own flat regions | `recovered` |
| Absent everywhere | Only if asked; match the stock; disclose | `reconstructed` |
| Digital capture | Leave alone | `none` |

The check: a faithful 2× upscale leaves grain **twice as large in pixels and
identical in structure**. Flat, textureless output means the grain was averaged
away. Uniform tiny texture everywhere means synthetic texture was substituted.

```sh
python scripts/finalize.py source/IMG_1234.jpg render.png --grain reconstructed
```

`--grain reconstructed` puts the fact into the provenance sentence automatically,
so a reconstruction cannot be delivered as if it were preservation.

## Tests

```sh
python -m pytest tests/ -q
```

The tests pin the invariants rather than the prose: naming never overwrites, the
provenance sentence cannot be talked out of disclosing a reconstructed grain, and
the original file is byte-identical after a run.

## Quick QA

```bash
python -m pip install Pillow
python scripts/compare.py original.jpg restored.png --out comparison.png
python scripts/compare.py original.jpg restored.png --out face-check.png --crop 120,100,300,330
```

The `--crop` coordinates refer to the original image (not the upscaled image). The comparison is for inspection, not a certified verification of identity.
