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
