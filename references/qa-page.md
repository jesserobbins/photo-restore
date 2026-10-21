# Review page

A person has to look at the photograph before you deliver it. The agent can check
the metadata, the aspect ratio and the pixel dimensions. The agent cannot see that
the gaze changed, or that two fingers joined.

`scripts/qa-page.py` builds a page for that check. The page collects the decision
and writes it to `qa/verdicts.jsonl`. The agent reads that file on its next turn.

## What the page shows

The page shows these parts for each photo pair.

- A slider. Both images have the same scale, and you drag the divider to compare
  them. The arrow keys move the divider when the slider has the focus.
- Callout tiles. Each tile shows a named crop of the source next to the same crop
  of the restore, at the same size. This is the view that shows a changed
  expression, invented teeth or joined fingers. The restored crop is scaled by the
  upscale factor, so both crops show the same area of the scene.
- One verdict for each photo. The choices are approve, needs work and reject.
- One note for each callout, stored under the callout id.
- The verdict from the previous pass, when the file has one.

The page shows a callout crop with nearest-neighbor scaling at a whole-number
factor. A smooth scale invents the detail that you are trying to see.

## Run the page on a laptop or in the Codex browser

1. Finalize the photo first. A new project has no finished files, and the review
   page needs finished files.

2. Run the script. It serves the page on `127.0.0.1` and prints a URL.

   ```bash
   python scripts/qa-page.py --project grandma \
     --crop "Face:60,40,300,300" --crop "Hands:150,250,420,390"
   ```

3. Open the URL. Record a verdict for each photo, then press Done. The command
   returns when the review closes, and the verdicts are in
   `grandma/qa/verdicts.jsonl`.

Codex reaches a port with its own browser. Bind the server to all addresses:

```bash
python scripts/qa-page.py --project grandma --host 0.0.0.0 --port 8731
```

The script prints the localhost URL and the network URL. Open the network URL in
the Codex browser. The URL has a random token, so a person who finds the port
cannot open the page.

## Run the page without a server

Use this method when the host has no browser, when no port is reachable, or when
the sandbox blocks a listening socket.

1. Write one HTML file. The file holds every image, so it works from `file://` and
   it still works after you move it or send it by email.

   ```bash
   python scripts/qa-page.py --project grandma --static
   ```

2. Open the file. Record a verdict for each photo. Each record adds a line to the
   text area at the bottom of the page.

3. Press Download verdicts.jsonl. The browser saves the file.

4. Import the downloaded file. The script checks every line before it writes any
   line. It gives the import a new pass number and it adds the lines under the same
   lock that serve mode uses.

   ```bash
   python scripts/qa-page.py --import verdicts.jsonl --project grandma
   ```

The copy buttons use `navigator.clipboard` on `http` and `https`. They use
`document.execCommand('copy')` as the fallback. On `file://` both methods can fail.
The text area is always present and you can always select the text.

## How the page finds the photos

`--project DIR` reads `manifest.json` and pairs each source with the output files
that `finalize.py` recorded for it. The script skips a pair that the manifest marks
as a failed check. The manifest is the only record of the link between a source and
an output, so it is the only source of pairs that the script trusts.

`--pair SOURCE RENDER` reviews one pair that you name. You can repeat the flag. It
overrides the manifest. Use it for a photo that never went through a project.

The script does not pair files by name. The `output/` folder can hold
`target_upscale.jpg`, `target_enhance.jpg` and `target_upscale-2.jpg`, and no rule
can tell which source made each one.

If a manifest entry resolves to two different pairs of existing files, the script
stops and names both. Run `finalize.py` again with absolute paths, or review that
photo with `--pair`.

## Callouts

```
--crop LABEL:L,T,R,B              applies to every photo in the run
--crop PHOTO:LABEL:L,T,R,B        applies to one photo
```

The coordinates are source pixels. The script scales the crop of the restore by the
upscale factor. The id is the label in lower case, with hyphens in place of spaces.
The label `Left eye` gives the id `left-eye`. A note attaches to the id, so the id
must stay the same across passes.

A callout belongs to one photo. One set of coordinates cannot fit a portrait and a
group photo. The script refuses two labels in one photo that make the same id, and
it refuses a box that falls outside the source file.

The labelled form belongs to `qa-page.py`. `compare.py` keeps its bare `--crop`.

## The verdict file

`qa/verdicts.jsonl` holds one JSON object on each line. The script adds lines under
an exclusive lock and it flushes each line to the disk.

```json
{"ts":"2026-10-20T23:22:50-07:00","pass":1,"photo":"output/target_upscale.jpg","verdict":"needs-work","callouts":{"face":"eyes slightly soft"}}
```

- `pass` comes from the log. The script takes the highest pass number and adds one.
- The script does not change an older line. A second pass adds a line, so the file
  holds the history of the decisions and not only the latest one.
- When you read the file, the last record for a photo wins. Within one pass, the
  position in the file decides. Between passes, the pass number decides.
- A photo that is absent from a later run keeps its earlier lines. The file is a
  history, not a statement about the current set.

Read the file with `cat grandma/qa/verdicts.jsonl`, or print one line per record:

```bash
python -c "import json;[print(json.loads(l)['photo'], json.loads(l)['verdict']) for l in open('grandma/qa/verdicts.jsonl')]"
```

## Remove the generated files

```bash
python scripts/qa-page.py --project grandma --clean
```

The command removes the files that the script made. The list is in
`qa/.qa-page-files`. The command keeps `verdicts.jsonl`, because the page is easy to
make again and the verdicts are not.

To remove the verdict file as well, add `--verdicts`. Ask the user before you run
that command.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | The review closed with at least one verdict, or the script wrote the page |
| 1 | The review closed with no verdict |
| 2 | The command or the environment is wrong. The script wrote nothing |

## When something goes wrong

The server reports `cannot listen on ... address already in use`. An older review
still runs. Use a different `--port`, or stop the older process.

The page is empty or the URL returns 404. The URL needs the token. Copy the full URL
that the script printed, with the path after the port.

The Done button does nothing. The browser cannot reach the server, so the page wrote
the lines to the text area. Download the file and import it.

The review closed without a command. `--idle-timeout` closes a review after 30
minutes with no request. Pass `--idle-timeout 0` to turn the timer off. The page
sends a signal each minute, so a review that stays open does not reach the limit.

You changed the page and you want to know that it still works. The Python tests
check the markup and the verdict file. Only a browser can check the script, and that
check runs only when the host has the tools. Install them once:

```bash
mkdir -p .tools && cd .tools && npm install playwright && npx playwright install chromium
cd .. && NODE_PATH=.tools/node_modules python3 -m pytest tests/ -q
```

Without playwright the test skips, and the run prints a coverage note that says the
script was not executed. Do not read a green run as a check of the page's
JavaScript unless the note is absent.

A test with `node --check` reads the generated script on any host with node, so a
syntax error still fails without a browser.
