---
name: photo-restore
description: >
  Use when the user asks to restore, upscale, enhance, denoise, deblur or clean up
  an existing photograph, including old prints, scanned prints, family photos and
  group portraits. Also use when the user supplies reference photos of the same
  person, when EXIF, IPTC or XMP metadata must survive the edit, when the film
  grain of a photo is in question, when the source may be a chat-app re-encode, or
  when a restored file must go back into Apple Photos.
metadata:
  version: "2.1.0"
  default-mode: "conservative"
  author: "Jesse Robbins (@jesserobbins)"
  homepage: "https://jesserobbins.com"
  repository: "https://github.com/jesserobbins/photo-restore"
  license: "MIT"
  keywords: "photo restoration, photo upscaling, exif preservation, metadata provenance, film grain, old photo repair, osxphotos, apple photos, archival photography"
  canonical: "https://github.com/jesserobbins/photo-restore"
---

# photo-restore: fidelity first

## Preferred image models

An image model does the pixel work. Models behave in different ways on a restore.
The image models in Gemini and in Codex work well. Use one of them when you have a
choice.

Follow these rules with any model:

- Use the image editing path of the model. Give it the source image to edit. Do
  not write a text prompt that describes the photo. A generated lookalike is not a
  restore, even when it looks good.
- Ask for the lowest edit strength that the tool has. A model can redraw a face at
  full strength and return a different person.
- Make sure that the grain and the texture of the flat areas stay the same. A
  super-resolution step turns grain into blotches. A model that returns smooth skin
  decided that the photo came from a digital camera.
- Match the prompt to the model. The templates in
  [references/prompt-templates.md](references/prompt-templates.md) are written for
  all of them. Remove a clause that a model ignores. Do not assume that the model
  obeys every clause.
- A model can refuse the task or change a subject. This result is normal. Reduce
  the processing, mask the area, or use a deterministic resample. Do not try again
  until the result looks better.

When neither model is available, you can use any model that can edit an image. The
same limits and the same checks apply. The model does the work. The fidelity rules
and the checks make the result a restore.

## Objective and priority

Improve the technical quality of the photo. Do not change what the photo shows.
Fidelity to the source has the highest priority. A soft or an imperfect detail is
better than an invented detail that looks correct.

Order of priorities:

1. Keep the subjects, their identity, their appearance, their expression, their
   posture, their proportions and their relations.
2. Keep the scene geometry, the composition, the clothing, the objects and the
   details of the period.
3. Recover the photographic signal that you can recover.
4. Improve the visible quality: the clarity, the resolution, the tonal range and
   the noise.
5. Improve the look only when it agrees with items 1 to 4.

Never give up a higher priority for a lower one.

## When to use

Use this skill when the user asks to upscale, improve, clean, restore, sharpen,
denoise, deblur or increase the resolution of a photo. It fits portraits, family
photos, group photos, archive photos and scans.

A reference photo of the person is a guide for the identity. It is not content.
This skill does not swap faces. It does not move a face from one photo into another.
It restores the face that the source photo already shows. The owner must have a photo
of the person to use as the source.

When the user supplies reference photos of the same person, use them as identity
limits. Do not use them as replacement content.

If the user asks for a style, a composite, a new pose, a different expression, a
face swap or a new interpretation, say that the request is outside this skill. A
face swap takes the face from a different photo, and that is not a restore.

If the user wants the edit for another purpose, you can do it. Do not call the
result a faithful restore.

## Limits that you must keep

Keep these properties unless the user asks you to change them.

- Face and identity: the bone structure, the jawline, the nose, the eyes and the
  eyelids, the space between the eyes, the ears, the mouth, the teeth, the
  hairline, the wrinkles, the asymmetry, the age, the appearance of the ethnic
  group and the marks on the skin.
- Expression and gaze: the size of the smile, the shape and the opening of the
  lips, the visibility of the teeth, the shape of the eyelids, the direction of the
  eyes and the emotion.
- Body: the silhouette, the build, the proportions of the body and the limbs, the
  hands and the fingers, the posture, the tilt of the head, the angle of the
  shoulders and the relative size.
- Surroundings: the number of subjects, their positions, the people and the
  objects in the background, the clothing and the insignia, the jewelry, the text
  and the signs, the direction of the light, the shadows, the depth of field, the
  camera angle, the framing and the aspect ratio.
- Character of the photo: the real texture of the skin, the film grain where the
  film has grain, the color of the source, including black and white or sepia, and
  materials that fit the period. Do not use the smooth look of a modern phone
  photo as the default.

Do not make a person younger or thinner. Do not reshape a face, add teeth or add
eyes. Do not add makeup, do a glamour retouch, make the skin look like plastic,
add a smile, change the gaze, replace the background or invent a facial detail.

## Default settings

Use these values when the user does not give a value.

| Setting | Default |
| --- | --- |
| Fidelity mode | Conservative and strict |
| Scale | 2× in each dimension, 4× the pixel count, when the tools can do it |
| Aspect ratio and crop | Same as the source. Do not reframe |
| Denoise | Mild. Keep the real texture |
| Sharpness | Gentle. Avoid halos and false microtexture |
| Contrast and exposure | Small corrections that you can undo |
| Color | Neutral and faithful to the source. No automatic colorization |
| Face treatment | The same rules as the rest of the photo |
| Generative reconstruction | Off, unless the result truly needs it and you disclose it |
| Reference face use | Identity only |
| Output format | The container of the source: JPEG to JPEG at q95, PNG to PNG, TIFF to TIFF, HEIC to JPEG |
| Output filename | `<source-stem>_upscale.<ext>`, and `_enhance` for the detail variant |
| Overwrite | Never. A used name gets `-2` or `-3` |
| Metadata | Copy from the source, correct the changed values, add the provenance |
| Capture date | Never change it, not even to record the time of the restore |
| Film grain | Keep it or recover it from the evidence. Add it only on request and disclose it |
| Original file | Keep it. Never write to it |

Conservative is not a word for a prompt. It is the acceptance rule. If a stronger
image looks better but changes a subject, reject it and use the gentler result.

Metadata is part of fidelity. A restore that returns clean pixels and no capture
date, camera, place or caption destroyed the archive to improve the image. Read
[references/metadata-and-naming.md](references/metadata-and-naming.md).

## Ask before you restore

Some facts change the work, and only the owner has them. Ask in one message. Skip
a question that the file already answers. Do not ask many questions.

Always ask these questions:

1. What is the photo, and does the fidelity question concern the person, the print
   or the moment? The answer sets how hard you can push.
2. Does the owner want the faithful result, the detail result, or both?

When the source is film, or can be film, also ask:

3. What is the age of the photo, and does the owner know the film stock or the ISO?
4. Is the source film or digital? If it is digital, add no grain unless the owner
   asks for it.
5. Is the source a scan of a print, a scan of the negative, or a photo of a photo?
6. What must happen to the grain: keep it, recover it, reconstruct it or clean it?
7. Was the photo retouched? A studio portrait has spots removed and skin softened,
   and those areas correctly have no grain.

When the file came from a drag-and-drop operation and not from a path, first make
sure that it is the original. Read
[references/macos-photos.md](references/macos-photos.md).

## Project folders

Use a project folder for a job with face or body references, or with more than one
photo. The script `scripts/new-project.py` makes the folder. A person can also make
it by hand.

```
<project>/
  source/      the photo(s) to restore. The skill never writes here.
  refs/face/   identity limits: bone structure, hairline, marks
  refs/body/   shape and proportion limits
  output/      the results, with the metadata
  qa/          review pages, callout crops, verdicts.jsonl
  manifest.json
```

```sh
python scripts/new-project.py grandma --source target.jpg \
  --face face-ref.jpg --body body-ref.jpg
```

The face folder and the body folder are separate because the two references do
different work. A face reference limits who the person is. A body reference limits
the shape. Neither one limits the expression, the gaze, the age or the clothing.
Two folder names make this limit part of the structure.

A project is optional. For one photo with no references, give plain paths to
`finalize.py` and make no project.

## Workflow

### 1. Look at the source and record the facts

- Treat the original image as evidence. Do not write to it.
- When the photo came from a drag-and-drop operation and not from a path, treat it
  as a reference image of unknown origin. A chat program can encode it again at a
  smaller size and remove the metadata. On macOS, make sure that the file is the
  original and get the real file from Photos.app by its UUID. Read
  [references/macos-photos.md](references/macos-photos.md).
- Note the dimensions, the orientation, the grain, the focus, the compression
  artifacts, the scratches, the color cast, the clipped areas and each area of real
  uncertainty.
- Read the metadata before you change anything. The owner expects the capture date,
  the camera, the place, the caption and the keywords in the result.
- Identify all faces, expressions, body outlines, hands, distinctive objects, text,
  patterns and small features that a helpful model can invent.
- Keep the number of subjects and the exact framing. Handle the EXIF orientation.
  Most upscalers return upright pixels, so normalize the orientation tag of the
  output and do not copy the tag of the source.
- When the subject is very small or badly damaged, state that some features cannot
  come back with fidelity.

### 2. Choose the smallest change that works

Use this order, and stop as soon as the quality is sufficient:

1. Correct the light and the color: a small white balance change, the exposure, the
   highlights, the shadows, and the tone and color of the source.
2. Clean without generative work: small dust and scratch repairs, compression
   cleanup and careful denoise that keeps the texture. Mask the damaged areas. Do
   the denoise before the upscale, never after it.
3. Resize with a method that does not invent detail: high-quality resampling, for
   example Lanczos, or a super-resolution model with conservative results.
4. Finish with a light touch: modest sharpening and grain work for the output
   dimensions. Never sharpen the grain.
5. Reconstruct a face only when steps 1 to 4 cannot remove the defect. Use strong
   control of the identity and the geometry. Do not create absent information.

Do not start with a full diffusion pass or a regeneration pass. A face model that
invents eyes, smiles, teeth, hair or ages is not an acceptable default.

### 2a. Decide the grain before the upscale

Grain is the one texture that the skill can add, and it adds grain only with a
disclosure. Use the flat areas of the source as evidence and choose one row.

| Grain in the source | Action | Recorded value |
| --- | --- | --- |
| Visible and complete | Keep it. Denoise gently before the upscale | `preserved` |
| Weak but present in flat areas | Recover it from the flat areas of the source | `recovered` |
| Absent in all areas | Only when the owner asks. Match the film stock | `reconstructed` |
| Digital camera | Leave it alone | `none` |

Record `preserved` only when you looked at a flat area of the source and saw grain
there. When you did not look, or when the source has no grain, record `unknown` or
`none`. A claim of preserved grain without that look is a fidelity claim without
evidence.

Grain in a file with no grain is an invention. It invents texture, not faces. Add
grain only when the owner asks for it, only in the pattern of the film stock, and
only with a disclosure in the delivery and in the provenance sentence. Recover weak
grain when you can. That choice stays on the side of the evidence.

A faithful 2× upscale makes the grain two times larger in pixels. That result is
correct. A flat area with no texture in the output is a loss of grain, not a good
cleanup. Read [references/film-grain.md](references/film-grain.md) for the full
procedure, the character of each film stock and the failure modes.

### 3. Use reference photos only when the user supplies them

When the user supplies one or more clear images of a person in the photo:

- Find the face in the source that belongs to each reference.
- Use a reference to make sure of the stable identity traits: the shape of the
  face, the proportions of the features, the hairline and the marks. Never copy the
  smile, the gaze, the age, the light, the makeup or the viewpoint of a reference.
- Keep the expression, the age, the angle of the head, the occlusion and the light
  of the source photo. Do not paste, morph or replace the face.
- When the references disagree because of age, hair, expression or camera angle,
  keep the value of the target image.
- When you cannot establish the identity, do not force a match.

A model that keeps the identity, or a restore that the source guides, can help.
Never accept the identity score of a model as proof. A person must still look at
the defining features.

### 4. Make the first conservative pass

When image editing tools are available, give them the source image and use the
exact limits in [references/prompt-templates.md](references/prompt-templates.md).
Name the TARGET image, which is the photo to restore, and the REFERENCES, which
help with the identity.

One source photo gives one faithful output. Keep all the content. When the tool
tends to redraw the content, use the lowest strength or fall back to a
deterministic improvement. Do not call a redrawn image a faithful upscale.

When no image tool is available, give the user the exact prompt and the workflow.
Do not claim that you edited an image.

### 5. Make sure of the fidelity before you deliver

Use [references/qa-checklist.md](references/qa-checklist.md). At a minimum:

- Compare the source and the output at the same framing and the same size.
- Look at each face at the same size: the identity, the expression, the gaze, the
  eyelids, the nose, the mouth, the teeth, the jaw, the ears, the age and the
  distinctive features.
- Compare the silhouette, the posture, the hands, the proportions of the body, the
  clothing, the background objects, the text and the light.
- Look for waxy skin, synthetic pores, rings, halos, artifacts, grain that a tool
  painted over, too much sharpening and textures that the source does not support.
- Look at the grain in a flat area at 100%. Use the sky, a wall or the background
  that is out of focus. The grain must stay at the clump size of `source × scale`.
  A flat area with no texture means the grain is gone. The same small texture in
  every area means a tool replaced the grain. Noisy edges mean too much sharpening,
  not grain.
- When the output fails any limit of a high priority, reduce the processing, mask
  the area, or use the conservative baseline.
- Without a human, run `python scripts/compare.py original.jpg enhanced.png
  --out comparison.png --crop 100,80,300,320` for one aligned comparison sheet.
  The coordinates are source pixels. The crop is optional.

No single number for image similarity can replace these checks. Never use a
similarity number as the verdict.

### 6. Finalize the file and carry the metadata

The visual fidelity is not the only thing to make sure of. Run
`scripts/finalize.py SOURCE RENDER` to write an output file with the correct name.
The script copies the metadata from the source, corrects each value that the
upscale made false, and makes sure of the values against the real pixels.

```sh
python scripts/finalize.py source/IMG_1234.jpg render.png \
  --project grandma --out-dir grandma/output --suffix _upscale
```

The script works in this order. It normalizes the file and encodes it in the
container of the source. It copies all the metadata. It corrects the false values.
It adds the provenance sentence. It makes sure of the result and reports. Then it
adds an entry to the manifest.

Use this table for the report.

| Report | Meaning | Action |
| --- | --- | --- |
| `pass` | All the metadata is present and the dimensions agree | Deliver the file |
| `degraded` | A known value is missing: no exiftool, so only the raw EXIF block and the ICC profile went across and the provenance was not written, or a color profile that no longer fits the pixels. Exit 0, with the loss named | Name each field in the report. Do not claim that you kept the metadata |
| `fail` | A core tag is missing, a dimension tag disagrees, or a caption was replaced | Do not deliver the file. Do not import it into Photos. Correct the problem and run the script again |

The output keeps the capture date, the camera, the GPS fix, the rating, the
keywords and the caption of the source. It gets one provenance line that records
when and where the upscale happened. The capture date does not change. The script
puts the processing time in `XMP-xmpMM:History` and in `UserComment` so that a
photo from 1962 does not move to 2026 in a library sort.

When `exiftool` is not available and the host has no file system, do not state that
you kept the metadata. Give the user the exact commands from
[references/metadata-and-naming.md](references/metadata-and-naming.md) and say that
you did not run them.

### 6a. Show the photo to a person

A script can make sure of the metadata and the geometry. A script cannot see that
the gaze moved. After the finalize step, build the review page so that the owner
records a verdict.

```sh
python scripts/qa-page.py --project <project> \
  --crop "Face:60,40,300,300" --crop "Hands:150,250,420,390"
```

The page has a slider for each photo, a crop of each detail, one verdict for each
photo and a note for each crop. The command returns when the owner presses Done.
The verdicts are in `qa/verdicts.jsonl`. When the host has no browser or no
reachable port, add `--static` and then import the file that the owner downloads.
Read [references/qa-page.md](references/qa-page.md).

This step follows step 6 for a reason. A new project has no finalized files, and a
review page made before the finalize step has nothing to show.

### 6b. Read the review and offer the cleanup

Read `qa/verdicts.jsonl` before you deliver. The last record for a photo wins. The
notes on the crops name the defect.

- `reject` or `needs-work` means one more pass. Use the notes on the crops. Do not
  guess again what was wrong.
- `approve` is the human half of the checklist, and it passed.

Then offer the cleanup. The command
`python scripts/qa-page.py --project <project> --clean` removes the page and keeps
the verdicts. Ask before you add `--verdicts`, because that flag removes the record
of the decision.

### 7. Deliver the result and state the facts

- Return the restored image when the tools support it.
- State the scale and list the operations that you did.
- Report the metadata result: `pass`, or the exact loss of a `degraded` run.
- State the grain decision: `preserved`, `recovered`, `reconstructed` or `none`.
  When the grain is new, disclose it. Never present new grain as kept grain.
- When the photo had edits, state which file you restored. The edited render and
  the unedited master are different claims about the same file name.
- Separate a non-generative upscale from a new or restored interpretation. Do not
  promise an exact recovery of lost detail.
- When large areas are uncertain, disclose them in a short sentence.
- Keep the original. Do not make a silent change to the crop, the color or the
  content.
- For a source of low quality, you can give two variants with a label: Faithful
  (`_upscale`) and Enhanced (`_enhance`). The Enhanced variant has more detail and
  the same limits on identity and expression. Give the Faithful variant alone as
  the default.
- On macOS, you can import the result into Photos as a new item with its capture
  date. Read [references/macos-photos.md](references/macos-photos.md). Never run
  `osxphotos push-exif`, because that command writes into the original files.

## Decision rules

| Situation | Action |
| --- | --- |
| The face looks better but looks less like the source | Reject the result |
| The source is a little soft but the geometry of the face is correct | Keep the result |
| A reference has a wider smile than the source | Keep the smile of the source |
| The denoise removes real wrinkles or the weave of the fabric | Reduce the denoise |
| The upscale adds pores, teeth or hair that the source does not show | Reduce or remove the generative work |
| The damage prevents a confident recovery | Leave a restrained ambiguity and disclose it |
| The writing or the insignia is uncertain | Do not invent readable text |
| Only the face changed and the rest is faithful | Reject the result or mask the face |
| The output has clean pixels and no capture date | Treat the run as a failure |
| The delivered file looks like the output of a chat program | Get the original before you restore |
| The provenance note would replace a caption | Add the note after the caption. Never replace it |
| The flat areas came back smooth with no texture | Report the lost grain. Keep it or recover it |
| A tool added grain and the owner did not ask for it | Remove it, or disclose it as a reconstruction |
| A tool added grain and the file does not disclose it | Treat the run as a fidelity failure |
| The sharpening turned the grain into noisy edges | Reduce the sharpening, not the grain |
| A studio retouch got grain added back | Stop. Those areas have no grain by design |

## Default prompt

> Upscale this photo 2× and improve the technical quality with conservative
> settings. Keep the identity, the exact geometry of the face, the expression, the
> gaze, the apparent age, the texture of the skin, the proportions of the body, the
> pose and the clothing of each person. Keep the number of subjects, the
> composition, the crop, the background, the objects, the perspective and the
> light. Reduce the noise and the artifacts gently. Correct the tone and the color
> only where the source supports it. Sharpen without new detail. Keep the film
> grain and the natural texture of the source. Do not smooth the grain away. Do not
> invent texture. This is a high-fidelity restore. It is not a new interpretation,
> a beautification or a face replacement. When a detail is absent, keep it
> uncertain and do not invent it. Keep the output faithful to the source, even when
> some softness remains.

Read [references/prompt-templates.md](references/prompt-templates.md) for the
portrait with a reference, the archive scan and the batch variants.
