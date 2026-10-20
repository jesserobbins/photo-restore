# Design notes

Why the skill is shaped the way it is. Useful if you intend to change it, and
honest about where the sharp edges are.

## The premise

A photograph is an archival object, not a bag of pixels. Two things follow.

**Fidelity is the product.** The interesting failure of AI photo restoration is
not softness, it is a plausible stranger. So the skill states what must not change
— identity, expression, gaze, pose, proportions, clothing, background — and
prefers a softer result that still looks like the person. Improvement is allowed
only where it does not cost fidelity, and the priority order is explicit so a
trade can be resolved without argument.

**The record matters as much as the image.** A restore that returns sharp pixels
with no capture date, camera, place, or caption improved the photograph and
destroyed the archive. The file is what gets kept in ten years, so the metadata is
part of the deliverable, not a nicety.

## The blank-slate rule

The output carries the render's pixels and the source's record. Never the render's
claims.

A render is whatever tool produced it, and those tools stamp things: their own
camera, their own location, a processing timestamp, a comment, a caption. None of
that is evidence about the photograph. If it reaches the delivered file it is
indistinguishable from the source's own metadata, and it will be believed.

So the metadata pass works on a blank slate: the staged file is stripped with
`exiftool -all=`, then the source's tags are written onto it.

This replaced an earlier design that copied everything and then un-copied what the
render had invented. That version needed an entry for every tag a tool might stamp
— dates, camera, GPS, caption, comment, thumbnail, dimensions, orientation — and
each addition created the next gap. One of them cleared a date the source genuinely
had, because the check was a single flag derived from a different tag. Stripping
once is bounded; enumerating is not.

If you change this area, keep the strip. Anything that reintroduces "copy then
remove" will grow the same class of bug.

## Provenance, and why the capture date never moves

One sentence records when and where the upscale happened:

> Upscaled 2.0x (4000x3000 to 8000x6000) by photo-restore 2.0, conservative mode,
> on 2026-10-19. Source: IMG_1234.jpg. Capture date unchanged.

It is written to `Software`, `CreatorTool`, `UserComment`, `XMP-xmpMM:History`,
and appended to the caption and keywords. Different readers look in different
places, so one location is not enough.

The processing time goes in the history event and the comment, never in
`DateTimeOriginal` or `CreateDate`. Writing it there would refile a 1962
photograph as a 2026 one, which is the opposite of what an archive wants.

Append, never replace. Captions and comments are the owner's words, and a
restoration tool that eats someone's caption is indistinguishable from data loss.

## Grain

Grain belongs to the negative: silver halide crystals, dye clouds in C-41. A print
shows that same grain enlarged by the print's magnification, plus paper surface
texture at a different frequency.

That makes grain size predictable from stock, ISO, and enlargement, which makes
the era a **diagnostic**. A uniformly smooth scan of a 1997 400-speed negative is
evidence of a denoise pass, because film that fast was not that clean. The year
tells you grain was destroyed; it is not a recipe for adding grain back.

Synthesis is still available, because an owner may want it, but it is gated: only
when asked, matched to what the stock actually did, and disclosed in the file. The
distinction between recovering attenuated grain from the source's own flat regions
and synthesizing grain from a profile is the whole line between restoring and
decorating.

One consequence that gets missed: a faithful 2x upscale leaves grain twice as large
in pixels. That is correct. Flat, textureless output is a grain failure, not a
cleanup success.

## Apple Photos

`osxphotos` is here to bring the result *into* the library intact — filed at its
capture date, in a named album, carrying its keywords — rather than appearing as an
orphan dated today.

`push-exif` is named as forbidden because its own help text is "Write photo
metadata to original files in the Photos library". It is the one operation that
would modify the originals, and it looks like a reasonable next step to an agent
holding metadata and a library.

## What is deliberately not automated

- No upscaler, face model, or weights. The skill orchestrates whichever image
  model you have, and the fidelity rules plus the checks are what make the result
  a restoration.
- No metadata editor. Copy, correct what the upscale made false, append
  provenance. Nothing else.
- No library management. Deleting, deduplicating, and reorganizing photos is out
  of scope.

## Known limits

- Any Pillow re-encode of a 16-bit RGB TIFF yields 8-bit RGB, and Pillow presents
  that input as 8-bit, so a rotated 16-bit RGB TIFF can lose depth without a
  warning. There is no signal to detect the demotion.
- On a host without `exiftool`, only the raw EXIF blob and ICC profile cross. The
  run reports `degraded` and names the gap.
- A sidecar's caption is skipped, with a shortfall, when the output carries
  translated XMP descriptions, because a bare `Description` write deletes the
  translations.

## Behaviours worth knowing before you edit

These were verified against exiftool 13.55 and each fails *silently* if you get it
wrong:

1. `-all:all` beats explicit assignments in the same invocation. Copy and correct
   need separate passes.
2. `-Orientation=1` is ignored; `-Orientation#=1` works. The `#` forces numeric.
3. The writable dimension tags are `ExifImageWidth` / `ExifImageHeight`.
   `PixelXDimension` is rejected as undefined.
4. `-Keywords+=` appends to list tags, but `-Caption-Abstract+=` is a numeric shift
   on a string tag and the value is dropped with only a warning.
5. `-ICC_Profile:all` writes nothing to a file that has no profile; the plain
   `-ICC_Profile` tag is what writes it.
6. `-s3` joins list values with `", "`, so reading keywords that way and splitting
   on commas destroys a keyword like `Washington, D.C.`. Read list tags as JSON.
