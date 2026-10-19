# Metadata, naming, and output format

The restored file is what gets kept. If it arrives without the capture date, the
camera, the place, the caption, and the keywords, then the restoration improved
the pixels and destroyed the archive. This reference defines what to preserve,
what to correct, and what to record.

## The rule that matters most

**The metadata belongs to the source, not to the process.** Copy it, correct only
what the upscale made false, append your provenance, and never replace the
owner's words.

## What travels, and what changes

| Tag | Action | Why |
| --- | --- | --- |
| `DateTimeOriginal`, `CreateDate`, subseconds, offset | Copy unchanged | The photo must keep filing at its capture time. Moving this refiles the photo at the top of a library and looks like a new picture. |
| `Make`, `Model`, `LensModel`, `SerialNumber`, exposure, ISO, focal length | Copy unchanged | Still the same camera and the same exposure. |
| GPS block | Copy unchanged | Still the same place. |
| `Rating`, `Keywords`, `Subject`, `Title` | Copy unchanged, then add | These are the owner's organization, not yours. |
| `Caption-Abstract`, `XMP-dc:Description` | **Append** | The owner's words. A restoration that eats a caption is indistinguishable from data loss. |
| ICC profile | Copy unchanged | Color intent. |
| `Orientation` | Set to `1` | Pixels are already upright, so an orientation tag left at 6 or 8 rotates a correct image. |
| `ExifImageWidth`, `ExifImageHeight` | Set to actual output pixels | Half-copied metadata that states the old dimensions is worse than no metadata, because it lies confidently. |
| `Software`, `XMP:CreatorTool` | Set to tool and version | |
| `XMP-xmpMM:History` | Append one event | The structured, machine-readable record. Read by Lightroom, Bridge, Photoshop. |
| `EXIF:UserComment` | **Append** the provenance sentence | A source comment is the owner's words too, so it is appended to, not replaced. |
| `ThumbnailImage`, `PreviewImage` | **Cleared** | `-all:all -unsafe` can carry the source's embedded thumbnail, which is a pre-restoration image that Finder and some DAMs display instead of the real pixels. Cleared explicitly and verified absent. |

## Provenance: when and where the upscale happened

One sentence, written to every place a different reader looks:

> Upscaled 2.0x (4000x3000 to 8000x6000) by photo-upscale-enhance 2.0,
> conservative mode, on 2026-10-19. Source: IMG_1234.jpg. Capture date unchanged.

| Location | Reader |
| --- | --- |
| `Software`, `XMP:CreatorTool` | ingest tools, Adobe apps |
| `UserComment` | most viewers' metadata panel |
| `XMP-xmpMM:History` | Lightroom / Bridge / Photoshop edit history |
| `XMP-dc:Description`, `IPTC:Caption-Abstract` | search, DAMs, Photos.app |
| `IPTC:Keywords` | Photos.app tagging and search |

The keywords `upscaled` and `photo-upscale-enhance` make a batch findable later.
`--keyword` adds more; `--no-keywords` suppresses them.

### When goes in the history, not in a date field

The "when" is the processing time. It belongs in `xmpMM:History` and
`UserComment`. It must **never** go into `DateTimeOriginal` or `CreateDate`,
because that would silently refile a 1962 photograph as a 2026 one. This is the
whole reason for writing provenance to a separate field.

### Idempotency

Re-running the finalize step on the same file must not stack the sentence
repeatedly. Before appending, check whether this tool's marker for this scale is
already present, and skip if so. `--note` replaces the default wording;
`--no-appearance-tags` leaves captions entirely untouched.

## Naming

`<source-stem><suffix>.<ext>`

| Suffix | Meaning |
| --- | --- |
| `_upscale` | Default. The faithful variant. |
| `_enhance` | The higher-detail variant, when the user asked for two outputs. |

The suffix matches the vocabulary already used in the fidelity rules, so a
filename and a delivered claim say the same thing.

Collisions append `-2`, `-3`. An existing file is never silently overwritten;
`--force` is the explicit opt-in. Keeping the source stem is what makes a folder
of results sort next to its originals and stay traceable.

## Output format

Default (`--format auto`) follows the source container:

| Source | Output | Note |
| --- | --- | --- |
| JPEG | JPEG q95, no chroma subsampling | No extra generation when the render is already JPEG — pixels are copied, not re-encoded. |
| PNG | PNG | |
| TIFF | TIFF (LZW) | |
| HEIC / HEIF / AVIF | JPEG | Pillow cannot decode these. ImageMagick or macOS `sips` is required; the script refuses rather than writing pixels it could not read. |

PNG *can* hold EXIF, IPTC, and XMP — exiftool writes and reads all of it. The
reason JPEG is the default is narrower: consumer readers such as Photos.app,
Preview, and most viewers ignore PNG's metadata chunks. Portable metadata is
worth more than pixel purity for an archive.

`--format png` is available for anyone who wants the lossless render. Say plainly
that it trades away portable metadata when you use it.

## What the finalize step verifies

Order is fixed: **encode, then copy, then correct, then verify.** Copying before
encoding loses everything; verifying before correcting measures the wrong thing.

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
| `degraded` | exiftool absent: only the raw EXIF blob and ICC profile were carried. Exit 0, shortfall listed. | Say which fields are missing, including that provenance was not written. |
| `fail` | A core tag is missing, a dimension tag disagrees, or a caption was replaced. Exit 1, file renamed `*_UNVERIFIED`. | Do not deliver. Do not import into Photos. |

## Verified exiftool behavior

Each of these produces a wrong result rather than an error, so they are worth
knowing before trusting a one-line command:

1. **`-all:all` wins over explicit assignments in the same invocation.**
   `-TagsFromFile src -all:all -Orientation#=1` leaves the copied orientation in
   place. Overrides need a second pass.
2. **`-Orientation=1` is silently ignored; `-Orientation#=1` works.** The `#`
   forces numeric assignment.
3. **The writable dimension tags are `ExifImageWidth` / `ExifImageHeight`.**
   `PixelXDimension` and `PixelYDimension` are rejected as undefined.
   `ImageWidth`/`ImageHeight` are updated automatically.
4. **`-Keywords+=` appends to list tags, but `-Caption-Abstract+=` does not.**
   On string tags `+=` is a numeric shift; exiftool warns "Shift value is not a
   number" and drops the value. Read the old value and write the concatenation.
5. **The history tag is `XMP-xmpMM:History`**, written as
   `-XMP-xmpMM:History+={Action=saved,SoftwareAgent=...,When=...}`. `XMP:History`
   does not exist and silently lands somewhere useless.

Working two-pass recipe:

```sh
# 1. copy everything
exiftool -overwrite_original -TagsFromFile "$SRC" -all:all -unsafe "$DST"
# 2. correct what the upscale made false, and record provenance
exiftool -overwrite_original -Orientation#=1 \
  -ExifImageWidth="$W" -ExifImageHeight="$H" \
  -Software="photo-upscale-enhance 2.0" \
  -UserComment="$NOTE" \
  "-XMP-xmpMM:History+={Action=saved,SoftwareAgent=photo-upscale-enhance 2.0,When=$NOW}" \
  "$DST"
```

## When there are no scripts

On a host with no filesystem and no Python, no verification is possible. Do not
claim metadata was preserved. Give the user the exiftool commands above with
their actual filenames and a short checklist of the tags to confirm, and say
plainly that the commands were not run here.
