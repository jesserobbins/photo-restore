# Metadata, naming, and output format

The restored file is what gets kept. If it arrives without the capture date, the
camera, the place, the caption, and the keywords, then the restoration improved
the pixels and destroyed the archive. This reference defines what to preserve,
what to correct, and what to record.

## The rule that matters most

The metadata belongs to the source, not to the process. Copy it, correct only
what the upscale made false, append your provenance, and never replace the
owner's words.

### The output carries the render's pixels, never its claims

A render is whatever tool produced it, and those tools stamp things: their own
camera, their own location, a processing timestamp, a comment, a caption. None of
that is evidence about the photograph.

So the metadata pass works on a blank slate. When the pixels are copied
through unchanged, the staged file is stripped of everything (`exiftool -all=`)
before the source's metadata is written onto it. What arrives is the source's,
and there is nothing to un-invent.

This replaced an earlier design that copied everything and then cleared what the
render had invented. That version needed an entry for every tag a tool can
stamp -- dates, camera, GPS, caption, comment, thumbnail, dimensions -- and each
addition created the next gap. Stripping once is bounded. Enumerating is not.

## What travels, and what changes

| Tag | Action | Why |
| --- | --- | --- |
| `DateTimeOriginal`, `CreateDate`, subseconds, offset | Copy unchanged | The photo must keep filing at its capture time. Moving this refiles the photo at the top of a library and looks like a new picture. |
| `Make`, `Model`, `LensModel`, `SerialNumber`, exposure, ISO, focal length | Copy unchanged | Still the same camera and the same exposure. |
| GPS block | Copy unchanged | Still the same place. |
| `Rating`, `Keywords`, `Subject`, `Title` | Copy unchanged, then add | These are the owner's organization, not yours. |
| `Caption-Abstract`, `XMP-dc:Description` | Append | The owner's words. A restoration that eats a caption is indistinguishable from data loss. |
| ICC profile | Copy unchanged | Color intent. |
| `Orientation` | Set to `1` | Pixels are already upright, so an orientation tag left at 6 or 8 rotates a correct image. |
| `ExifImageWidth`, `ExifImageHeight` | Set to actual output pixels | Half-copied metadata that states the old dimensions is worse than no metadata, because it lies confidently. |
| `Software`, `XMP:CreatorTool` | Set to tool and version | |
| `XMP-xmpMM:History` | Append one event | The structured, machine-readable record. Read by Lightroom, Bridge, Photoshop. |
| `EXIF:UserComment` | Append the provenance sentence | A source comment is the owner's words too, so it is appended to, not replaced. |
| `ThumbnailImage`, `PreviewImage` | Cleared | `-all:all -unsafe` can carry the source's embedded thumbnail, which is a pre-restoration image that Finder and some DAMs display instead of the real pixels. Cleared explicitly and verified absent. |

## Provenance: when, where and how the upscale happened

One sentence, written to every place a different reader looks:

> Upscaled 2.0x (4000x3000 to 8000x6000, delivered from the model's 3620x2715 output
> resampled by lanczos) by photo-restore 2.2, faithful repair mode, on 2026-10-19.
> Source: IMG_1234.jpg. Capture date unchanged.

The mode is part of the sentence because the sentence is the only claim about how the
detail was produced. A generative run appends:

> Detail was reconstructed by a generative model; it is not recovery of detail lost
> from the source.

### Three sizes, and why all three are recorded

| Fact | Where it comes from | What it answers |
| --- | --- | --- |
| Source size | the source file | what the photograph holds |
| Native size | the model's own output, before any resample | how much detail the model produced |
| Delivery size | the output file | what the owner receives |

A larger delivery size does not mean more recovered detail. A model that returns
fewer pixels than the source is common, and resampling that render to 2× is a
resample. When the delivered file is larger than the native render, name both and the
method. `finalize.py --native-dims WxH --resample METHOD` records them in the manifest
and in the sentence. Without `--native-dims` the script cannot know, and the sentence
must not imply otherwise.

| Location | Reader |
| --- | --- |
| `Software`, `XMP:CreatorTool` | ingest tools, Adobe apps |
| `UserComment` | most viewers' metadata panel |
| `XMP-xmpMM:History` | Lightroom / Bridge / Photoshop edit history |
| `XMP-dc:Description`, `IPTC:Caption-Abstract` | search, DAMs, Photos.app |
| `IPTC:Keywords` | Photos.app tagging and search |

The keywords `upscaled` and `photo-restore` make a batch findable later.
`--keyword` adds more. `--No-keywords` suppresses them.

### When goes in the history, not in a date field

The "when" is the processing time. It belongs in `xmpMM:History` and
`UserComment`. It must never go into `DateTimeOriginal` or `CreateDate`,
because that would silently refile a 1962 photograph as a 2026 one. This is the
whole reason for writing provenance to a separate field.

### Where the capture date came from

A date in a tag and a date in a library catalog are different facts. A scan of a print
can have no embedded capture date at all, and Photos still files it under a timestamp.
Copying that timestamp keeps the library in order, which is what the owner wants, and
it says nothing about when the photograph was taken.

`finalize.py --date-source` records the provenance, and every value except `embedded`
adds a sentence to the file:

| Value | Meaning | Sentence added |
| --- | --- | --- |
| `embedded` | the source file carries the capture date | none |
| `catalog` | the photo library supplied the date | the date was copied from the catalog; the source carries none |
| `owner` | a person stated the date | the date is not embedded capture metadata |
| `unknown` | nobody established it | the provenance is unknown |
| `auto` (default) | `embedded` when `DateTimeOriginal` is present, otherwise `unknown` | as derived |

A metadata `pass` reports that the tags the source had are still there. It is not a
statement that the date is historically right, and it must not be described as one.
Delete the date, edit any tag after the finalize step, or re-export the file, and the
whole verification runs again.

### Idempotency

Re-running the finalize step on the same file must not stack the sentence
repeatedly. Before appending, check whether this tool's marker for this scale is
already present, and skip if so. `--note` replaces the default wording. 
`--no-appearance-tags` leaves captions entirely untouched.

## Naming

`<source-stem><suffix>.<ext>`

| Suffix | Meaning |
| --- | --- |
| `_upscale` | Default. The faithful variant. |
| `_enhance` | The higher-detail variant, when the user asked for two outputs. |

The suffix matches the vocabulary already used in the fidelity rules, so a
filename and a delivered claim say the same thing.

Collisions append `-2`, `-3`. An existing file is never silently overwritten. 
`--force` is the explicit opt-in. Keeping the source stem is what makes a folder
of results sort next to its originals and stay traceable.

## Output format

Default (`--format auto`) follows the source container:

| Source | Output | Note |
| --- | --- | --- |
| JPEG | JPEG q95, no chroma subsampling | No extra generation when the render is already JPEG. The script copies the pixels and does not encode them again. |
| PNG | PNG | |
| TIFF | TIFF (LZW) | |
| HEIC / HEIF / AVIF | JPEG | Pillow cannot decode these. ImageMagick or macOS `sips` is required. The script refuses rather than writing pixels it can not read. |

PNG can hold EXIF, IPTC, and XMP. Exiftool writes and reads all of it. The
reason JPEG is the default is narrower: consumer readers such as Photos.app,
Preview, and most viewers ignore PNG's metadata chunks. Portable metadata is
worth more than pixel purity for an archive.

`--format png` is available for anyone who wants the lossless render. Say plainly
that it trades away portable metadata when you use it.

## What the finalize step verifies

Order is fixed: encode, then copy, then correct, then verify. Copying before
encoding loses everything. Verifying before correcting measures the wrong thing.

The check compares the output against the source and against its own pixels:

- every core tag the source had is still present, on both the exiftool and the
  degraded path
- the output container matches what was asked for, decided by contents rather
  than by filename
- `DateTimeOriginal` is byte-identical to the source
- `Orientation` is horizontal
- real pixel dimensions match what the run recorded, and `ExifImageWidth` agrees
  with the real width
- aspect ratio did not drift
- the provenance note is present
- the original caption is still a substring of the new caption
- the source's `UserComment` is still a substring of the new one
- no source keyword was dropped
- no embedded thumbnail or preview survives

| Result | Meaning | What to do |
| --- | --- | --- |
| `pass` | Everything carried. | Deliver. |
| `degraded` | A known gap: exiftool absent, so only the raw EXIF blob and ICC profile crossed and provenance was not written. Or an ICC profile dropped because it no longer describes the output pixels. Exit 0, shortfall listed. | Report the shortfall it names rather than describing it as an exiftool gap. |
| `fail` | A core tag is missing, a dimension tag disagrees, or a caption was replaced. Exit 1, file renamed `*_UNVERIFIED`. | Do not deliver. Do not import into Photos. |

## Verified exiftool behavior

Each of these produces a wrong result rather than an error, so they are worth
knowing before trusting a one-line command:

1. `-all:all` wins over explicit assignments in the same invocation.
   `-TagsFromFile src -all:all -Orientation#=1` leaves the copied orientation in
   place. Overrides need a second pass.
2. `-Orientation=1` is silently ignored. `-Orientation#=1` works. The `#`
   forces numeric assignment.
3. The writable dimension tags are `ExifImageWidth` / `ExifImageHeight`.
   `PixelXDimension` and `PixelYDimension` are rejected as undefined.
   `ImageWidth`/`ImageHeight` are updated automatically.
4. `-Keywords+=` appends to list tags, but `-Caption-Abstract+=` does not.
   On string tags `+=` is a numeric shift. Exiftool warns "Shift value is not a
   number" and drops the value. Read the old value and write the concatenation.
5. The history tag is `XMP-xmpMM:History`, written as
   `-XMP-xmpMM:History+={Action=saved,SoftwareAgent=...,When=...}`. `XMP:History`
   does not exist and silently lands somewhere useless.

Working two-pass recipe:

```sh
# 1. strip the render completely, THEN copy the source in. Without this step a
#    render's own capture date, camera or location survives next to the source's
#    and cannot be told apart afterwards. This is the blank-slate rule, and
#    skipping it is how a manual restore invents a capture date.
exiftool -overwrite_original -all= "$DST"
exiftool -overwrite_original -TagsFromFile "$SRC" -all:all -unsafe "$DST"

# 2. the render's own profile must not survive, and the source's must not be
#    pasted onto render pixels. Carry the profile that matches the pixels, or
#    none at all -- never the source's. Step 1 already stripped the render's, so
#    only restore one if the render had a profile that still applies:
#      exiftool -overwrite_original -TagsFromFile "$RENDER" -ICC_Profile "$DST"
#    Skip that line when the render was re-encoded into a different colour model.

# 3. append to the owner's words, never replace them. UserComment included:
#    a scanner note or a previous editor's remark is someone else's record.
EXISTING=$(exiftool -q -s3 -UserComment "$DST")
if [ -n "$EXISTING" ]; then NOTE="$EXISTING $NOTE"; fi

# 3. correct what the upscale made false, and record provenance
exiftool -overwrite_original -Orientation#=1 -XMP-tiff:Orientation#=1 \
  -ExifImageWidth="$W" -ExifImageHeight="$H" \
  -ThumbnailImage= -PreviewImage= \
  -Software="photo-restore 2.2" \
  -UserComment="$NOTE" \
  "-XMP-xmpMM:History+={Action=saved,SoftwareAgent=photo-restore 2.2,When=$NOW}" \
  "$DST"
```

`XMP-tiff:Orientation` is corrected alongside the EXIF tag because `-all:all`
copies it too, and readers that prefer XMP will otherwise rotate upright pixels.

One known limit, and `exiftool` does not lift it: any Pillow re-encode of a
16-bit RGB TIFF yields 8-bit RGB, because Pillow presents that input as 8-bit.
A rotated 16-bit RGB TIFF is re-encoded whenever orientation has to be baked, so
it can be demoted without a warning even with `exiftool` installed. Convert such
a file with a tool that preserves depth, or accept 8 bits deliberately.

## When there are no scripts

On a host with no filesystem and no Python, no verification is possible. Do not
claim metadata was preserved. Give the user the exiftool commands above with
their actual filenames and a short checklist of the tags to confirm, and say
plainly that the commands were not run here.
