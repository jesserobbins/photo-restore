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
  version: "1.0.0"
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
| Output | Lossless PNG or high-quality original-appropriate format; retain original |

**Conservative** is not an adjective for a prompt; it is the acceptance
criterion. If a more dramatic image looks better but changes a subject,
reject it and use the gentler result.

## Workflow

### 1. Inspect and anchor the source

- Treat the original image as authoritative evidence. Do not overwrite it.
- Note dimensions, orientation, grain, focus, compression artifacts, scratches,
  color cast, clipping, and areas of genuine uncertainty.
- Identify all faces, expressions, body outlines, hands, distinctive objects,
  text, patterns, and small features at risk of "helpful" invention.
- Preserve subject count and exact framing. Handle EXIF orientation correctly.
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

### 6. Deliver transparently

- Return the restored image where the available tools support it.
- Say the scale applied and summarize **actual** operations performed.
- Clearly distinguish a non-generative upscale from a generated/restored
  interpretation; do not promise exact recovery of lost detail.
- If significant areas are ambiguous, disclose them briefly.
- Preserve the original and avoid silent crop/colorization/content changes.
- For low-quality source material, optionally provide two labeled variants:
  **Faithful** (minimal change) and **Enhanced** (more detail but subject to
  the same identity/expression constraints). Default to **Faithful** alone.

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
