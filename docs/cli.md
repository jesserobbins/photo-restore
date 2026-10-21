# Command reference

Two scripts do the mechanical work: `finalize.py` names the output and carries the
metadata, `new-project.py` scaffolds a project. Everything else in the skill is
instructions for the agent doing the restoration.

Neither script upscales anything. They take the source photo and the render your
image model produced.

## finalize.py

```
python scripts/finalize.py SOURCE RENDER [options]
```

- `SOURCE` — the authoritative original. Read-only evidence; never modified.
- `RENDER` — the upscaled output from your image model.

Order of operations is fixed: encode, copy metadata, correct, verify. Copying
before encoding loses everything; verifying before correcting measures the wrong
thing.

### Output

`<out-dir>/<source-stem><suffix>.<ext>`, defaulting to the suffix `_upscale` and
the format of the source container. Collisions append `-2`, `-3`; nothing is
overwritten without `--force`.

With `--project`, one entry is appended to the project's `manifest.json`,
including the verification result.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Verified (`pass`), or `degraded` with the shortfall named |
| 1 | Verification failed: the output is renamed `*_UNVERIFIED`, do not deliver |
| 2 | Bad invocation or environment problem: nothing was written |

`degraded` covers any known gap — no `exiftool`, or a profile or field that could
not be carried. It exits 0 because a named shortfall is not a failure, but it is
not a success claim either: report it.

### Options

| Flag | Default | |
| --- | --- | --- |
| `--out-dir DIR` | alongside the source, or `<project>/output` | destination directory |
| `--suffix STR` | `_upscale` | use `_enhance` for the higher-detail variant. Empty is rejected: it is how a run would overwrite its own source |
| `--format {auto,jpeg,png,tiff}` | `auto` | `auto` follows the source container: JPEG at q95 with no chroma subsampling, PNG as PNG, TIFF as LZW TIFF, HEIC as JPEG |
| `--quality N` | `95` | JPEG quality |
| `--project DIR` | — | append to `DIR/manifest.json` |
| `--note STR` | generated | replace the provenance sentence |
| `--keyword STR` | — | extra keyword, repeatable |
| `--no-appearance-tags` | off | leave captions and descriptions exactly as copied |
| `--no-keywords` | off | add no keywords |
| `--grain {preserved,recovered,reconstructed,none,unknown}` | `unknown` | recorded in the manifest; `reconstructed` is disclosed in the provenance sentence automatically |
| `--master-name STR` | — | filename of the unedited master, for the manifest |
| `--force` | off | overwrite an existing output |
| `--dry-run` | off | print the plan and exit without writing |
| `--json` | off | emit the result as JSON |

### What it verifies

Against the source, and against its own pixels:

- every core tag the source had is still present (`DateTimeOriginal`,
  `CreateDate`, `Make`, `Model`, `GPSLatitude`, `Rating`)
- `DateTimeOriginal` is byte-identical to the source
- EXIF and XMP orientation are both horizontal
- real dimensions match what the run recorded, and the dimension tags agree with
  the real width
- the output decodes: headers over truncated pixel data are not enough
- the output container is what was asked for, decided by contents not filename
- the provenance note is present, and a history event was recorded
- the source caption is still a substring, and no source keyword was dropped
- no embedded thumbnail survives
- an EXIF/XMP date disagreement is reported rather than silently reconciled
- a reconstructed grain is disclosed

### Examples

```bash
# faithful 2x, metadata carried, verified
python scripts/finalize.py IMG_1234.jpg render.png

# inside a project, writing to its output directory
python scripts/finalize.py grandma/source/target.jpg render.png \
  --project grandma --out-dir grandma/output

# higher-detail variant alongside the faithful one
python scripts/finalize.py IMG_1234.jpg render.png --suffix _enhance

# grain was synthesized on request, and the file will say so
python scripts/finalize.py IMG_1234.jpg render.png --grain reconstructed

# inspect the plan without writing anything
python scripts/finalize.py IMG_1234.jpg render.png --dry-run --json
```

## new-project.py

```
python scripts/new-project.py PATH [options]
```

Creates `source/`, `refs/face/`, `refs/body/`, `output/`, `qa/`, `manifest.json`,
and a README. Refuses a non-empty directory without `--force`.

| Flag | |
| --- | --- |
| `--name STR` | human label; defaults to the directory name. An explicit value wins over a stored one |
| `--source FILE` | copy into `source/`, repeatable |
| `--face FILE` | copy into `refs/face/`, repeatable |
| `--body FILE` | copy into `refs/body/`, repeatable |
| `--master FILE` | copy the unedited master into `source/` as `<stem>_master.<ext>`, so it cannot collide with the restore target |
| `--force` | scaffold into a non-empty directory, merging into the existing manifest |

Re-running with identical arguments is idempotent. A file that differs under the
same name is refused rather than overwritten: `source/` is evidence, and silently
replacing the photograph being restored is the worst outcome available to this
script. XMP sidecars travel with their image and follow the same rule.

`--force` merges: `assets` (the finalizer's verification history), `created`, the
`name`, and any notes already in the manifest all survive.

## qa-page.py

```
python scripts/qa-page.py [--project DIR | --pair SOURCE RENDER ...] [--crop SPEC ...]
```

Builds the human review page: a slider per photo pair, callout crops of specific
details, one verdict per photo, a note per callout, and an append-only verdict log
at `qa/verdicts.jsonl`. Serves by default and returns when the review is closed.

| Flag | Default | |
| --- | --- | --- |
| `--project DIR` | — | pair photos from `DIR/manifest.json`, skipping failed verifications |
| `--pair SOURCE RENDER` | — | review one pair; repeatable, overrides the manifest |
| `--crop SPEC` | — | `LABEL:L,T,R,B` for all photos, or `PHOTO:LABEL:L,T,R,B`. Source pixels |
| `--out-dir DIR` | `<project>/qa` or `./qa` | where the page and verdicts live |
| `--static` | off | write one self-contained HTML file instead of serving |
| `--host` | `127.0.0.1` | `0.0.0.0` to reach it from Codex's browser |
| `--port` | free port | |
| `--open` | off | open a browser, best effort |
| `--idle-timeout` | `1800` | close an abandoned review; `0` disables |
| `--import FILE` | — | validate and append verdicts downloaded in static mode |
| `--clean` | off | remove generated files; keeps `verdicts.jsonl` |
| `--verdicts` | off | with `--clean`, remove the verdict log too |
| `--json` | off | emit a summary |

Exit codes: 0 closed with a verdict (or page written), 1 closed with nothing
recorded, 2 usage or environment error. Per-photo callouts, id stability, and the
per-environment recipes are in [`../references/qa-page.md`](../references/qa-page.md).

## compare.py

```
python scripts/compare.py ORIGINAL RESTORED [--out FILE] [--crop L,T,R,B]
```

Builds a three-panel sheet: source at the output's apparent size, the restored
result, and an amplified pixel difference. A review aid, not identity
verification. `--crop` uses **source** pixel coordinates.

## Grain decisions

`--grain` records what was done; the script does not alter texture itself.

| Value | Means |
| --- | --- |
| `preserved` | source grain survived the restore |
| `recovered` | attenuated grain was rebuilt from the source's own flat regions |
| `reconstructed` | grain was synthesized to match the stock, and the file says so |
| `none` | digital capture; no grain was added |
| `unknown` | not established — the default, and honest about it |

`reconstructed` appends the disclosure to the provenance sentence by
construction, so a reconstruction cannot be delivered as preservation.
