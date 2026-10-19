# Prompt templates

These prompts are intended for image-editing tools receiving source imagery.
Pass the *target image* explicitly, plus any separately identified reference
images. Prefer low edit strength and localized corrections.

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
subject scale.

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
the original and discard any identity-changing candidate.
