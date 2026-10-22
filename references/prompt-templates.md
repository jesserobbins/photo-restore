# Prompt templates

These prompts are intended for image-editing tools receiving source imagery.
Pass the *target image* explicitly, plus any separately identified reference
images. Prefer low edit strength and localized corrections.

## Which model to hand this to

The image models reachable through Gemini and Codex have held up best on
restoration work. Prefer them when there is a choice. Two habits matter more than
the choice itself:

- Use the model's image-editing path with the source passed as the image to
  edit. A text-to-image prompt that describes the photo produces a lookalike, and
  a lookalike is not a restoration however good it is.
- Ask for the lowest edit strength the tool exposes, then check grain and
  flat-region texture. A model that returns smooth skin made a decision about
  what kind of photo it was looking at.

These templates are deliberately model-agnostic so they survive a model change.
Trim clauses a given model ignores rather than assuming every sentence is
honoured, and re-verify after any model or version change.

## Mode clause

Pick the template that matches the mode, and pass the same mode to
`finalize.py --mode`. The mode decides the acceptance rule, so a template used
outside its mode is the wrong test.

| Mode | Template | Acceptance rule |
| --- | --- | --- |
| Faithful repair | A, B, C or D | nothing in the frame may change except technical quality |
| Requested retouch | F, and G for a red eye, over the last accepted baseline | only the named region may change |
| Generative interpretation | E | detail may be reconstructed; identity, expression, gaze, age and composition may not change |

Do not soften a template because the owner asked for more. A stronger request is a
change of template, not a weaker reading of the same one.

## Grain clause

Append the clause that matches the decision from `references/film-grain.md`.
Never leave grain unmentioned in a film-source prompt. Unspecified grain is the
texture a super-resolution model flattens first.

| Decision | Clause to append |
| --- | --- |
| Preserved | `Preserve the existing film grain exactly: same clump size relative to the subject, same randomness, same chroma-luminance balance. Do not smooth flat areas and do not add texture anywhere it is absent.` |
| Recovered | `Preserve the film grain that is visible in flat areas and carry it through at the same relative scale. Where grain is attenuated, recover it from the source's own flat regions rather than inventing new texture.` |
| Reconstructed (asked for) | `Add film grain matching this stock's real character: [stock and era]. Random clumping, not uniform noise. Grain size scaled to the output dimensions so it reads as film, not sensor noise. Do not apply it to areas the photographer retouched.` |
| None (digital) | `Do not add film grain. Preserve the digital image's existing noise character and do not introduce texture that was not in the source.` |

Because a faithful 2× upscale leaves grain twice as large in pixels, the render
must show grain that is *coarser in pixels and identical in structure*. Grain
that vanishes in flat areas has been averaged away. Grain that is uniformly
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
preserve both. Do not let one be mistaken for the other or amplified on the way
up.

## D. Group portraits

Upscale 2x conservatively. Protect every individual equally, including
small, partially obscured or background faces. Retain exact head count,
placement, expression, apparent age, silhouette, clothing, and interactions.
Do not refine a small face using speculative details. Do not alter hands,
proportions, or overlap/occlusion relationships. Restore global image quality
without re-generating people.

## E. Generative interpretation (only if the owner asks for it)

This is the generative mode. Pass `--mode generative` to `finalize.py`, which adds the
disclosure to the provenance sentence. Without that disclosure the result would read
as recovered detail.

Increase perceived detail beyond the faithful baseline while continuing
to preserve all identity, expression, and geometry invariants. Where higher
detail would require hallucinating distinct physical features, refrain from
doing so. Prefer local improvements to global reconstruction. Compare with
the original and discard any identity-changing candidate. Higher detail is not
a licence for cleaner texture: sharper does not mean smoother, and grain must
not be traded for invented micro-detail.

## F. Requested retouch of one region

Use this for a change the owner named: skin smoothing, a small nostril adjustment,
makeup-style cleanup, flyaway hairs. Work on a crop of the last accepted version,
then composite the result back into that version. A full-frame pass moves parts of
the photograph nobody asked about.

Image 1 is the TARGET. It is a crop of the accepted version, and it is the only part
of the photograph that may change.

Make exactly this change and nothing else: <the owner's request, in their words>.

Hold every other value at the accepted version: the shape and position of the pupils,
the catchlights, the eyelid openings, the lip line, the teeth, the outline of the
nostrils, the facial contours, the jawline, the hairline, the apparent age and the
expression. Do not smooth beyond the named region. Do not redraw a feature. Do not
move a feature inside the crop. Keep the grain and the texture of the surrounding
skin as they are.

Then composite this crop back into the accepted frame. Compare the result with the
accepted version at the same size before you show it. If the model moved a feature
inside the crop, the alignment is wrong and feathering will not repair it.

## G. Red-eye correction of one eye

Use this in the requested-retouch mode. Red-eye is the case that breaks first,
because the obvious fixes all destroy the eye: darkening the pupil paints a disc,
recoloring the iris turns it green or flat, and asking the model for "clean eyes"
usually redraws the eyelid while it works.

Image 1 is the TARGET. Image 2 is a crop of the same eye in the source, at the size
the pupil should be.

Remove the red cast from the pupil of the eye in Image 1. Keep the pupil at its exact
position and diameter, keep its luminance structure, keep the catchlight and its
shape, and keep the iris untouched. Do not change the eyelid, the lashes, the
sclera, the tear line or the skin around the eye. Do not add or remove a highlight.

Then check it at 200% against the source eye:

- the pupil is the same size and position
- the catchlight is still there and still the same shape
- the iris colour did not move
- the eyelid and lashes are identical to the accepted version

Reddish, amber and already-correct eyes each fail in a different way. An eye that
was already correct must come back unchanged, and a correction that alters it is a
defect even when the result looks cleaner.

When the model will not do this reliably, do not iterate. Borrow the iris and pupil
from another photograph of the same person at the same angle, or leave the eye and
disclose it. A painted-looking pupil is worse than a red one.

## Notes on what the controls will not do

- A prompt cannot set an edit strength the tool does not expose. Do not describe a
  result as "run at 35% strength" because a blend used 35%.
- A blend percentage is a compositing weight. Report it as one.
- When a model refuses the edit or changes a subject, reduce the change, mask it
  smaller, or use a deterministic resample. Do not iterate until a better-looking
  frame appears.
