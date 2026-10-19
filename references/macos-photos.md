# macOS and Apple Photos

On a Mac the photograph usually lives in Photos.app, and the usual gesture is to
drag it into the chat window. That gesture is convenient and it is not
trustworthy. This reference covers getting the authoritative file, and getting
the result back into the library intact.

`osxphotos` is optional. Everything here degrades to plain file paths.

## The problem with a dragged file

A file that arrives by drag-and-drop is a **copy of unknown provenance**. A chat
client or browser upload may hand over a re-encoded render with metadata
stripped or rewritten, at reduced dimensions. It is fine as a visual reference
and it is not evidence about the original.

Treat it as a *visual reference* until metadata proves otherwise.

## Preflight: is this the real original?

```sh
exiftool -s -DateTimeOriginal -Make -Model -ImageWidth -ImageHeight FILE
```

Strong evidence it is the original:

- `DateTimeOriginal` is present
- `Make` / `Model` are present
- dimensions are plausible for the camera

Signs it is a render:

- no `DateTimeOriginal`, no `Make`
- round dimensions such as 1024×1024 or 2048×2048
- a `Software` value naming a chat client or browser

If the evidence is missing, ask for the original. Do not restore a re-encode and
call it faithful to a file you never saw.

## Getting the authoritative original

With the photo selected in Photos.app:

```sh
osxphotos uuid                     # prints the UUID of the selection
osxphotos uuid -f                  # same, with filenames
```

Then export just that asset, read-only, into the project:

```sh
osxphotos export ./source --uuid <UUID> --sidecar xmp --export-aae
```

Notes:

- Do **not** pass `--skip-edited`. For a photo the owner has already adjusted,
  the edited render is the version they have seen and approved, and it is the
  one to restore. For archival work on the unedited original instead, export the
  master file as well and pass it to `new-project.py --master`, which copies it
  in as `<stem>_master.<ext>` beside the source. `finalize.py` has no `--master`
  option: you choose which file is SOURCE by which path you pass.
- `--sidecar xmp` keeps a machine-readable record beside the file, useful when
  the container cannot hold everything.
- `--export-aae` keeps the non-destructive edit recipe. If the result is later
  re-imported, the adjustments stay intact.
- Export writes to a new directory. It does not modify the library.

If no UUID is available, search instead:

```sh
osxphotos query --name IMG_1234.HEIC --print "{uuid} {original_filename}"
osxphotos query --from-date 1990-01-01 --to-date 1990-12-31 --print "{uuid} {original_filename}"
```

Keeping the photo selected requires the owner to be at the machine. When the
agent cannot see Photos.app, ask them to select it and say when done, or to paste
the UUID. That human step is normal, not a failure.

## Returning the result: import, intact

This is the main reason `osxphotos` is in this skill. The restored file should
become a proper library asset — filed at its **original capture date**, in a
named album, carrying its keywords — rather than an orphan dated today.

Because `finalize.py` has already written correct `DateTimeOriginal` and the
capture tags, this lands in the right place chronologically:

```sh
osxphotos import ./output/IMG_1234_upscale.jpg \
  --album "<project> restored" \
  --keyword "photo-upscale-enhance" \
  --skip-dups
```

- `--album` accepts a template and creates the album if missing.
- `--skip-dups` prevents a second copy on a re-run.
- `--sidecar` can pull keywords, title, and description from an XMP sidecar
  instead of flags.
- Import adds an asset. The original is not replaced, and the skill should say
  that plainly so nobody wonders which file is which. The restored file is
  identifiable by its suffix and its provenance sentence.

## The command that must never run

```sh
osxphotos push-exif        # DO NOT USE
```

Its own help text says "Write photo metadata to original files in the Photos
library." That is the exact operation this skill must not perform. It looks like
a reasonable next step when you have metadata in hand and a library in view, and
it is the one thing that would modify the originals.

If a user asks for metadata to be written into library originals, stop and say
why this is out of scope: the original is evidence.

## After import, confirm

```sh
osxphotos query --uuid <new-uuid> --print "{original_filename} {date} {keyword}"
```

Check that the capture date matches the source and that the keywords arrived. If
the asset files under today's date instead of its capture date, the metadata did
not survive and the import should be redone after fixing it.

## When osxphotos is not installed

```sh
command -v osxphotos || echo "not installed"
```

Without it:

1. Ask for a file path, or for the photo to be dragged into a folder on disk.
2. Restore from that file.
3. Finalize as usual; metadata handling is unchanged.
4. Tell the user to import the result by dragging it into Photos.app. Warn that
   Photos may file it under today's date, since drag-import does not always read
   EXIF capture time.

## Checklist

- [ ] Preflighted the delivered file; it is the original, not a render
- [ ] `source/` holds the edited render for an adjusted photo (or the master copied in with `--master` used deliberately)
- [ ] `finalize.py` reported `pass`
- [ ] Imported into a named album with `--skip-dups`
- [ ] Confirmed the new asset carries the capture date
- [ ] Told the user there are now two assets: original and restored
- [ ] `push-exif` was never run
