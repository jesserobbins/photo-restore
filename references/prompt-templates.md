# Prompt templates

These prompts are intended for image-editing tools receiving source imagery.
Pass the *target image* explicitly, plus any separately identified reference
images. Prefer low edit strength and localized corrections.

## Which model to hand this to

The image models reachable through **Gemini** and **Codex** have held up best on
restoration work; prefer them when there is a choice. Two habits matter more than
the choice itself:

- Use the model's **image-editing** path with the source passed as the image to
  edit. A text-to-image prompt that describes the photo produces a lookalike, and
  a lookalike is not a restoration however good it is.
- Ask for the **lowest edit strength** the tool exposes, then check grain and
  flat-region texture. A model that returns smooth skin made a decision about
  what kind of photo it was looking at.

These templates are deliberately model-agnostic so they survive a model change.
Trim clauses a given model ignores rather than assuming every sentence is
honoured, and re-verify after any model or version change.

## Grain clause

Append the clause that matches the decision from `references/film-grain.md`.
Never leave grain unmentioned in a film-source prompt; unspecified grain is the
texture a super-resolution model flattens first.

| Decision | Clause to append |
| --- | --- |
| Preserved | `Preserve the existing film grain exactly: same clump size relative to the subject, same randomness, same chroma-luminance balance. Do not smooth flat areas and do not add texture anywhere it is absent.` |
| Recovered | `Preserve the film grain that is visible in flat areas and carry it through at the same relative scale. Where grain is attenuated, recover it from the source's own flat regions rather than inventing new texture.` |
| Reconstructed (asked for) | `Add film grain matching this stock's real character: [stock and era]. Random clumping, not uniform noise. Grain size scaled to the output dimensions so it reads as film, not sensor noise. Do not apply it to areas the photographer retouched.` |
| None (digital) | `Do not add film grain. Preserve the digital image's existing noise character and do not introduce texture that was not in the source.` |

Because a faithful 2× upscale leaves grain twice as large in pixels, the render
should show grain that is *coarser in pixels and identical in structure*. Grain
that vanishes in flat areas has been averaged away; grain that is uniformly
tiny everywhere has been synthesised by the upscaler.

## A. Ordinary photograph (default)

Upscale the TARGET photograph 2x in both dimensions. Apply conservative
photographic restoration only: reduce compression artifacts and distracting
noise, recover slight tonal detail, and apply restrained sharpness.

ABSOLUTE CONSTRAINTS: Preserve the subject(s) exactly. No edits to facial
structure, expression, eye direction, mouth, teeth, apparent age, physique,
pose, skin texture, clothing, props, or background. Preserve the exact
framing and aspect ratio. Do not add new objects, repair speculative details,
beautify, colorize, or stylize. Keep ambiguous areas appropriately soft.
Prioritize faithful identity and source accuracy over dramatic crispness.

## B. Target portrait with reference face photo(s)

Image 1 is the TARGET TO RESTORE. Images 2+ are REFERENCE PHOTOS of the
same person and must NOT be copied or composited into Image 1.

Upscale Image 1 2x with gentle denoise and detail recovery. Use the
references solely as guidance for stable identity features (facial structure,
feature proportions, hairline, and distinctive marks). Maintain Image 1's
exact expression, gaze, mouth shape, teeth visibility, apparent age, head
angle, lighting, hairstyle as photographed, and degree of occlusion.
Do not import any smile, wrinkles, hair, expression, angle, or lighting
from a reference image. Do not swap or replace the face. Preserve body,
clothing, background, pose, composition, and film character as in Image 1.
If the source has insufficient evidence for a feature, retain ambiguity.
The output must still look like the same moment captured by the camera.

## C. Archival / film scan

Faithfully restore and upscale the TARGET scan 2x. Correct obvious
dust/scratches and scanning defects with the smallest plausible changes.
Keep original film grain, focus falloff, period color or monochrome, and
photographic texture. Do not erase age lines, alter expressions, repaint
clothing, modernize materials, colorize black-and-white, or invent faces,
letters, patterns, or historical details. Preserve image boundaries and
subject scale. Keep the paper's surface texture separate from the film grain and
preserve both; do not let one be mistaken for the other or amplified on the way
up.

## D. Group portraits

Upscale 2x conservatively. Protect **every** individual equally, including
small, partially obscured or background faces; retain exact head count,
placement, expression, apparent age, silhouette, clothing, and interactions.
Do not refine a small face using speculative details. Do not alter hands,
proportions, or overlap/occlusion relationships. Restore global image quality
without re-generating people.

## E. Higher detail (only if user explicitly asks)

Increase perceived detail beyond the conservative baseline while continuing
to preserve all identity, expression, and geometry invariants. Where higher
detail would require hallucinating distinct physical features, refrain from
doing so. Prefer local improvements to global reconstruction; compare with
the original and discard any identity-changing candidate. Higher detail is not
a licence for cleaner texture: sharper does not mean smoother, and grain must
not be traded for invented micro-detail.
