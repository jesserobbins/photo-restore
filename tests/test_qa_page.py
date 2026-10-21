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
    by_photo = qa_page.callouts_for(crops, ["a", "b"])
    assert set(by_photo) == {"a", "b"}
    assert by_photo["a"]["eyes"]["box"] == (0, 0, 10, 10)


def test_duplicate_slug_with_different_boxes_is_refused():
    crops = [qa_page.parse_crop("a:Left eye:0,0,10,10"),
             qa_page.parse_crop("a:left-eye:20,20,40,40")]
    with pytest.raises(SystemExit) as exc:
        qa_page.callouts_for(crops, ["a"])
    assert exc.value.code == 2


def test_same_slug_and_same_box_is_allowed():
    crops = [qa_page.parse_crop("a:Left eye:0,0,10,10"),
             qa_page.parse_crop("a:left-eye:0,0,10,10")]
    assert len(qa_page.callouts_for(crops, ["a"])["a"]) == 1


def test_crop_naming_an_unknown_photo_is_refused():
    crops = [qa_page.parse_crop("ghost:Eyes:0,0,10,10")]
    with pytest.raises(SystemExit) as exc:
        qa_page.callouts_for(crops, ["a"])
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
    assert pairs[0]["photo"] == "target"


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
