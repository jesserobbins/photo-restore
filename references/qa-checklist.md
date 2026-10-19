# Visual fidelity acceptance checklist

Use this checklist after EVERY pass. Fail any hard check -> reduce the edit,
mask the affected area, or revert to a deterministic baseline.

## Hard checks (must pass)

- [ ] Correct subject count and identities; no invented faces/people.
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
- [ ] Original file retained; outputs labeled if multiple variants are generated.

## Grain checks

Grain is the one texture this skill may add, and only under disclosure.

- [ ] Grain decision established from the source, not from the year alone:
      `preserved`, `recovered`, `reconstructed`, or `none`.
- [ ] Flat regions — sky, wall, out-of-focus background — still show texture
      at 100%. Smooth and textureless means grain was destroyed.
- [ ] Clump size is approximately `source × scale`. A 2× upscale should show
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
- [ ] Existing caption is still present as a substring; the provenance sentence
      was appended, not substituted.
- [ ] No source keyword was dropped.
- [ ] Provenance records when and where: the sentence in `UserComment`, the
      structured event in `XMP-xmpMM:History`.
- [ ] Re-running the finalize step does not stack the provenance sentence twice.
- [ ] `scripts/finalize.py` reported `pass`. A `fail` means do not deliver and do
      not import into Photos.
- [ ] A `degraded` result was reported to the owner, naming what was lost rather
      than claiming preservation.

## Procedure

1. View source and result side-by-side in identical framing at the same
   *apparent* size. Look for scene/content drift.
2. View at 100% output scale. Look for noise, sharpening, texture artifacts.
3. Compare source and result *faces* at matched apparent size; inspect
   vulnerable details individually. Repeat for all people.
4. If possible, shrink the enhanced result to source dimensions and
   compare again; pixel increases can conceal geometry/expression drift.
5. If uncertain, choose the less aggressive restoration.

Optionally create a comparison sheet:

```sh
python scripts/compare.py original.jpg enhanced.png \
  --out comparison.png \
  --crop 150,100,340,360
```

The crop is `[left,top,right,bottom]` in source pixels, optional.
The comparison utility does *not* assert identity preservation; its purpose
is to make mismatches easier for a human/vision reviewer to notice.
