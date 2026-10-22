# Sources the tools do not round-trip

Some sources do not survive the obvious path. A JPEG 2000 scan, a file with
transparent margins, and a render whose color profile no longer describes its pixels
each need a decision before the restore, not after it.

Nothing here is a script this skill runs. The agent's own tool decodes and encodes;
this page says what to check and what to disclose.

## Find out which decoder the host has

Do not assume one. In a real session ImageMagick had no JPEG 2000 decoder, `sips`
read the file, and an existing Pillow environment also read it.

```sh
exiftool -s -FileType -MIMEType -ImageWidth -ImageHeight -Software -ColorSpace SOURCE
sips -g all SOURCE                     # macOS
magick identify SOURCE                 # fails when the delegate is missing
python3 -c "from PIL import Image; im=Image.open('SOURCE'); print(im.mode, im.size)"
```

Pick the first decoder that works, use it for the whole batch, and say which one it
was. Preflight the imports and commands once, then reuse them. Rediscovering a
missing decoder in the middle of a finalize step is how a run ends with half a
result and no record of why.

## Transparent margins

A scanned print often arrives with alpha, and the alpha is the scanner bed, not a
request to cut the subject out. The values span the whole range because the film
holder was uneven.

- Read the alpha channel before you composite anything. Copying opacity from a
  differently shaped image can copy luminance instead, which is what a grayscale
  frame and a lost pupil edit have in common.
- Keep the margins unless the owner asks for a cutout. A generated fill at the
  margin is an invented area, and it belongs in the disclosure if you keep it.
- To keep the original transparency, extract the source alpha channel first and
  apply it to the result. Test that operation on a small file before you run it on a
  full scan.
- JPEG has no alpha. Flattening the margins onto white is a decision: make it
  deliberately, and say so. The source file stays unchanged either way.

## Color profiles

A source profile describes the pixels it was written for. Attaching it to new pixels
does not convert them.

- When the source and the edited render carry different profiles, convert the
  pixels, then write the profile that describes the result. Do not graft the
  source's profile onto a model's output.
- A model's render can carry a different working space from the source. Check both.
- A profile that no longer matches the output must be dropped, and the run reports
  that as a shortfall rather than a pass. `finalize.py` does this, and names it.

## Containers the pipeline cannot keep

- **JPEG 2000** has no encoder in some hosts. Decoding it and delivering TIFF or
  JPEG is a container change: disclose it. Do not claim the source container was
  preserved.
- **HEIC** needs ImageMagick or `sips` for the decode. Pillow cannot read it alone.
- **16-bit** input can lose depth in a Pillow re-encode. The skill's known limit
  covers this, and the run must not describe the result as lossless.

## What to say in the delivery

Name the decoder, the container you delivered, and every decision that changed the
file's shape or transparency. "Restored from a JPEG 2000 scan, delivered as JPEG with
transparent margins flattened onto white, alpha kept in the project copy" is a
sentence a reader can act on. "Format preserved" is not.

## Checklist

- [ ] Decoder established on this host, and reused for the whole batch
- [ ] Alpha channel read before any composite
- [ ] Margins kept, or the cutout decision stated
- [ ] Alpha applied from the source's own channel, tested small first
- [ ] Profiles converted where they differ, and the output's profile describes the output
- [ ] Container change disclosed, with the format named
- [ ] Source file unchanged
