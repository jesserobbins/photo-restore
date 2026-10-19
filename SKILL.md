---
name: photo-upscale-enhance
description: >
  Conservatively upscale, restore, and enhance photographs while preserving
  the exact identity, facial features, expression, gaze, pose, body shape,
  clothing, composition, and historical details of every subject. Use for
  photo upscaling, old-photo restoration, scanned prints, noise reduction,
  deblurring, and face-reference-guided restoration. Prefer faithful recovery
  over creative reconstruction or beautification.
metadata:
  version: "2.0.0"
  default-mode: "conservative"
---

# Photo Upscale & Enhance — Fidelity First

## Objective and priority

Improve the *technical quality* of a supplied photo without changing what it
depicts. Treat fidelity to the source as the highest priority. It is preferable
to leave uncertain details soft or imperfect than to invent plausible ones.

**Order of priorities:**
1. Preserve the subjects, their identity, appearance, expression, posture,
   proportions, and relationships.
2. Preserve scene geometry, composition, clothing, objects, and period details.
3. Recover the photographic signal that can reasonably be recovered.
4. Improve perceived quality (clarity, resolution, tonal range, noise).
5. Aesthetic enhancement only when compatible with 1–4.

Never sacrifice a higher priority for a lower one.

## When to use

Use when the user asks to **upscale**, **enhance**, **clean up**, **restore**,
**sharpen**, **denoise**, **deblur**, or **improve resolution** of an existing
photograph, especially portraits, family photos, group photos, archival
photos, and scans. When reference photos of the same subject are supplied,
use them cautiously as *identity constraints*, not as replacement content.

If the user instead requests stylization, compositing, a new pose, a changed
expression, face swapping, or creative reimagining, clarify that this is
outside the default fidelity-first mode (or follow the explicitly requested
edit without representing it as faithful restoration).

## Non-negotiable invariants

Preserve, unless the user **explicitly** directs a change:

- **Face and identity:** bone structure, jawline, nose, eyes/eyelids, eye
  spacing, ears, mouth, teeth, hairline, wrinkles, asymmetry, age,
  ethnicity-indicative appearance, and distinctive marks.
- **Expression and gaze:** smile intensity, lip shape and openness, teeth
  visibility, eyelid shape, eye direction, emotional expression.
- **Body:** silhouette, physique, body/limb proportions, hands/fingers,
  posture, head tilt, shoulder angle, and relative scale.
- **Surroundings:** subject count, positions, background people and objects,
  clothing and insignia, jewelry, text/signage, lighting direction, shadows,
  depth of field, camera perspective, framing, and aspect ratio.
- **Photo character:** authentic skin texture, film grain where appropriate,
  original color intent (including monochrome/sepia), and historically
  plausible materials. Do not default to smooth modern phone-photo rendering.

No de-aging, slimming, face reshaping, new teeth, new eyes, makeup, glamour
retouching, skin plasticization, artificial smiles, changed gaze, replacement
background, speculative facial details, or "AI prettification".

## Default settings

If the user does not specify otherwise, use:

| Setting | Default |
| --- | --- |
| Fidelity mode | **Conservative / strict** |
| Scale | **2× in each dimension** (4× pixel count), if technically feasible |
| Aspect ratio / crop | **Identical to source**, no reframing |
| Denoise | Mild; retain real texture |
| Sharpness | Gentle; avoid halos and fake microtexture |
| Contrast / exposure | Small, reversible corrections |
| Color | Neutral and source-faithful; no automatic colorization |
| Face treatment | Same fidelity rules as the rest of the photo |
| Generative reconstruction | **Off**, unless truly needed and disclosed |
| Reference face use | Identity consistency only |
| Output format | **Same container as the source** (JPEG→JPEG q95, PNG→PNG, TIFF→TIFF, HEIC→JPEG) |
| Output filename | `<source-stem>_upscale.<ext>`; `_enhance` for the higher-detail variant |
| Overwrite | **Never**; collisions append `-2`, `-3` |
| Metadata | **Copy from source, correct what changed, append provenance** |
| Capture date | **Never modified**, not even to record the processing time |
| Original | Retained, unwritten, unmodified |

**Conservative** is not an adjective for a prompt; it is the acceptance
criterion. If a more dramatic image looks better but changes a subject,
reject it and use the gentler result.

Metadata is part of fidelity. A restoration that returns clean pixels and no
capture date, camera, place, or caption destroyed the archive to improve the
image. See [references/metadata-and-naming.md](references/metadata-and-naming.md).

## Project directories

For a job with face or body references, or more than one photo, keep the work in
a project directory. `scripts/new-project.py` scaffolds it; a human can also
make one by hand.

```
<project>/
  source/      the photo(s) to restore — read-only, never written to
  refs/face/   identity constraints: bone structure, hairline, marks
  refs/body/   silhouette and proportion constraints
  output/      suffixed results, metadata intact
  qa/          compare.py sheets
  manifest.json
```

```sh
python scripts/new-project.py grandma --source target.jpg \
  --face face-ref.jpg --body body-ref.jpg
```

Face and body references are separated by directory because their roles are not
interchangeable: face references constrain *who*, body references constrain
*shape*, and neither constrains expression, gaze, apparent age, or clothing.
Putting them in differently named directories makes that limit structural rather
than something to remember.

A project is optional. For one photo with no references, pass plain paths to
`finalize.py` and skip the scaffold.

## Workflow

### 1. Inspect and anchor the source

- Treat the original image as authoritative evidence. Do not overwrite it.
- If the photo arrived by drag-and-drop rather than as a path, it is a **visual
  reference of unknown provenance**, not the original — a chat client may have
  re-encoded it at reduced size with metadata stripped. On macOS, preflight it
  and recover the real file from Photos.app by UUID. See
  [references/macos-photos.md](references/macos-photos.md).
- Note dimensions, orientation, grain, focus, compression artifacts, scratches,
  color cast, clipping, and areas of genuine uncertainty.
- Read the existing metadata before touching anything. The capture date, camera,
  place, caption, and keywords are what the owner will expect back.
- Identify all faces, expressions, body outlines, hands, distinctive objects,
  text, patterns, and small features at risk of "helpful" invention.
- Preserve subject count and exact framing. Handle EXIF orientation correctly;
  most upscalers return pixels already upright, so the output orientation tag
  must be normalized rather than inherited.
- If the subject is very small or badly damaged, be explicit that some features
  cannot be faithfully recovered.

### 2. Select a minimal-change restoration path

Prefer this progression, stopping as soon as quality is sufficient:

1. **Photometric corrections:** slight white balance, exposure, highlights,
   shadows, tonal and color restoration as appropriate.
2. **Non-generative cleanup:** mild dust/scratch repair, compression cleanup,
   careful denoise without destroying texture; mask localized damage.
3. **Deterministic / low-hallucination resize:** high-quality resampling
   (e.g. Lanczos) or a demonstrably conservative super-resolution model.
4. **Light finishing:** modest sharpening and fine-grain management
   suitable for the output dimensions.
5. **Conditional face-aware reconstruction:** only if steps 1–4 cannot
   reasonably address the defect, with *strong* identity/geometry control
   and no confident fabrication of absent information.

Avoid a wholesale diffusion/regeneration pass as the starting point. Face
restorers that invent eyes, smiles, teeth, hairstyles, or ages are *not*
acceptable default choices.

### 3. Use reference photos only when provided

If one or more clear images of a depicted person are supplied:

- Determine which face in the source corresponds to each reference.
- Use references to check **stable identity traits** (face shape, feature
  proportions, hairline, distinctive marks), never to transplant the
  reference's smile, gaze, age, lighting, makeup, or viewpoint.
- Preserve the **source photo's** expression, age, head angle, occlusion,
  and lighting. Do not paste, morph, or replace the face.
- If references disagree because of age, hairstyle, expression, or camera
  angle, prefer the target image for those properties.
- If identity cannot be established confidently, don't force a match.

When available, an identity-preserving model or source-guided restoration
may assist; never assume the model's "identity similarity" score certifies
the result. Visual checking of defining features remains mandatory.

### 4. Make a first conservative pass

If image editing/generation tools are available, supply the relevant source
image(s), and use the exact constraints in
[references/prompt-templates.md](references/prompt-templates.md).
Distinguish TARGET (photo to restore) from REFERENCES (identity aids).

**One source photo -> one faithful output.** Preserve all depicted content.
If the available editing tool tends to rerender content, minimize strength
or fall back to deterministic enhancement. Do not label a regenerated
interpretation as a faithful upscale.

If no image-processing capability is available, provide the user the
precise prompt and workflow rather than claim that editing occurred.

### 5. Verify fidelity before delivering
Follow [references/qa-checklist.md](references/qa-checklist.md). At minimum:

- Compare original and output at matched framing and magnification.
- Check each face at the same apparent size: identity, expression, gaze,
  eyelids, nose, mouth, teeth, jaw, ears, age, distinctive features.
- Compare silhouette, posture, hands, body proportions, clothing,
  background objects, text, and lighting.
- Look for waxy skin, synthetic pores, ringing/halos, artifacts,
  painted-over grain, oversharpening, speculative textures or alterations.
- If the output fails **any** high-priority invariant, **reduce processing,
  mask the affected area, or use the conservative baseline**.
- Optionally run `python scripts/compare.py original.jpg enhanced.png
  --out comparison.png --crop 100,80,300,320` to make an aligned visual
  comparison. Coordinates are in **original-image pixels**; crop is optional.

No aggregate image-similarity metric can substitute for these checks.

### 6. Finalize the file: name it and carry the metadata

Visual fidelity is not the only thing to verify. Run
`scripts/finalize.py SOURCE RENDER` to write a correctly named output whose
metadata is copied from the source, corrected where the upscale made it false,
and verified against the real pixels.

```sh
python scripts/finalize.py source/IMG_1234.jpg render.png \
  --project grandma --out-dir grandma/output --suffix _upscale
```

It performs, in this order: normalize and encode to the source container, copy
all metadata, correct the falsified tags, add a provenance sentence, then verify
and report. Then it appends a manifest entry.

What it guarantees, and what to do if it does not:

| Reported | Meaning | Action |
| --- | --- | --- |
| `pass` | All metadata carried and dimensions consistent. | Deliver. |
| `degraded` | exiftool absent; only the raw EXIF blob and ICC profile carried. | Say exactly which fields are missing, including that provenance was not written. Do not claim preservation. |
| `fail` | A core tag is missing, a dimension tag disagrees, or a caption was replaced. | **Do not deliver and do not import into Photos.** Fix and rerun. |

The output keeps the source's capture date, camera, GPS, rating, keywords and
caption, and gains a provenance line recording **when** and **where** the
upscale happened. The capture date is never moved — the processing time goes in
`XMP-xmpMM:History` and `UserComment` precisely so that a 1962 photograph does
not get refiled as a 2026 one.

If `exiftool` is unavailable and the host has no filesystem at all, do not
assert that metadata was preserved. Give the user the exact commands from
[references/metadata-and-naming.md](references/metadata-and-naming.md) and say
they were not run here.

### 7. Deliver transparently

- Return the restored image where the available tools support it.
- Say the scale applied and summarize **actual** operations performed.
- Report the metadata result: `pass`, or the specific `degraded` shortfall.
- Say which file was restored when a photo had edits: the edited render or the
  unedited master are different claims about the same filename.
- Clearly distinguish a non-generative upscale from a generated/restored
  interpretation; do not promise exact recovery of lost detail.
- If significant areas are ambiguous, disclose them briefly.
- Preserve the original and avoid silent crop/colorization/content changes.
- For low-quality source material, optionally provide two labeled variants:
  **Faithful** (`_upscale`) and **Enhanced** (`_enhance`, more detail but subject
  to the same identity/expression constraints). Default to **Faithful** alone.
- On macOS, the result can be imported back into Photos as a new asset with its
  capture date intact. See [references/macos-photos.md](references/macos-photos.md),
  and never run `osxphotos push-exif`, which writes to the originals.

## Priority decision rules

| Situation | Action |
| --- | --- |
| Face looks more attractive but less like the source | Reject |
| Source looks a little soft but facial geometry is correct | Prefer |
| Reference has a wider smile than the source | Keep source smile |
| Denoise removes real wrinkles or fabric weave | Reduce denoise |
| "Upscale" adds pores/teeth/hair strands not evidenced by source | Reduce or remove generative processing |
| Damage prevents confident recovery | Leave restrained ambiguity; disclose |
| Uncertain writing or insignia | Do not invent readable text |
| Only face changes while rest stays faithful | Reject or mask off face |
| Output has clean pixels but lost the capture date | Treat as a failure, not a success |
| The delivered file looks like a chat-app re-encode | Get the original before restoring |
| A caption would be replaced by the provenance note | Append instead; never replace |

## Default prompt

> Upscale this supplied photograph 2× and improve technical quality
> conservatively. Preserve every person's identity, exact facial geometry,
> expression, gaze, apparent age, skin texture, body proportions, pose, and
> clothing. Preserve subject count, composition, cropping, background,
> objects, perspective, and lighting. Reduce noise and artifacts gently,
> correct tone/color only where justified, and sharpen without creating
> synthetic detail. This is a high-fidelity restoration, NOT a reimagining,
> face beautification, or face replacement. If a detail is genuinely absent,
> keep it uncertain rather than hallucinating it. Keep the output visually
> faithful to the original even if that means some softness remains.

See [references/prompt-templates.md](references/prompt-templates.md) for
portrait-with-reference, archival, and batch variants.
