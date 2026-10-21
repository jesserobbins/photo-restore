# photo-restore

This skill provides powerful AI photo restoration, enhancement and upscaling with
ChatGPT, Codex, Claude Code, Gemini and other compatible AI agents. It needs no
repetitive prompting, no ComfyUI workflow, no custom pipeline and no dedicated GPU
server.

Restore old photographs, upscale low-resolution images, enhance scanned prints,
reduce noise, correct blur, preserve film grain and restore faces with reference
photos. The workflow is repeatable and conservative. It produces a high-quality
result and keeps the identity, the facial features, the expression, the gaze, the
pose, the body proportions, the clothing, the composition and the historical
authenticity of each subject.

Start with a single photo. Use the optional features for more demanding work.

- **Reference photographs.** Supply more face or body photos to guide an
  identity-accurate restore. The skill keeps the expression, the pose and the
  appearance of the source.
- **Organized projects.** Use a fixed set of folders for the source images, the
  reference photos, the restored files and the comparisons.
- **Metadata preservation.** Carry the EXIF, IPTC and XMP metadata from the source,
  including the capture date, the camera, the GPS coordinates, the caption and the
  keywords.
- **Automated file management.** Make each file name from its source file, keep the
  originals, and record the provenance of the restore.
- **Film grain management.** Keep the real photographic texture and use the film
  characteristics of the period to set the grain treatment.
- **Quality verification.** Compare the restored file against the source and the
  references to find an unwanted change or an invented detail.
- **Apple Photos integration.** Retrieve the original, keep the metadata, and import
  the restored version without a change to the original.

Use the skill directly for a simple restore. Use the project structure, the
reference images and the verification tools for harder work.

**Prioritize faithful recovery over reconstruction, beautification or invented
detail.**

An Agent Skill is a set of instructions that an AI agent reads and follows. This
folder is one such skill, and it also holds scripts that make the metadata work
checkable.

## Motivation

## Motivation

> The state of the art in AI enabled photo restoration continues to evolve rapidly
> while the goals and objectives remain the same. This skill provides simple and
> repeatable photo restoration instructions for your AI platform.

## Install

You need an agent that reads Agent Skills. Claude Code, Cursor, Codex, pi and
Windsurf all read them.

1. Run the install command. It copies the skill into the skill folder of your agent.

   ```bash
   npx skills add jesserobbins/photo-restore
   ```

2. If the repository holds more than one skill, name the skill to install.

   ```bash
   npx skills add <owner>/<repo> --skill photo-restore
   ```

3. If you cannot use the command, copy the folder by hand. The folder name must
   equal the `name` field in `SKILL.md`.

   ```bash
   cp -r photo-restore ~/.claude/skills/
   ```

A ChatGPT Project has no skill folder. Paste `SKILL.md` into the project
instructions and add the reference files as project material.

## Requirements

| Tool | What it does | If it is missing |
| --- | --- | --- |
| Python 3.9 or later, with Pillow | runs the helper scripts | you get the workflow as text only |
| `exiftool` | copies and checks the metadata | the run reports `degraded` and names the loss |
| ImageMagick or `sips` | opens HEIC and HEIF files | the run refuses HEIC input |
| `osxphotos` | reads and writes the Apple Photos library | you use file paths instead |

You do not need any of these tools to read the skill as instructions. The scripts
make the metadata guarantee checkable.

```bash
brew install exiftool imagemagick
python3 -m pip install Pillow
brew install osxphotos   # macOS only
```

## What the skill does

- It keeps the person in the photograph unchanged. Identity, expression, gaze,
  pose, body proportions, clothing and background are constraints. A soft result
  that still looks like the person wins over a sharp result that does not.
- It keeps the record that the camera wrote. Capture date, camera, GPS, rating,
  keywords, caption and color profile go into the output file.
- It writes down what it did. One sentence names the time and the tool that did
  the upscale. The sentence goes into the file, and the capture date does not move.
- It names the output file after the source file, and it never overwrites.
- It builds a review page for a human. The page has a slider, callout crops, and
  one verdict per photo.
- It treats film grain as a decision. The year tells you if grain was lost, and
  the year is not a reason to invent grain.
- It moves a result into Apple Photos as a new item, and it does not change the
  items that are already there.

## Quickstart

The three commands below restore one photograph.

1. Make a project folder. The folder holds the source, the reference photos and
   the output.

   ```bash
   python scripts/new-project.py grandma --source target.jpg --face face.jpg
   ```

2. Restore the photograph with your image model. Write the result to a temporary
   file.

3. Finalize the result. This step names the file, carries the metadata and checks
   the result.

   ```bash
   python scripts/finalize.py grandma/source/target.jpg render.png \
     --project grandma --out-dir grandma/output
   ```

The output is `grandma/output/target_upscale.jpg`. The capture date, the camera,
the GPS fix, the caption and the keywords are in the output. The file also has a
provenance sentence. `grandma/manifest.json` records `pass` or `degraded` for that
photo.

If you want only the instructions and no scripts, read `SKILL.md`. You can follow
it by hand.

## How the metadata works

A photograph is an archive item. A restore that returns clean pixels and no
capture date improved the image and destroyed the archive.

The output file holds the pixels from the render and the record from the source.
It holds nothing that the render claims. In practice the script strips the staged
file and then writes the source metadata onto it. An editing tool can put its own
camera, location, caption or processing date in its output. None of it survives.

`references/metadata-and-naming.md` has the full list of tags and the exiftool
behaviors that fail without a warning.

## Film grain

Grain is in the negative. A print shows the same grain, made larger by the print.
You can therefore predict the grain size from the film stock, the ISO and the
print size.

That prediction tells you if a denoise step removed the grain. It does not tell you
to add grain. The script adds grain only when you ask for it, only in the pattern
of that stock, and it writes a note in the file that says so.

`references/film-grain.md` has the questions to ask and the check to make.

## Apple Photos on macOS

A file that you drag out of Photos can be a smaller copy with no metadata. The
skill checks that file first. If the check fails, the skill takes the original
from Photos by its UUID.

```bash
osxphotos uuid                    # select the photo in Photos first
osxphotos export ./source --uuid <UUID> --sidecar xmp
```

The skill then imports the result as a new item, with the capture date. Do not run
`osxphotos push-exif`. That command writes into the original files in the library.
`references/macos-photos.md` has the detail.

## Project layout

```
<project>/
  source/      the photo to restore. The skill never writes here.
  refs/face/   reference photos of the face
  refs/body/   reference photos of the body
  output/      the finished files, with metadata
  qa/          review pages and verdicts.jsonl
  manifest.json
```

The face and body folders are separate because the two kinds of reference do
different work. A face reference limits who the person is. A body reference limits
the shape. Neither one limits expression, age or clothing.

## Review page

After finalize, the skill can build a page for a human reviewer.

```bash
python scripts/qa-page.py --project grandma \
  --crop "Face:60,40,300,300" --crop "Hands:150,250,420,390"
```

The page has a slider for each photo and a crop of each detail. The reviewer
records a verdict for each photo and can write a note on each crop. The reviews go
to `qa/verdicts.jsonl`, and the file keeps the older passes.

## Tests

```bash
python3 -m pytest tests/ -q
```

The tests check the rules, not the text. They confirm that the source file does not
change, that an undated source does not get the date of the render, and that a
keyword with a comma survives.

## Common questions

Can I keep the original file? Yes. The script reads the source file and writes a
new file with the suffix `_upscale`. It checks the source file before and after, and
the two files must match.

Does the output keep the EXIF data? Yes. The capture date, the camera, the GPS fix,
the rating, the keywords and the caption go into the output, and the script reads
the output back to confirm it. The capture date stays the same in every case.

Which image model does the skill use? Use the image models in Gemini or in Codex. Give
the model the source image and ask it to edit that image. A model that redraws the
photo from a description makes a new photograph, and a new photograph is not a
restore.

What happens without exiftool? The workflow runs, but the script can carry only the
raw EXIF block and the color profile. The run then reports `degraded` and names each
field that it cannot carry.

## Limits

- The skill does not include an upscaler or a face model. It uses the image model
  that you already have.
- The skill cannot recover detail that is not in the original. Its job is to avoid
  the appearance of recovery.
- A Pillow encode of a 16-bit RGB TIFF writes 8 bits. A rotated 16-bit RGB TIFF can
  therefore lose depth without a warning.
- Without `exiftool`, the script carries only the raw EXIF block and the color
  profile.

## About this project

Jesse Robbins writes about AI agents, infrastructure, and software that people
keep. The website is [jesserobbins.com](https://jesserobbins.com), and the GitHub
profile is [@jesserobbins](https://github.com/jesserobbins).

The canonical copy of this skill is
[github.com/jesserobbins/photo-restore](https://github.com/jesserobbins/photo-restore).
You can fork it. If you publish a fork, keep the name and the provenance.

The license is MIT. See [LICENSE](LICENSE).
