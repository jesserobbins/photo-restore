# Command reference

The skill has four scripts. Two of them do the mechanical work on a photograph:
`finalize.py` names the output file and carries the metadata, and `new-project.py`
makes a project folder. `qa-page.py` builds the review page. `compare.py` makes a
single comparison sheet.

None of the scripts makes the upscaled pixels, and none of them edits an image. Each
script takes the source photo and the render that the agent's own image tool made.
That is deliberate: the skill ships no model, so it works with whatever editing tool
the agent already has.

## finalize.py

```
python scripts/finalize.py SOURCE RENDER [options]
```

`SOURCE` is the original photo. The script reads it and does not change it.
`RENDER` is the file that your image model made.

The script works in a fixed order. It encodes the output, copies the metadata,
corrects the tags that the upscale made false, and then checks the result. If you
copy the metadata before the encode, you lose it. If you check the result before
the correction, you measure the wrong thing.

### Output file

The output name is `<out-dir>/<source-stem><suffix>.<ext>`. The suffix `_upscale`
is the default, and the format follows the source file. If the name is taken, the
script adds `-2` or `-3`. The script never replaces an existing file unless you pass
`--force`.

If you pass `--project`, the script adds one entry to the project `manifest.json`.
The entry includes the result of the check.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | The check passed, or the run is `degraded` and names each loss |
| 1 | The check failed. The script renamed the output `*_UNVERIFIED`. Do not deliver it |
| 2 | The command or the environment is wrong. The script wrote nothing |

A run is `degraded` when the script cannot carry something. Examples are a missing
`exiftool` and a color profile that no longer fits the pixels. The exit code is 0
because the run names the loss. Report the loss to the user.

### Options

| Flag | Default | What it does |
| --- | --- | --- |
| `--out-dir DIR` | the source folder, or `<project>/output` | sets the output folder |
| `--suffix STR` | `_upscale` | sets the file suffix. Use `_enhance` for the detail variant |
| `--format {auto,jpeg,png,tiff}` | `auto` | sets the output format. `auto` follows the source |
| `--quality N` | `95` | sets the JPEG quality |
| `--project DIR` | none | adds an entry to `DIR/manifest.json` |
| `--note STR` | generated | replaces the provenance sentence |
| `--keyword STR` | none | adds a keyword. You can repeat this flag |
| `--no-appearance-tags` | off | leaves the captions exactly as copied |
| `--no-keywords` | off | adds no keywords |
| `--grain VALUE` | `unknown` | records the grain decision in the manifest |
| `--mode VALUE` | `faithful` | records the restoration mode. `generative` adds a disclosure to the provenance sentence |
| `--input-version VALUE` | `unknown` | records which version of the photo the source is: `render`, `master` or `unknown` |
| `--native-dims WxH` | none | records the size the image model returned before any resample |
| `--resample METHOD` | none | records the method that reached the delivery size from `--native-dims` |
| `--date-source VALUE` | `auto` | records where the capture date came from. `auto` reads the source |
| `--master-name STR` | none | records the name of the unedited master |
| `--force` | off | replaces an existing output file |
| `--dry-run` | off | prints the plan and writes nothing |
| `--json` | off | prints the result as JSON |

Do not pass an empty `--suffix`. An empty suffix is how a run overwrites its own
source file. The script refuses it.

### What the script checks

The script compares the output against the source file and against its own pixels.

- Each core tag that the source had is still in the output. The core tags are
  `DateTimeOriginal`, `CreateDate`, `Make`, `Model`, `GPSLatitude` and `Rating`.
- `DateTimeOriginal` is byte for byte the same as the source.
- The EXIF orientation and the XMP orientation are both horizontal.
- The real pixel dimensions equal the dimensions that the run recorded.
- The output file decodes. Correct headers over a truncated image do not pass.
- The output format is the format that you asked for. The script reads the file
  content, not the file name.
- The provenance sentence is present, and the history entry is present.
- The generative disclosure is present when the generative mode ran.
- The date-provenance sentence is present when the date did not come from the file.
- The source caption is still in the output, and no source keyword is missing.
- No thumbnail from the source is in the output.
- The script reports a disagreement between the EXIF date and the XMP date.
- The file discloses a reconstructed grain.

### Examples

```bash
# a faithful 2x restore with the metadata carried and checked
python scripts/finalize.py IMG_1234.jpg render.png

# inside a project, with the output in the project output folder
python scripts/finalize.py grandma/source/target.jpg render.png \
  --project grandma --out-dir grandma/output

# a detail variant next to the faithful one
python scripts/finalize.py IMG_1234.jpg render.png --suffix _enhance

# grain was added on request, and the file says so
python scripts/finalize.py IMG_1234.jpg render.png --grain reconstructed

# the owner asked for stronger reconstruction, and the file says so
python scripts/finalize.py IMG_1234.jpg render.png --mode generative

# the model returned fewer pixels, and the file went to 2x anyway
python scripts/finalize.py scan.jpg model-output.png \
  --native-dims 1086x1448 --resample lanczos

# a scanned print with no capture date, filed by its library date
python scripts/finalize.py scan.jpg render.png --date-source catalog

# read the plan and write nothing
python scripts/finalize.py IMG_1234.jpg render.png --dry-run --json
```

## new-project.py

```
python scripts/new-project.py PATH [options]
```

The script makes `source/`, `refs/face/`, `refs/body/`, `output/`, `qa/`,
`manifest.json` and a README. It refuses a folder that is not empty unless you pass
`--force`.

| Flag | What it does |
| --- | --- |
| `--name STR` | sets a label for the project. This value wins over a stored label |
| `--source FILE` | copies a file into `source/`. You can repeat this flag |
| `--face FILE` | copies a file into `refs/face/`. You can repeat this flag |
| `--body FILE` | copies a file into `refs/body/`. You can repeat this flag |
| `--master FILE` | copies the unedited master into `source/` as `<stem>_master.<ext>` |
| `--force` | adds to an existing project and merges with the existing manifest |

You can run the same command twice. The second run accepts identical files. The
script refuses a different file with the same name, because `source/` holds the
evidence and a replaced photo destroys it. An XMP sidecar belongs to its image and
follows the same rule.

`--force` merges. The entries that `finalize.py` added, the creation time, the
label and the notes all stay in the manifest.

## qa-page.py

```
python scripts/qa-page.py [--project DIR | --pair SOURCE RENDER ...] [--crop SPEC ...]
```

The script builds the review page. The page has a slider for each photo pair, a crop
of each detail, one verdict for each photo and a note for each crop. The verdicts go
to `qa/verdicts.jsonl`. The script serves the page and returns when the reviewer
closes it.

| Flag | Default | What it does |
| --- | --- | --- |
| `--project DIR` | none | takes the photo pairs from `DIR/manifest.json` |
| `--pair SOURCE RENDER` | none | reviews one pair. You can repeat this flag |
| `--crop SPEC` | none | adds a crop. Use `LABEL:L,T,R,B` for every photo or `PHOTO:LABEL:L,T,R,B` |
| `--out-dir DIR` | `<project>/qa` or `./qa` | sets the folder for the page and the verdicts |
| `--static` | off | writes one HTML file and starts no server |
| `--host` | `127.0.0.1` | sets the listen address. Use `0.0.0.0` for the Codex browser |
| `--port` | a free port | sets the port |
| `--open` | off | opens a browser if one is available |
| `--idle-timeout` | `1800` | closes an inactive review after N seconds. `0` turns it off |
| `--import FILE` | none | checks and adds the verdicts that you downloaded |
| `--clean` | off | removes the files that the script made. It keeps the verdicts |
| `--verdicts` | off | with `--clean`, removes the verdict file too |
| `--json` | off | prints the result as JSON |

The exit code is 0 when the review closed with at least one verdict, or when the
script wrote the page. The code is 1 when the review closed with no verdict. The
code is 2 when the command or the environment is wrong.

`references/qa-page.md` has the steps for each environment, the callout rules and
the format of the verdict file.

## compare.py

```
python scripts/compare.py ORIGINAL RESTORED [--out FILE] [--crop L,T,R,B]
```

The script makes one image with three parts. The first part is the source at the
size of the output. The second part is the restored result. The third part is the
difference, with the contrast increased.

The sheet helps a reviewer to see a change. It does not prove that the identity
stayed the same, and it is the only script that writes an image at all: it writes a
new comparison sheet and never a deliverable. `--crop` uses the pixel coordinates of the source file.

## Grain values

`--grain` records the decision. The script does not change the texture.

| Value | Meaning |
| --- | --- |
| `preserved` | the grain of the source survived the restore |
| `recovered` | the script rebuilt weak grain from the flat areas of the source |
| `reconstructed` | the script added grain to match the film stock, and the file says so |
| `none` | the photo came from a digital camera, and the script added no grain |
| `unknown` | the user did not establish the decision. This is the default |

When the value is `reconstructed`, the script adds the disclosure to the provenance
sentence. A reconstruction therefore cannot leave the script as preservation.

## Mode values

`--mode` records which request the pass answered. Each mode has its own acceptance
rule in `references/qa-checklist.md`.

| Value | Meaning | Disclosure |
| --- | --- | --- |
| `faithful` | technical repair only, no cosmetic change. This is the default | none |
| `retouch` | the regions the owner named, changed locally | none |
| `generative` | reconstructed detail, with identity and composition unchanged | the file says the detail was reconstructed |

## Date-source values

A date in a tag and a date in a library catalog are different facts. `--date-source`
records which one the output carries. Every value except `embedded` adds a sentence to
the file.

| Value | Meaning |
| --- | --- |
| `auto` | `embedded` when the source has `DateTimeOriginal`, otherwise `unknown`. This is the default |
| `embedded` | the source file carries the capture date |
| `catalog` | the photo library supplied the date, and the source carries none |
| `owner` | a person stated the date |
| `unknown` | nobody established it |

A metadata `pass` reports that the source's tags survived. It does not say the date is
historically right.
