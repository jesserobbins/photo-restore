# Review page

The review step has a human in it. The agent can check metadata, aspect ratios and
pixel dimensions; it cannot tell you that the gaze drifted or that the fingers
merged. This page is where that judgement happens, and where it is recorded so the
agent can act on it.

`scripts/qa-page.py` builds the page, collects verdicts, and appends them to
`qa/verdicts.jsonl`.

## What you see

Per photo pair:

- **A left-to-right slider.** Both images at identical scale, a draggable divider,
  and a range input that responds to arrow keys when focused.
- **Callout tiles below.** Each one shows a named crop of the source beside the
  same crop of the restored version, at equal apparent size. This is the view that
  catches a changed expression, invented teeth, or merged fingers. The restored
  crop is scaled by the upscale factor, so the two are the same piece of the world.
- **A verdict per photo:** approve, needs work, or reject.
- **A note per callout**, keyed to its id.
- **The previous pass's verdict**, when there is one, so a second review starts
  informed.

Callout crops are shown with nearest-neighbour scaling at an integer factor.
Smoothing a crop would invent the detail you are trying to inspect.

## Running it

### On a laptop, or in Codex's browser

```bash
python scripts/qa-page.py --project grandma \
  --crop "Face:60,40,300,300" --crop "Hands:150,250,420,390"
```

That serves on `127.0.0.1` and prints a URL. Open it, review, press **Done**. The
command returns when the review closes, so the next thing the agent does can read
`grandma/qa/verdicts.jsonl`.

For Codex, which reaches a port through its own browser, bind to all interfaces:

```bash
python scripts/qa-page.py --project grandma --host 0.0.0.0 --port 8731
```

The script prints both the localhost URL and the network URL. Open the network one
in Codex's browser. The URL carries a random token, so the page is not reachable
by anyone who merely finds the port.

### No server, no display, or a sandbox with no reachable port

```bash
python scripts/qa-page.py --project grandma --static
```

Writes one self-contained HTML file into `qa/`. Every image is embedded, so it
works from `file://`, survives being moved or emailed, and needs no network for
fonts or assets. Record copies each verdict into a textarea at the bottom; **Download
verdicts.jsonl** saves it. Then:

```bash
python scripts/qa-page.py --import verdicts.jsonl --project grandma
```

`--import` validates every line before writing any of them, re-stamps the pass, and
appends under the same lock as serve mode. Hand-editing the log is never required.

The clipboard buttons try `navigator.clipboard` on `http(s)` and fall back to
`document.execCommand('copy')`. On `file://` neither may work; the textarea is
always there and always selectable, which is the point.

## Which photos it reviews

`--project DIR` reads `manifest.json` and pairs each source with the outputs
`finalize.py` recorded for it, skipping anything recorded as a failed
verification. That file is the only place the source-to-output relation is
written down, so it is the only pairing this script trusts.

`--pair SOURCE RENDER` reviews one pair you name, repeatable, and overrides the
manifest. Use it for a photo that was never finalized into a project.

Pairing by filename is refused. `output/` can hold `target_upscale.jpg`,
`target_enhance.jpg` and `target_upscale-2.jpg`, and there is no safe way to guess
which source each came from.

## Callouts

```
--crop LABEL:L,T,R,B              applies to every photo in the run
--crop PHOTO:LABEL:L,T,R,B        applies to one photo
```

Coordinates are **source** pixels. The restored crop is scaled by the upscale
factor. The id is the slug of the label (`Left eye` → `left-eye`), and it is what
a note is attached to, so it must stay stable across passes.

Callouts are per-photo by nature: one coordinate set across a portrait and a group
photo would be wrong for both. Two labels in one photo that slug to the same id are
refused rather than guessed. A box that falls outside the source is refused too.

## The verdict log

`qa/verdicts.jsonl`, one JSON object per line, appended under an exclusive lock and
fsynced:

```json
{"ts":"2026-10-20T23:22:50-07:00","pass":1,"photo":"target","verdict":"needs-work","callouts":{"face":"eyes slightly soft","hands":"fingers merged"}}
```

- `pass` comes from the log: the highest existing pass plus one.
- Earlier lines are never rewritten, so pass 2 is a new line and the file is the
  history of judgement rather than its latest state.
- Reading: last record wins per photo, ordered by `ts`.
- A photo that disappears from a later run keeps its earlier lines. The log is
  history, not a claim about the current set.

Reading it back:

```bash
cat grandma/qa/verdicts.jsonl
python -c "import json,sys;[print(json.loads(l)['photo'], json.loads(l)['verdict']) for l in open('grandma/qa/verdicts.jsonl')]"
```

## After the review

```bash
python scripts/qa-page.py --project grandma --clean
```

Removes the files the script generated, listed in `qa/.qa-page-files`. It **keeps**
`verdicts.jsonl`, because the page is regenerable and the verdicts are not. Removing
them takes `--clean --verdicts`, and the agent should ask before doing that.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | The review closed with at least one verdict recorded, or the page was written |
| 1 | The review closed with nothing recorded |
| 2 | Usage or environment problem — nothing was written |

## Troubleshooting

**"cannot listen on … address already in use."** A previous review is still
running. Use a different `--port`, or stop the old process.

**The page is blank or the URL 404s.** The token in the URL is required. Copy the
whole URL the script printed, including the path segment after the port.

**Nothing happens when I press Done.** The browser could not reach the server, so
the page fell back to logging. The lines are in the textarea; download and
`--import` them.

**I changed the page and want to check it still runs.** The Python tests check
markup and the verdict log; only a browser can check the script. With node and
playwright available:

```sh
NODE_PATH=/path/to/node_modules python3 -m pytest tests/ -q -k browser
```

Without playwright that test skips, and the markup tests still enforce that each
slider owns its range input.

**The review closed on its own.** `--idle-timeout` defaults to 30 minutes of no
requests. Pass `--idle-timeout 0` to disable it.
