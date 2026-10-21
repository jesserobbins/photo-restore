"""Tests for qa-page.py.

The invariants that matter: a callout id is stable so notes keep pointing at the
same detail, the verdict log is append-only so a second pass does not erase the
first, and cleanup never removes verdicts without being asked.

Run: python -m pytest tests/ -q
"""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "qa-page.py"
spec = importlib.util.spec_from_file_location("qa_page", SCRIPT)
qa_page = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa_page)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_pair(tmp_path, size=(80, 60), scale=2, name="src"):
    src = tmp_path / f"{name}.jpg"
    Image.new("RGB", size, (110, 95, 80)).save(src, quality=95)
    out = tmp_path / f"{name}_upscale.jpg"
    Image.new("RGB", (size[0] * scale, size[1] * scale), (110, 95, 80)).save(out, quality=95)
    return src, out


def run_cli(*args, timeout=60):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, timeout=timeout)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("label,expected", [
    ("Left eye", "left-eye"),
    ("Hands / fingers", "hands-fingers"),
    ("Collar & tie", "collar-tie"),
    ("  Spaced   out  ", "spaced-out"),
])
def test_slug_is_stable_and_readable(label, expected):
    assert qa_page.slug(label) == expected


def test_parse_crop_bare_form_applies_to_all():
    crop = qa_page.parse_crop("Left eye:10,20,110,120")
    assert crop["photo"] is None
    assert crop["id"] == "left-eye"
    assert crop["box"] == (10, 20, 110, 120)


def test_parse_crop_with_photo():
    crop = qa_page.parse_crop("IMG_1234:Left eye:10,20,110,120")
    assert crop["photo"] == "IMG_1234"
    assert crop["id"] == "left-eye"


@pytest.mark.parametrize("spec", ["nobox", "label:1,2,3", "label:a,b,c,d", ":1,2,3,4"])
def test_parse_crop_rejects_bad_specs(spec):
    with pytest.raises(SystemExit) as exc:
        qa_page.parse_crop(spec)
    assert exc.value.code == 2


def test_callouts_expand_bare_form_to_every_photo():
    crops = [qa_page.parse_crop("Eyes:0,0,10,10")]
    pairs = [{"photo": "a", "source_stem": "a"}, {"photo": "b", "source_stem": "b"}]
    by_photo = qa_page.callouts_for(crops, pairs)
    assert set(by_photo) == {"a", "b"}
    assert by_photo["a"]["eyes"]["box"] == (0, 0, 10, 10)


def test_duplicate_slug_with_different_boxes_is_refused():
    crops = [qa_page.parse_crop("a:Left eye:0,0,10,10"),
             qa_page.parse_crop("a:left-eye:20,20,40,40")]
    with pytest.raises(SystemExit) as exc:
        qa_page.callouts_for(crops, [{"photo": "a", "source_stem": "a"}])
    assert exc.value.code == 2


def test_same_slug_and_same_box_is_allowed():
    crops = [qa_page.parse_crop("a:Left eye:0,0,10,10"),
             qa_page.parse_crop("a:left-eye:0,0,10,10")]
    pairs = [{"photo": "a", "source_stem": "a"}]
    assert len(qa_page.callouts_for(crops, pairs)["a"]) == 1


def test_crop_naming_an_unknown_photo_is_refused():
    crops = [qa_page.parse_crop("ghost:Eyes:0,0,10,10")]
    with pytest.raises(SystemExit) as exc:
        qa_page.callouts_for(crops, [{"photo": "a", "source_stem": "a"}])
    assert exc.value.code == 2


# --------------------------------------------------------------------------- #
# verdict log
# --------------------------------------------------------------------------- #

def test_append_never_rewrites_earlier_lines(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    qa_page.append_record(path, {"photo": "a", "verdict": "approve", "pass": 1,
                                 "ts": "2026-01-01T00:00:00"})
    first = path.read_text()
    qa_page.append_record(path, {"photo": "a", "verdict": "reject", "pass": 2,
                                 "ts": "2026-01-02T00:00:00"})
    after = path.read_text()
    assert after.startswith(first), "the first pass must be preserved verbatim"
    assert len(after.splitlines()) == 2


def test_latest_by_photo_uses_the_most_recent_record(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    qa_page.append_record(path, {"photo": "a", "verdict": "reject", "pass": 1,
                                 "ts": "2026-01-01T00:00:00"})
    qa_page.append_record(path, {"photo": "a", "verdict": "approve", "pass": 2,
                                 "ts": "2026-01-02T00:00:00"})
    latest = qa_page.latest_by_photo(qa_page.read_verdicts(path))
    assert latest["a"]["verdict"] == "approve"


def test_next_pass_counts_from_the_log(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    assert qa_page.next_pass(qa_page.read_verdicts(path)) == 1
    qa_page.append_record(path, {"photo": "a", "verdict": "approve", "pass": 3})
    assert qa_page.next_pass(qa_page.read_verdicts(path)) == 4


def test_malformed_line_is_skipped_with_a_warning(tmp_path, capsys):
    path = tmp_path / "verdicts.jsonl"
    path.write_text('{"photo":"a","verdict":"approve"}\nnot json\n')
    records = qa_page.read_verdicts(path)
    assert len(records) == 1
    assert "not valid JSON" in capsys.readouterr().err


@pytest.mark.parametrize("record,ok", [
    ({"photo": "a", "verdict": "approve"}, True),
    ({"photo": "a", "verdict": "approved"}, False),
    ({"verdict": "approve"}, False),
    ({"photo": "a", "verdict": "reject", "callouts": {"x": 3}}, False),
    ({"photo": "a", "verdict": "reject", "callouts": {"x": "fine"}}, True),
])
def test_validate_record(record, ok):
    assert (qa_page.validate_record(record) is None) is ok


def test_stamp_drops_empty_notes():
    record = qa_page.stamp("a", "approve", {"eyes": "  ", "hands": "merged"}, 2)
    assert record["callouts"] == {"hands": "merged"}
    assert "ts" in record and record["pass"] == 2


# --------------------------------------------------------------------------- #
# pairing
# --------------------------------------------------------------------------- #

def test_manifest_pairing_uses_recorded_source_and_output(tmp_path):
    project = tmp_path / "proj"
    (project / "output").mkdir(parents=True)
    src, out = make_pair(project, name="target")
    out = project / "output" / "target_upscale.jpg"
    out.parent.mkdir(exist_ok=True)
    make_pair(project, name="target")[0].rename(project / "target.jpg")
    Image.new("RGB", (160, 120)).save(out)
    (project / "manifest.json").write_text(json.dumps({
        "assets": [{"source": str(project / "target.jpg"), "output": str(out),
                    "verification": "pass"}]
    }))
    pairs = qa_page.pairs_from_manifest(project)
    assert len(pairs) == 1
    # The verdict key is the output stem, which is unique per variant; the source
    # stem stays available for naming callouts.
    assert pairs[0]["photo"] == "target_upscale.jpg"
    assert pairs[0]["source_stem"] == "target"


def test_manifest_pairing_skips_failed_verifications(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    src, out = make_pair(project)
    (project / "manifest.json").write_text(json.dumps({
        "assets": [{"source": str(src), "output": str(out), "verification": "fail"}]
    }))
    with pytest.raises(SystemExit) as exc:
        qa_page.pairs_from_manifest(project)
    assert exc.value.code == 2


def test_manifest_pairing_ignores_missing_files(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "manifest.json").write_text(json.dumps({
        "assets": [{"source": str(project / "gone.jpg"),
                    "output": str(project / "gone_up.jpg"), "verification": "pass"}]
    }))
    with pytest.raises(SystemExit):
        qa_page.pairs_from_manifest(project)


def test_no_inputs_is_a_usage_error(tmp_path):
    r = run_cli("--out-dir", tmp_path)
    assert r.returncode == 2
    assert "nothing to review" in r.stderr


def test_aspect_mismatch_is_refused(tmp_path):
    src = tmp_path / "s.jpg"
    Image.new("RGB", (80, 60)).save(src)
    out = tmp_path / "o.jpg"
    Image.new("RGB", (160, 100)).save(out)   # 1.6 vs 1.33
    r = run_cli("--pair", src, out, "--static", "--out-dir", tmp_path / "qa")
    assert r.returncode == 2
    assert "aspect" in r.stderr.lower()


def test_callout_outside_the_image_is_refused(tmp_path):
    src, out = make_pair(tmp_path)
    r = run_cli("--pair", src, out, "--crop", "Far:900,900,1000,1000",
                "--static", "--out-dir", tmp_path / "qa")
    assert r.returncode == 2
    assert "outside" in r.stderr


# --------------------------------------------------------------------------- #
# static mode
# --------------------------------------------------------------------------- #

@pytest.mark.needs_pillow
def test_static_page_is_self_contained(tmp_path):
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    r = run_cli("--pair", src, out, "--crop", "Eyes:0,0,40,30",
                "--static", "--out-dir", qa_dir, "--json")
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    page = Path(summary["page"])
    html = page.read_text()

    assert "data:image/png;base64" in html
    assert "http://" not in html.split("<script>")[0].replace("http://www.w3.org", ""), \
        "the page must not reference anything over the network"
    assert "src=\"/" not in html, "no relative asset references"
    assert summary["callouts"] == 1
    # Two files: the page and the bookkeeping list. Verdicts appear only when used.
    assert sorted(p.name for p in qa_dir.iterdir()) == [".qa-page-files", page.name]


@pytest.mark.needs_pillow
def test_static_page_survives_being_moved(tmp_path):
    """Everything is embedded, so a moved file still renders."""
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    run_cli("--pair", src, out, "--static", "--out-dir", qa_dir)
    page = next(qa_dir.glob("review-pass*.html"))
    moved = tmp_path / "elsewhere" / "page.html"
    moved.parent.mkdir()
    shutil.move(page, moved)
    html = moved.read_text()
    assert "data:image/png;base64" in html


# --------------------------------------------------------------------------- #
# import and clean
# --------------------------------------------------------------------------- #

def test_import_validates_then_appends(tmp_path):
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    download = tmp_path / "download.jsonl"
    download.write_text(
        json.dumps({"photo": "src", "verdict": "approve",
                    "ts": "2026-01-01T00:00:00"}) + "\n")
    r = run_cli("--import", download, "--out-dir", qa_dir)
    assert r.returncode == 0, r.stderr
    records = qa_page.read_verdicts(qa_dir / "verdicts.jsonl")
    assert len(records) == 1
    assert records[0]["verdict"] == "approve"
    assert records[0]["pass"] == 1


def test_import_rejects_a_bad_line_and_writes_nothing(tmp_path):
    qa_dir = tmp_path / "qa"
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"photo":"a","verdict":"approve"}\n{"photo":"b","verdict":"nope"}\n')
    r = run_cli("--import", bad, "--out-dir", qa_dir)
    assert r.returncode == 2
    assert "verdict must be one of" in r.stderr
    # Nothing is written, so a partly-bad file cannot half-import.
    assert not (qa_dir / "verdicts.jsonl").exists()


def test_import_stamps_a_new_pass(tmp_path):
    qa_dir = tmp_path / "qa"
    first = tmp_path / "one.jsonl"
    first.write_text('{"photo":"a","verdict":"reject"}\n')
    assert run_cli("--import", first, "--out-dir", qa_dir).returncode == 0
    second = tmp_path / "two.jsonl"
    second.write_text('{"photo":"a","verdict":"approve"}\n')
    assert run_cli("--import", second, "--out-dir", qa_dir).returncode == 0
    records = qa_page.read_verdicts(qa_dir / "verdicts.jsonl")
    assert [r["pass"] for r in records] == [1, 2]


def test_clean_removes_the_page_and_keeps_verdicts(tmp_path):
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    run_cli("--pair", src, out, "--static", "--out-dir", qa_dir)
    qa_page.append_record(qa_dir / "verdicts.jsonl",
                          {"photo": "src", "verdict": "approve", "pass": 1})

    r = run_cli("--clean", "--out-dir", qa_dir)
    assert r.returncode == 0
    assert not list(qa_dir.glob("review-pass*.html"))
    assert (qa_dir / "verdicts.jsonl").exists(), "verdicts are not regenerable"
    assert "kept" in r.stdout


def test_clean_with_verdicts_removes_them_when_asked(tmp_path):
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    qa_page.append_record(qa_dir / "verdicts.jsonl",
                          {"photo": "src", "verdict": "approve", "pass": 1})
    r = run_cli("--clean", "--verdicts", "--out-dir", qa_dir)
    assert r.returncode == 0
    assert not (qa_dir / "verdicts.jsonl").exists()


# --------------------------------------------------------------------------- #
# serve mode
# --------------------------------------------------------------------------- #

@pytest.mark.needs_pillow
def test_serve_end_to_end(tmp_path):
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--pair", str(src), str(out),
         "--crop", "Eyes:0,0,40,30", "--port", str(port),
         "--out-dir", str(qa_dir), "--idle-timeout", "30"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        token = None
        deadline = time.time() + 15
        while time.time() < deadline:
            line = proc.stdout.readline()
            if "review page:" in line:
                token = line.strip().rstrip("/").split("/")[-1]
                break
        assert token, "the script must print the tokenised URL"

        base = f"http://127.0.0.1:{port}"

        def get(path):
            try:
                with urllib.request.urlopen(f"{base}{path}", timeout=5) as r:
                    return r.status
            except urllib.error.HTTPError as exc:
                return exc.code

        def post(path, payload):
            req = urllib.request.Request(
                f"{base}{path}", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status
            except urllib.error.HTTPError as exc:
                return exc.code

        assert get(f"/{token}/") == 200
        assert get("/") == 404, "an un-tokenised path must not serve the page"
        assert get(f"/wrong/") == 404

        assert post(f"/{token}/verdicts",
                    {"photo": "src", "verdict": "needs-work",
                     "callouts": {"eyes": "gaze drifted"}}) == 200
        assert post(f"/{token}/verdicts", {"photo": "src", "verdict": "maybe"}) == 400

        assert post(f"/{token}/done", {}) == 200
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()

    records = qa_page.read_verdicts(qa_dir / "verdicts.jsonl")
    assert len(records) == 1
    assert records[0]["verdict"] == "needs-work"
    assert records[0]["callouts"] == {"eyes": "gaze drifted"}
    assert proc.returncode == 0


@pytest.mark.needs_pillow
def test_serve_exits_1_when_nothing_was_recorded(tmp_path):
    src, out = make_pair(tmp_path)
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--pair", str(src), str(out),
         "--port", str(port), "--out-dir", str(tmp_path / "qa"),
         "--idle-timeout", "1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    out_text, _ = proc.communicate(timeout=30)
    assert proc.returncode == 1, out_text
    assert "no verdicts recorded" in out_text


# --------------------------------------------------------------------------- #
# regressions found in review
# --------------------------------------------------------------------------- #

@pytest.mark.needs_pillow
def test_every_slider_contains_its_range_input(tmp_path):
    """The range input must be inside .slider; as a sibling the page's JS throws."""
    src, out = make_pair(tmp_path)
    r = run_cli("--pair", src, out, "--static", "--out-dir", tmp_path / "qa", "--json")
    html = Path(json.loads(r.stdout)["page"]).read_text()
    assert 'class="slider"' in html
    for chunk in html.split('class="slider"')[1:]:
        block = chunk.split('class="callouts"')[0]
        assert "input type=\"range\"" in block, "range input left outside the slider"


@pytest.mark.needs_pillow
def test_hostile_filename_cannot_inject_markup(tmp_path):
    """A filename is data. It must never become an element in a page full of photos."""
    evil = tmp_path / "<img src=x onerror=alert(1)>.jpg"
    Image.new("RGB", (40, 30)).save(evil)
    out = tmp_path / "out.jpg"
    Image.new("RGB", (80, 60)).save(out)
    r = run_cli("--pair", evil, out, "--crop", '<script>x</script>:0,0,10,10',
                "--static", "--out-dir", tmp_path / "qa", "--json")
    assert r.returncode == 0, r.stderr
    html = Path(json.loads(r.stdout)["page"]).read_text()
    # Escaped text still contains the words; what must not exist is an element.
    assert "<img src=x" not in html, "the filename became an element"
    assert "<script>x</script>" not in html, "the label became an element"
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


@pytest.mark.needs_pillow
def test_two_outputs_of_one_source_get_distinct_verdict_keys(tmp_path):
    src = tmp_path / "target.jpg"
    Image.new("RGB", (40, 30)).save(src)
    out_a = tmp_path / "target_upscale.jpg"
    out_b = tmp_path / "target_enhance.jpg"
    for path in (out_a, out_b):
        Image.new("RGB", (80, 60)).save(path)
    qa_dir = tmp_path / "qa"
    r = run_cli("--pair", src, out_a, "--pair", src, out_b,
                "--static", "--out-dir", qa_dir, "--json")
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert summary["pairs"] == 2
    html = Path(summary["page"]).read_text()
    assert 'data-photo="target_upscale.jpg"' in html
    assert 'data-photo="target_enhance.jpg"' in html
    # Distinct radio groups, so one choice cannot satisfy both cards.
    assert html.count('name="v0"') == 3
    assert html.count('name="v1"') == 3


def test_manifest_relative_paths_resolve_against_the_project(tmp_path):
    project = tmp_path / "proj"
    (project / "source").mkdir(parents=True)
    (project / "output").mkdir()
    Image.new("RGB", (40, 30)).save(project / "source" / "t.jpg")
    Image.new("RGB", (80, 60)).save(project / "output" / "t_upscale.jpg")
    (project / "manifest.json").write_text(json.dumps({"assets": [{
        "source": "source/t.jpg", "output": "output/t_upscale.jpg",
        "verification": "pass"}]}))
    pairs = qa_page.pairs_from_manifest(project)
    assert len(pairs) == 1
    assert pairs[0]["photo"] == "t_upscale.jpg"


@pytest.mark.parametrize("record,ok", [
    ({"photo": ["a"], "verdict": "approve"}, False),
    ({"photo": "", "verdict": "approve"}, False),
    ({"photo": "a", "verdict": "approve", "ts": 12345}, False),
    ({"photo": "a", "verdict": "approve", "pass": "1"}, False),
])
def test_validate_record_rejects_wrong_types(record, ok):
    assert (qa_page.validate_record(record) is None) is ok


def test_newer_pass_wins_even_without_a_timestamp():
    records = [
        {"photo": "a", "verdict": "approve", "pass": 1, "ts": "2026-01-02T00:00:00"},
        {"photo": "a", "verdict": "reject", "pass": 2},
    ]
    assert qa_page.latest_by_photo(records)["a"]["verdict"] == "reject"


@pytest.mark.needs_pillow
def test_clean_removes_every_generated_page(tmp_path):
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    run_cli("--pair", src, out, "--static", "--out-dir", qa_dir, "--json")
    qa_page.append_record(qa_dir / "verdicts.jsonl",
                          {"photo": out.stem, "verdict": "needs-work", "pass": 1})
    run_cli("--pair", src, out, "--static", "--out-dir", qa_dir, "--json")
    assert len(list(qa_dir.glob("review-pass*.html"))) == 2, "a second pass has its own page"
    run_cli("--clean", "--out-dir", qa_dir)
    assert not list(qa_dir.glob("review-pass*.html")), "an earlier page was orphaned"


def test_bomb_guard_is_disabled_for_archival_sizes():
    from PIL import Image
    assert Image.MAX_IMAGE_PIXELS is None


# --------------------------------------------------------------------------- #
# the page's JavaScript, executed for real
# --------------------------------------------------------------------------- #

def _playwright_node_path():
    """Where a playwright install can be found, or None.

    The structural tests above can tell that the markup is right; only a browser
    can tell that the script runs. A markup-only assertion is exactly how a page
    that threw on load once passed this suite.
    """
    if shutil.which("node") is None:
        return None
    candidates = [os.environ.get("NODE_PATH"),
                  str(Path(__file__).resolve().parent.parent / "node_modules")]
    for candidate in filter(None, candidates):
        probe = subprocess.run(["node", "-e", "require.resolve('playwright')"],
                               env={**os.environ, "NODE_PATH": candidate},
                               capture_output=True)
        if probe.returncode == 0:
            return candidate
    return None


NODE_PATH = _playwright_node_path()

BROWSER_CHECK = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await page.goto(process.argv[2]);
  const cards = await page.locator('.card').count();
  const clipBefore = await page.locator('.after').first().evaluate(el => el.style.clipPath);
  await page.locator('.slider').first().click({ position: { x: 20, y: 20 } });
  const clipAfter = await page.locator('.after').first().evaluate(el => el.style.clipPath);
  await page.locator('.card input[value="needs-work"]').first().check();
  await page.locator('.tile textarea').first().fill('gaze drifted');
  await page.locator('[data-action=record]').first().click();
  await page.waitForTimeout(250);
  const log = await page.locator('#log').inputValue();
  console.log(JSON.stringify({ cards, clipBefore, clipAfter, log, errors }));
  await browser.close();
})();
"""


@pytest.mark.needs_pillow
@pytest.mark.skipif(NODE_PATH is None, reason="needs node with playwright installed")
def test_page_script_runs_and_records_in_a_browser(tmp_path):
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    r = run_cli("--pair", src, out, "--crop", "Face:0,0,40,30",
                "--static", "--out-dir", qa_dir, "--json")
    assert r.returncode == 0, r.stderr
    page = Path(json.loads(r.stdout)["page"])

    script = tmp_path / "check.js"
    script.write_text(BROWSER_CHECK)
    probe = subprocess.run(
        ["node", str(script), page.resolve().as_uri()],
        env={**os.environ, "NODE_PATH": NODE_PATH}, capture_output=True, text=True,
        timeout=120,
    )
    assert probe.returncode == 0, probe.stderr
    result = json.loads(probe.stdout)

    assert result["errors"] == [], f"the page threw: {result['errors']}"
    assert result["cards"] == 1
    assert result["clipBefore"] != result["clipAfter"], "the slider did not respond"
    line = json.loads(result["log"])
    assert line["verdict"] == "needs-work"
    assert line["callouts"] == {"face": "gaze drifted"}


# --------------------------------------------------------------------------- #
# second review round
# --------------------------------------------------------------------------- #

@pytest.mark.needs_pillow
def test_hostile_directory_name_cannot_inject_into_the_summary_line(tmp_path):
    """The summary line carries paths; escaping only the cards is not enough."""
    hostile = tmp_path / "<img src=x onerror=alert(1)>"
    hostile.mkdir()
    src, out = make_pair(hostile)
    r = run_cli("--pair", src, out, "--static", "--out-dir", hostile / "qa", "--json")
    assert r.returncode == 0, r.stderr
    html = Path(json.loads(r.stdout)["page"]).read_text()
    assert "<img src=x" not in html


@pytest.mark.needs_pillow
def test_manifest_path_inside_the_project_is_not_double_prefixed(tmp_path):
    """finalize.py records `grandma/source/x.jpg`; prefixing the project again breaks it."""
    project = tmp_path / "grandma"
    (project / "source").mkdir(parents=True)
    (project / "output").mkdir()
    Image.new("RGB", (40, 30)).save(project / "source" / "t.jpg")
    Image.new("RGB", (80, 60)).save(project / "output" / "t_upscale.jpg")
    (project / "manifest.json").write_text(json.dumps({"assets": [{
        "source": "grandma/source/t.jpg", "output": "grandma/output/t_upscale.jpg",
        "verification": "pass"}]}))
    pairs = qa_page.pairs_from_manifest(project)
    assert len(pairs) == 1
    assert pairs[0]["source"] == project / "source" / "t.jpg"


@pytest.mark.needs_pillow
def test_same_stem_different_extension_is_not_collapsed(tmp_path):
    src = tmp_path / "target.jpg"
    Image.new("RGB", (40, 30)).save(src)
    for name in ("target_upscale.jpg", "target_upscale.png"):
        Image.new("RGB", (80, 60)).save(tmp_path / name)
    r = run_cli("--pair", src, tmp_path / "target_upscale.jpg",
                "--pair", src, tmp_path / "target_upscale.png",
                "--static", "--out-dir", tmp_path / "qa", "--json")
    assert r.returncode == 0, r.stderr
    html = Path(json.loads(r.stdout)["page"]).read_text()
    assert 'data-photo="target_upscale.jpg"' in html
    assert 'data-photo="target_upscale.png"' in html


def test_null_timestamp_is_rejected():
    assert qa_page.validate_record({"photo": "a", "verdict": "approve", "ts": None}) is not None


@pytest.mark.needs_pillow
def test_json_stdout_stays_parseable_in_static_mode(tmp_path):
    src, out = make_pair(tmp_path)
    r = run_cli("--pair", src, out, "--static", "--out-dir", tmp_path / "qa", "--json")
    assert r.returncode == 0
    json.loads(r.stdout)  # must not raise


@pytest.mark.needs_pillow
def test_clean_works_from_another_directory(tmp_path):
    src, out = make_pair(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    qa_dir = project / "qa"
    run_cli("--pair", src, out, "--static", "--out-dir", qa_dir, "--json")
    # clean with a relative out-dir from a different cwd
    r = subprocess.run([sys.executable, str(SCRIPT), "--clean", "--out-dir", "qa"],
                       cwd=project, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert not list(qa_dir.glob("review-pass*.html")), "the page survived cleanup"


# --------------------------------------------------------------------------- #
# third review round
# --------------------------------------------------------------------------- #

@pytest.mark.needs_pillow
def test_project_relative_path_wins_over_a_cwd_file(tmp_path, monkeypatch):
    """A same-named file in the cwd must not stand in for the project's photo."""
    a = tmp_path / "A"
    b = tmp_path / "B"
    for project, colour in ((a, (10, 10, 10)), (b, (200, 200, 200))):
        (project / "source").mkdir(parents=True)
        (project / "output").mkdir()
        Image.new("RGB", (40, 30), colour).save(project / "source" / "t.jpg")
        Image.new("RGB", (80, 60), colour).save(project / "output" / "t_upscale.jpg")
        (project / "manifest.json").write_text(json.dumps({"assets": [{
            "source": "source/t.jpg", "output": "output/t_upscale.jpg",
            "verification": "pass"}]}))
    monkeypatch.chdir(a)  # cwd contains the same relative paths
    pairs = qa_page.pairs_from_manifest(b)
    assert pairs[0]["source"] == (b / "source" / "t.jpg").resolve()


def test_keys_are_unique_across_directories(tmp_path):
    pairs = []
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        render = tmp_path / folder / "render.png"
        Image.new("RGB", (40, 30)).save(render)
        pairs.append({"photo": "render.png", "render": render,
                      "source_stem": "src"})
    qa_page.assign_keys(pairs)
    keys = [p["photo"] for p in pairs]
    assert len(set(keys)) == 2, keys
    assert all("render" in k for k in keys), "keys should stay readable"


def test_key_stays_readable_when_unique(tmp_path):
    render = tmp_path / "target_upscale.jpg"
    Image.new("RGB", (40, 30)).save(render)
    pairs = [{"photo": "x", "render": render, "source_stem": "target"}]
    qa_page.assign_keys(pairs)
    assert pairs[0]["photo"] == "target_upscale.jpg"


def test_import_order_survives_a_missing_timestamp(tmp_path):
    qa_dir = tmp_path / "qa"
    download = tmp_path / "d.jsonl"
    download.write_text(
        json.dumps({"photo": "a", "verdict": "approve",
                    "ts": "2026-01-01T00:00:00"}) + "\n"
        + json.dumps({"photo": "a", "verdict": "reject"}) + "\n")
    assert run_cli("--import", download, "--out-dir", qa_dir).returncode == 0
    latest = qa_page.latest_by_photo(qa_page.read_verdicts(qa_dir / "verdicts.jsonl"))
    assert latest["a"]["verdict"] == "reject", "the later correction lost"


def test_json_is_parseable_for_import_and_clean(tmp_path):
    qa_dir = tmp_path / "qa"
    download = tmp_path / "d.jsonl"
    download.write_text(json.dumps({"photo": "a", "verdict": "approve"}) + "\n")
    r = run_cli("--import", download, "--out-dir", qa_dir, "--json")
    assert json.loads(r.stdout)["imported"] == 1
    r = run_cli("--clean", "--out-dir", qa_dir, "--json")
    json.loads(r.stdout)


@pytest.mark.needs_pillow
def test_serve_writes_the_page_it_lists(tmp_path):
    """The generated-file list must reference a file that exists."""
    src, out = make_pair(tmp_path)
    qa_dir = tmp_path / "qa"
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--pair", str(src), str(out),
         "--port", str(port), "--out-dir", str(qa_dir), "--idle-timeout", "20"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        token = None
        deadline = time.time() + 20
        while time.time() < deadline:
            line = proc.stdout.readline()
            if "review page:" in line:
                token = line.strip().rstrip("/").split("/")[-1]
                break
        assert token
        urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/{token}/done", data=b"{}", method="POST"),
            timeout=5).read()
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    listing = json.loads((qa_dir / ".qa-page-files").read_text())
    for path in listing["generated"]:
        assert Path(path).exists(), f"listed a file that does not exist: {path}"


@pytest.mark.needs_pillow
def test_serve_json_stdout_is_clean(tmp_path):
    src, out = make_pair(tmp_path)
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--pair", str(src), str(out), "--json",
         "--port", str(port), "--out-dir", str(tmp_path / "qa"),
         "--idle-timeout", "20"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # The URL goes to stderr under --json, so stdout stays a document.
        token = None
        deadline = time.time() + 20
        while time.time() < deadline and token is None:
            err = proc.stderr.readline()
            if "review page:" in err:
                token = err.strip().rstrip("/").split("/")[-1]
        assert token
        urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/{token}/verdicts",
                data=json.dumps({"photo": out.name, "verdict": "approve"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST"),
            timeout=5).read()
        urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/{token}/done", data=b"{}", method="POST"),
            timeout=5).read()
        stdout, _ = proc.communicate(timeout=20)
        json.loads(stdout)  # must not raise
    finally:
        if proc.poll() is None:
            proc.kill()
