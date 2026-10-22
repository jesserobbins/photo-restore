# Design notes

This page gives the reason for each rule. Read it before you change the skill. It
also names the limits that the skill does not remove.

## The starting idea

A photograph is an archive item. It is not only a group of pixels. Two results
follow from that.

The fidelity of the photo is the product. The common failure of an AI restore is
not softness. The common failure is a face that looks like a different person. The
skill therefore names what must not change: identity, expression, gaze, pose,
proportions, clothing and background. A soft result that still looks like the person
wins over a sharp result that does not. The priority list is explicit, so a trade
has a known answer.

The record matters as much as the image. A restore that returns sharp pixels and no
capture date, camera, place or caption improved the photo and destroyed the archive.
The file is what someone keeps in ten years, so the metadata is part of the
deliverable.

## Why there are three modes

The skill began with one rule: conservative is the acceptance rule. A real session
showed that one rule cannot answer two different kind of request, and the result was
two failures that look opposite and share a cause.

The first pass did what the rule said and the owner said it did not look as though
anything had happened. Later, when the owner asked for skin smoothing and a small
nostril adjustment, the same rule read those requests as forbidden beauty retouching.
Neither was a prompt problem. The skill had no way to say what had been asked for, so
every request had to be argued against a prohibition written for a different request.

Three modes fix that by giving each request its own acceptance rule. Faithful repair
keeps the original rule. Requested retouch makes the owner's named change locally and
protects the features nobody named. Generative interpretation allows a different
quality tradeoff with identity and composition unchanged. The default is still the
conservative one, so nothing about the earlier behavior is lost; it is now one mode
instead of the only one.

The mode is recorded and disclosed for the same reason grain is. A file that says
"faithful repair" is making a claim a reader can check, and a generative run that did
not say so would read as recovered detail.

## The empty-file rule

The output file holds the pixels from the render and the record from the source. It
holds nothing that the render claims.

A render is the output of a tool, and such a tool puts its own values in the file:
its camera, its location, a processing time, a comment, a caption. None of those
values is evidence about the photograph. When one of them reaches the output file, no
reader can tell it from the metadata of the source, and the reader trusts it.

The script therefore works on an empty file. It strips the staged file with
`exiftool -all=` and then writes the tags from the source onto it.

An earlier design copied all the tags and then removed the tags that the render had
invented. That design needed one entry for each tag that a tool can write: dates,
camera, GPS, caption, comment, thumbnail, dimensions and orientation. Each new entry
opened the next gap. One entry removed a date that the source really had, because
the check used one flag from a different tag. One strip is a known quantity. A list
of exceptions is not.

If you change this part, keep the strip. A design that copies first and removes
later will grow the same faults.

## The provenance sentence and the capture date

One sentence records the time and the tool of the upscale:

> Upscaled 2.0x (4000x3000 to 8000x6000) by photo-restore 2.2, faithful repair mode,
> on 2026-10-19. Source: IMG_1234.jpg. Capture date unchanged.

The sentence names the mode because the mode is a claim about where the detail came
from. Faithful repair claims nothing beyond the source. A generative run appends a
disclosure, and a date that the library supplied rather than the file appends its own,
so neither can pass as something it is not. The script verifies both the way it
verifies the grain disclosure: by reading them back out of the written file.

The script writes the sentence to five places. The places are `Software`,
`CreatorTool`, `UserComment`, `XMP-xmpMM:History`, and the caption and keywords.
Different readers look in different places, so one place is not enough.

The processing time goes into the history entry and the comment. It never goes into
`DateTimeOriginal` or `CreateDate`. A processing time in a date field moves a 1962
photograph to 2026 in a library sort, and an archive does not want that.

The script adds to the existing values. It does not replace them. A caption and a
comment belong to the owner, and a restore tool that removes a caption is no
different from a tool that loses data.

## Film grain

Grain is in the negative. The grains of silver halide become clouds of dye in a C41
process. A print shows the same grain, made larger by the magnification of the
print. The print also adds the texture of the paper, at another frequency.

The grain size therefore follows from the film stock, the ISO and the print size.
The year of the photo is a test. A 1997 negative at ISO 400 has visible grain. A
scan of that photo with no grain went through a denoise step. The year tells you
that the grain is missing. The year does not tell you to add grain.

The script can still add grain, because an owner can want it. Three conditions
apply. The owner must ask for it. The grain must match the pattern of that stock.
The file must say that the grain is new. The line between a restore and a decoration
is the difference between rebuilding weak grain from the flat areas of the source
and making grain from a profile.

A faithful 2x upscale makes the grain two times larger in pixels. That result is
correct. A flat area with no texture means the grain was lost. It does not mean the
noise reduction worked.

## Apple Photos

The `osxphotos` tool brings the result into the library as a new item. The item has
the capture date, it goes into a named album, and it keeps its keywords. It does not
appear as an item with today as the date.

The skill names `push-exif` as a command that you must not run. Its help text says
"Write photo metadata to original files in the Photos library". It is the one
command that changes the originals, and an agent that holds metadata and sees a
library can think it is the next step.

## Work that the skill does not do

- The skill has no upscaler, no face model and no weights. It uses the image model
  that the agent has. The rules and the checks make the result a restore.
- The skill ships no image operation at all, and this is the line that keeps it
  useful. A skill that bundled a model would need a download, a GPU host and a
  workflow, and it would then only work where those things are installed. The point
  of the skill is that it makes whatever editing tool the agent already has behave
  well. Three real failures asked for a script each — a red-eye fix, an alpha mask,
  a JPEG 2000 decode — and all three became guidance and checks instead, because
  the pixels belong to the agent's tool.
- The skill does not edit metadata. It copies the tags, it corrects the tags that the
  upscale made false, and it adds the provenance.
- The skill does not manage the library. It does not delete, deduplicate or
  reorganize photos.

## Known limits

- A Pillow encode of a 16-bit RGB TIFF writes 8 bits. Pillow also reports that input
  as 8 bits, so a rotated 16-bit RGB TIFF can lose depth with no warning. The script
  has no signal to detect it.
- Without `exiftool`, the script carries only the raw EXIF block and the color
  profile. The run reports `degraded` and names each gap.
- The script does not merge the caption of a sidecar when the output has translated
  XMP descriptions. A plain `Description` write removes the translations. The run
  reports the skipped merge as a shortfall.

## Behaviors to know before you edit the scripts

Each item below was tested against exiftool 13.55. Each one fails with no message
when you get it wrong.

1. `-all:all` wins over an explicit value in the same command. Copy and correct
   need two separate commands.
2. `-Orientation=1` does nothing. `-Orientation#=1` works. The `#` makes the value
   numeric.
3. The writable dimension tags are `ExifImageWidth` and `ExifImageHeight`.
   `PixelXDimension` is not a valid name for a write.
4. `-Keywords+=` adds to a list tag. `-Caption-Abstract+=` does a numeric shift on a
   string tag, and the value is lost with only a warning.
5. `-ICC_Profile:all` writes nothing into a file that has no profile. The plain
   `-ICC_Profile` writes it.
6. `-s3` joins the items of a list with `", "`. If you split that text on commas,
   the keyword `Washington, D.C.` becomes two keywords. Read a list tag as JSON.

## What the review page taught

Nine review rounds found 60 problems in the review page. All of them are fixed. Two
results are worth keeping.

A test of the markup is not a test of the page. The range input was a sibling of the
slider element, so the script stopped at setup. Record, Done and Download never ran,
and every Python test passed because each test only checked that the elements
existed. The suite now loads a real page in a browser, moves a slider and records a
verdict, and it fails on any error from the page. A second round put a real newline
inside a string in the script, and the browser test found it at once.

One fault class came back five times. The key that identifies a photo in the verdict
file was first the file name, then the folder and the file name, then a value that
depended on the other photos in the run, then the path from the project, and finally
the path from the verdict file. Each version was correct for the case in front of
it. The version that holds uses the pair and the location of the verdict file,
because those are the two values that must stay the same for a verdict file to mean
anything.

The lesson is the same as for the metadata work. When one class of fault comes back,
the mechanism is wrong.


## Why the description states triggers only

The description in `SKILL.md` names the situations that call for this skill. It does
not summarize the workflow.

A description that summarizes the workflow gives a model enough to act without
reading the body. I tested that on this skill. Five fresh agent runs saw the older
description, which listed what the skill keeps and carries. Every run produced a
three step restoration plan from the description alone: inspect, keep the original
and its metadata, restore conservatively and compare. Each run then said it would
still read the body, but the plan was already there to follow under time pressure.

Five runs with a trigger-only description produced no plan. Each run said the
description was enough to select the skill and named reading the body as its first
step.

The tradeoff is real. The skills directory shows the description in its listing, and
a trigger list sells less than a summary. The README, llms.txt and the repository
description carry the sales copy. The description is for the model that must decide
whether to read the skill.
