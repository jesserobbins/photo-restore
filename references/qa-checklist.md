# Visual fidelity acceptance checklist

Use this checklist after EVERY pass. Fail any hard check -> reduce the edit,
mask the affected area, or revert to a deterministic baseline.

## First: which mode ran, and does the checklist match it

The hard checks below describe faithful repair. Two of them change with the mode, and
applying the wrong version turns a requested edit into a failure.

| Mode | What changes in the checklist |
| --- | --- |
| Faithful repair | all checks below, unchanged |
| Requested retouch | a named region that differs from the source is the result, not a defect. The rest of the frame is still held to every hard check |
| Generative interpretation | reconstructed detail is expected and is disclosed. Identity, expression, gaze, age and composition are still held to every hard check |

For a requested retouch, the protected set is explicit:

- [ ] Eyes, lips, teeth, nostril outlines and facial contours are unchanged unless
      the owner named them.
- [ ] Everything outside the named region is unchanged. Compare against the last
      accepted version, not only against the source.
- [ ] A feature the owner already accepted still matches the accepted version. Do not
      re-solve a face that was signed off in an earlier pass.

## Hard checks (must pass)

- [ ] Correct subject count and identities. No invented faces/people.
- [ ] Each face's defining structure and asymmetry retained (eyes, nose,
      cheekbones, mouth, jaw, ears, hairline, marks).
- [ ] Facial expressions, gaze direction, teeth visibility, and apparent age
      match the TARGET, not the face references.
- [ ] Body proportions, silhouette, posture, head tilt, hands, and fingers
      have not changed.
- [ ] Clothing, insignia, jewelry, props, readable text, and background objects
      are unchanged, except for faithful removal of clearly identifiable
      damage. No invented lettering or new objects.
- [ ] Composition, crop, orientation, horizon, perspective, aspect ratio,
      occlusions, and shadows are preserved.
- [ ] Original black-and-white, sepia, or restrained color character preserved
      unless user explicitly requests colorization.
- [ ] No invented distinct detail in severely blurred/damaged regions.

## Quality checks

- [ ] No over-smoothed/plastic skin or "AI glamour" face.
- [ ] Wrinkles, freckles, pores, fabric texture, and film grain are not
      aggressively removed or replaced with synthetic versions.
- [ ] No ringing, halos, edge stair-stepping, super-resolution grid patterns,
      duplicated details, or oversharpening.
- [ ] No false sharpness from invented eye reflections, teeth, eyelashes,
      hair strands, or background text.
- [ ] No crushed shadows, clipped highlights, artificial HDR, or extreme saturation.
- [ ] Reasonable pixel dimension increase (typically 2x width and height).
- [ ] Coarse model texture, extra pores, crosshatching and invented lines were read as
      defects, not as recovered detail.
- [ ] Where the delivered file is larger than the model's own render, the resample is
      recorded and described as a resample. Output dimensions are not evidence of
      recovered resolution.
- [ ] Expression-driven folds, such as forehead lines in an open-mouth portrait, were
      kept. They are part of the expression, not age damage.
- [ ] Original file retained. Outputs labeled if multiple variants are generated.

## Grain checks

Grain is the one texture this skill can add, and only under disclosure.

- [ ] Grain decision established from the source, not from the year alone:
      `preserved`, `recovered`, `reconstructed`, or `none`.
- [ ] Flat regions still show texture. Check the sky, a wall, or an out-of-focus
      at 100%. Smooth and textureless means grain was destroyed.
- [ ] Clump size is approximately `source × scale`. A 2× upscale must show
      grain twice as large in pixels and identical in structure.
- [ ] Texture is not uniform and identical everywhere, which would mean the
      upscaler substituted synthetic texture.
- [ ] No crunchy noise concentrated at edges (that is sharpened grain, not
      preserved grain).
- [ ] On a print scan, paper surface texture and film grain were not confused
      or amplified together.
- [ ] Retouched areas of a studio portrait were not given grain back.
- [ ] Chroma grain accounted for: colour negative grain is mostly chroma, so a
      suspiciously smooth colour image with intact luminance texture has had a
      chroma pass.
- [ ] If grain was synthesized, it was explicitly requested, is disclosed in the
      delivery, and is recorded by `finalize.py --grain reconstructed`.

## Metadata checks (hard)

A clean image that lost its history is a failed restoration, so these are not
soft checks.

- [ ] `DateTimeOriginal` is byte-identical to the source. The capture date never
      moves, not even to record the processing time.
- [ ] Camera, lens, GPS, rating, title, and keywords from the source are present.
- [ ] ICC profile carried.
- [ ] `Orientation` is `1`. An inherited 6 or 8 rotates an already-upright image.
- [ ] `ExifImageWidth` / `ExifImageHeight` match the real output pixels, not the
      source's. Half-copied metadata that states the old size is worse than none.
- [ ] Existing caption is still present as a substring. The provenance sentence
      was appended, not substituted.
- [ ] No source keyword was dropped.
- [ ] Provenance records when, where, which mode and at which sizes: the sentence in
      `UserComment`, the structured event in `XMP-xmpMM:History`.
- [ ] The capture date provenance is stated. A date the library supplied is reported as
      a catalog date, and a `pass` is not described as proof the date is historically
      right.
- [ ] Re-running the finalize step does not stack the provenance sentence twice.
- [ ] `scripts/finalize.py` reported `pass`. A `fail` means do not deliver and do
      not import into Photos.
- [ ] A `degraded` result was reported to the owner, naming what was lost rather
      than claiming preservation.

## Procedure

1. View source and result side-by-side in identical framing at the same
   *apparent* size. Look for scene/content drift.
2. View at 100% output scale. Look for noise, sharpening, texture artifacts.
3. Compare source and result *faces* at matched apparent size. Inspect
   vulnerable details individually. Repeat for all people.
4. If possible, shrink the enhanced result to source dimensions and
   compare again. Pixel increases can conceal geometry/expression drift.
5. If uncertain, choose the less aggressive restoration.

Optionally create a comparison sheet:

```sh
python scripts/compare.py original.jpg enhanced.png \
  --out comparison.png \
  --crop 150,100,340,360
```

The crop is `[left,top,right,bottom]` in source pixels, optional.
The comparison utility does *not* assert identity preservation. Its purpose
is to make mismatches easier for a human/vision reviewer to notice.
