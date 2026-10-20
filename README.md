# photo-restore

Fidelity-first photo restoration for AI agents.

**photo-restore** upscales, restores, and cleans up photographs without inventing
people, and without losing the record that makes a photograph findable in twenty
years. It is an Agent Skill: a set of instructions plus small verification scripts
that any capable AI agent can follow.

Works with Claude Code, Cursor, Codex, pi, Windsurf, and any other host that reads
Agent Skills.

## Motivation

The state of the art in AI enabled photo restoration continues to evolve rapidly
while the goals and objectives remain the same. This skill provides simple and
repeatable photo restoration instructions for your AI platform.

## Install

```bash
npx skills add jesserobbins/photo-restore
```

Installs into the skill directory your agent reads. To install one skill from a
collection:

```bash
npx skills add <owner>/<repo> --skill photo-restore
```

Manual install: copy this directory into your agent's skills folder, keeping the
folder name identical to the `name` in `SKILL.md`.

```bash
cp -r photo-restore ~/.claude/skills/
```

For a ChatGPT Project, which has no skill directory, paste `SKILL.md` into the
project instructions and upload the reference files as project material.

## Requirements

| Tool | Needed for | Without it |
| --- | --- | --- |
| Python 3.9+ with Pillow | the helper scripts | you get the workflow as prose only |
| `exiftool` | metadata carry, correction, and verification | the run reports `degraded` and names what was lost |
| ImageMagick or `sips` | reading HEIC/HEIF, which Pillow cannot decode | HEIC input is refused rather than half-processed |
| `osxphotos` | Apple Photos: recovering the original by UUID, importing the result back | plain file-path workflow |

Nothing is required to use the skill as instructions. The scripts are the part
that makes the metadata guarantee checkable.

```bash
brew install exiftool imagemagick
python3 -m pip install Pillow
brew install osxphotos   # macOS only
```

## What it does

- **Refuses to invent people.** Identity, expression, gaze, pose, body
  proportions, clothing, and background are treated as invariants. A softer
  result that still looks like the person beats a sharp one that does not.
- **Carries the archive forward.** Capture date, camera, GPS, rating, keywords,
  caption, and ICC profile are copied from the source, corrected only where the
  upscale made them false, and verified against the real pixels.
- **Records provenance.** One sentence saying when and where the upscale
  happened, written into `Software`, `CreatorTool`, `UserComment`,
  `XMP-xmpMM:History`, and appended to the caption and keywords. The capture date
  never moves.
- **Names outputs predictably.** `<source-stem>_upscale.<ext>`, with `_enhance`
  for a higher-detail variant. Never overwrites.
- **Keeps film grain honest.** Grain is a decision with a disclosure, and the era
  is a diagnostic for spotting destroyed grain rather than a licence to invent
  it.
- **Round-trips through Apple Photos** without touching the library's originals.

## Quickstart

```bash
# 1. optional: scaffold a project with role-separated references
python scripts/new-project.py grandma --source target.jpg --face face.jpg

# 2. restore with your image model, writing the raw render somewhere temporary

# 3. finalize: name it, carry the metadata, verify
python scripts/finalize.py grandma/source/target.jpg render.png \
  --project grandma --out-dir grandma/output
```

Output: `grandma/output/target_upscale.jpg`, with the capture date, camera, GPS,
caption and keywords intact, a provenance line added, and a machine-written
`pass` or `degraded` in `grandma/manifest.json`.

If you only want the instructions and no scripts, read
[`SKILL.md`](SKILL.md). It is written to be followed by hand.

## The metadata rule

Photographs are archival objects. A restore that returns clean pixels and no
capture date improved the image and destroyed the archive.

The output carries **the render's pixels and the source's record, never the
render's claims**. In practice: the staged file is stripped of everything, then
the source's metadata is written onto it. That way an editing tool's own camera,
location, caption, or processing date cannot survive into a delivered file, and
there is no per-tag exception list to maintain.

Full detail, including the exiftool behaviours that fail silently:
[`references/metadata-and-naming.md`](references/metadata-and-naming.md).

## Film grain

Grain belongs to the negative; a print shows it enlarged. That makes grain size
predictable from stock, ISO, and enlargement, so the year is evidence about
whether grain was *destroyed* by a denoise pass. It is not a recipe for adding
grain back.

Synthesizing grain into a grainless file is permitted only when asked for,
matched to what the stock actually did, and disclosed. `--grain reconstructed`
writes that disclosure into the file, so a reconstruction cannot ship as
preservation.

Ask-before-restoring questions, stock character, and the scale check:
[`references/film-grain.md`](references/film-grain.md).

## macOS and Apple Photos

A file dragged out of Photos.app may be a re-encoded render with its metadata
stripped. The skill preflights it, recovers the real original by UUID, and
imports the result back as a new asset filed at its capture date:

```bash
osxphotos uuid                    # with the photo selected in Photos.app
osxphotos export ./source --uuid <UUID> --sidecar xmp
```

`osxphotos push-exif` is named as forbidden, because it writes metadata into the
library's original files. Details:
[`references/macos-photos.md`](references/macos-photos.md).

## Project layout

```
<project>/
  source/      the photo to restore — read-only, never written to
  refs/face/   identity constraints: bone structure, hairline, marks
  refs/body/   silhouette and proportion constraints
  output/      suffixed results, metadata intact
  qa/          comparison sheets
  manifest.json
```

Face and body references are separated because their roles are not
interchangeable. Face references constrain *who*; body references constrain
*shape*; neither constrains expression, gaze, apparent age, or clothing.

## Tests

```bash
python3 -m pytest tests/ -q
```

83 tests covering the invariants rather than the prose: the original is
byte-identical after a run, an undated source does not inherit the render's
processing date, a keyword containing a comma survives, a reconstructed grain
cannot be delivered undisclosed, and a bad invocation exits 2 without writing.

## Files

| Path | |
| --- | --- |
| `SKILL.md` | the skill: fidelity rules, workflow, decision tables |
| `references/prompt-templates.md` | prompts per case, plus grain clauses |
| `references/qa-checklist.md` | acceptance criteria, visual and metadata |
| `references/metadata-and-naming.md` | tag table, provenance, format matrix, exiftool gotchas |
| `references/film-grain.md` | grain questions, stock character, scale check |
| `references/macos-photos.md` | Photos.app round trip |
| `scripts/finalize.py` | encode, copy metadata, correct, verify, manifest |
| `scripts/new-project.py` | scaffold a project |
| `scripts/compare.py` | side-by-side QA sheet |
| [`docs/cli.md`](docs/cli.md) | full flag reference |
| [`docs/design-notes.md`](docs/design-notes.md) | why the rules are what they are |
| [`llms.txt`](llms.txt) | machine-readable summary for assistants and direct answer engines |

## Limits

- The skill does not bundle an upscaler, face model, or weights. It orchestrates
  the image model you have. The preferred backends are the image models reachable
  through Gemini and Codex, used through their image-*editing* path with the
  source passed in.
- Detail that is not in the original cannot be recovered. The skill's job is to
  avoid pretending otherwise.
- Any Pillow re-encode of a 16-bit RGB TIFF yields 8-bit RGB, so a rotated 16-bit
  RGB TIFF can lose depth without a warning. Convert such a file with a tool that
  preserves depth.
- On a host with no `exiftool`, only the raw EXIF blob and ICC profile can be
  carried. The run says `degraded` and names the fields it could not keep.

## Questions

**What does this skill actually do?**
It turns a photo restoration into a repeatable procedure: what must not change
(identity, expression, pose, composition), which corrections are acceptable and in
what order, and how to verify the result actually matches the source. It also
handles the part most restorations skip: carrying the photograph's metadata and
recording what was done.

**Does it replace my original photo?**
No. The source is treated as read-only evidence and verified byte-identical after
a run. Output is written alongside it as `<name>_upscale.<ext>`.

**Does it preserve EXIF metadata?**
Yes, and it verifies that it did. Capture date, camera, lens, GPS, rating,
keywords, caption, and ICC profile are carried, corrected only where the upscale
made them false, and checked against the real pixels. The capture date never
moves.

**What image model should I use?**
The ones reachable through Gemini and Codex have held up best. Use the model's
image-*editing* path with the source passed in, not a text-to-image prompt that
describes it. The fidelity rules and checks are what make the result a
restoration; the model executes them.

**Does it work without exiftool?**
The workflow runs, but only the raw EXIF blob and ICC profile can be carried. The
run reports `degraded` and names what was lost rather than claiming success.

**Is it free?**
MIT licensed. Install it, fork it, change it.

**Where does it come from?**
Built and maintained by [Jesse Robbins](https://jesserobbins.com).

## Author

**Jesse Robbins** writes about AI agents, infrastructure, and the work of making
software trustworthy enough to keep.

- Website: [jesserobbins.com](https://jesserobbins.com)
- GitHub: [@jesserobbins](https://github.com/jesserobbins)
- Canonical source: [github.com/jesserobbins/photo-restore](https://github.com/jesserobbins/photo-restore)

If you use this skill, the canonical version lives in that repository. Forks are
welcome; the name and provenance should follow the work.

## License

MIT. See [LICENSE](LICENSE).
