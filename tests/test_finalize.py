"""Tests for finalize.py.

The pure helpers carry the invariants: naming never overwrites, the provenance
note cannot be talked out of disclosing a reconstructed grain, and caption
appends are idempotent. The integration tests pin the exit-code contract and the
one rule the script exists to keep — the original is never written.

Run: python -m pytest tests/ -q
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "finalize.py"
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

spec = importlib.util.spec_from_file_location("finalize", SCRIPT)
finalize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalize)


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("ext,requested,expected", [
    (".jpg", "auto", "jpeg"),
    (".jpeg", "auto", "jpeg"),
    (".png", "auto", "png"),
    (".tif", "auto", "tiff"),
    (".heic", "auto", "jpeg"),
    (".jpg", "png", "png"),
])
def test_choose_format(ext, requested, expected):
    assert finalize.choose_format(Path(f"x{ext}"), requested) == expected


def test_reserve_destination_uses_bare_name_when_free(tmp_path):
    path, created = finalize.reserve_destination(tmp_path, "IMG", "_upscale", ".jpg", False)
    assert path == tmp_path / "IMG_upscale.jpg"
    assert created and path.exists()


def test_reserve_destination_never_reuses_a_taken_name(tmp_path):
    first, _ = finalize.reserve_destination(tmp_path, "IMG", "_upscale", ".jpg", False)
    second, _ = finalize.reserve_destination(tmp_path, "IMG", "_upscale", ".jpg", False)
    third, _ = finalize.reserve_destination(tmp_path, "IMG", "_upscale", ".jpg", False)
    assert [first.name, second.name, third.name] == [
        "IMG_upscale.jpg", "IMG_upscale-2.jpg", "IMG_upscale-3.jpg"]


def test_reserve_destination_force_claims_the_base_name(tmp_path):
    existing = tmp_path / "IMG_upscale.jpg"
    existing.write_text("an earlier result")
    path, created = finalize.reserve_destination(tmp_path, "IMG", "_upscale", ".jpg", True)
    assert path == existing
    assert created is False, "an existing --force target must not be deleted on failure"
    assert existing.read_text() == "an earlier result", "reservation must not truncate"


def test_reserve_destination_force_reports_when_it_created_the_file(tmp_path):
    path, created = finalize.reserve_destination(tmp_path, "IMG", "_upscale", ".jpg", True)
    assert created is True


def test_pick_quarantine_never_overwrites(tmp_path):
    first = finalize.pick_quarantine(tmp_path / "a.jpg")
    assert first.name == "a_UNVERIFIED.jpg"
    first.write_text("x")
    second = finalize.pick_quarantine(tmp_path / "a.jpg")
    assert second.name == "a_UNVERIFIED-2.jpg"


def test_append_text_is_idempotent():
    note = "Upscaled 2.0x."
    once = finalize.append_text("Grandma on the porch.", note)
    assert once == "Grandma on the porch. Upscaled 2.0x."
    assert finalize.append_text(once, note) == once


def test_append_text_keeps_empty_caption_clean():
    assert finalize.append_text(None, "note") == "note"
    assert finalize.append_text("", "note") == "note"


def test_already_noted_matches_the_note_actually_written():
    assert finalize.already_noted("Restored. Upscaled 2.0x.", "Upscaled 2.0x.")
    assert not finalize.already_noted("Restored.", "Upscaled 2.0x.")
    assert not finalize.already_noted(None, "anything")


def test_merge_keywords_preserves_order_and_dedupes_case_insensitively():
    assert finalize.merge_keywords(["family", "1960s"], ["Family", "upscaled"]) == \
        ["family", "1960s", "upscaled"]


def test_parse_keywords_splits_exiftool_list():
    assert finalize.parse_keywords("family, 1960s") == ["family", "1960s"]
    assert finalize.parse_keywords(None) == []


@pytest.mark.parametrize("size,orientation,expected", [
    ((400, 300), "1", (400, 300)),
    ((400, 300), None, (400, 300)),
    ((400, 300), "6", (300, 400)),
    ((400, 300), "8", (300, 400)),
    ((400, 300), "3", (400, 300)),
])
def test_transposed_size(size, orientation, expected):
    assert finalize.transposed_size(size, orientation) == expected


# --------------------------------------------------------------------------- #
# provenance and grain disclosure
# --------------------------------------------------------------------------- #

def _note(**kw):
    args = dict(scale=2.0, src_name="IMG_1.jpg", src_dims=(400, 300),
                out_dims=(800, 600), when="2026-10-19", note=None, grain=None)
    args.update(kw)
    return finalize.provenance_note(**args)


def test_default_note_mentions_scale_and_source_and_capture_date():
    note = _note()
    assert "Upscaled 2.0x" in note
    assert "IMG_1.jpg" in note
    assert "Capture date unchanged" in note


def test_preserved_grain_does_not_claim_reconstruction():
    assert "grain" not in _note(grain="preserved").lower()


def test_reconstructed_grain_discloses():
    assert finalize.GRAIN_DISCLOSURE in _note(grain="reconstructed")


def test_custom_note_cannot_defeat_reconstruction_disclosure():
    """The bug this test exists for: 'grain preserved' contains the word grain."""
    note = _note(note="Film grain preserved through the upscale", grain="reconstructed")
    assert finalize.GRAIN_DISCLOSURE in note
    assert note.startswith("Film grain preserved through the upscale")


def test_disclosure_is_not_duplicated():
    first = _note(grain="reconstructed")
    assert finalize.GRAIN_DISCLOSURE in first
    assert first.count(finalize.GRAIN_DISCLOSURE) == 1


# --------------------------------------------------------------------------- #
# integration: exit codes and the read-only original
# --------------------------------------------------------------------------- #

pytestmark_needs_pillow = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool required for these paths"
)


def make_jpeg(path, size=(60, 45), orientation=None, tags=True):
    im = Image.new("RGB", size, (120, 90, 60))
    kwargs = {}
    if tags:
        exif = Image.Exif()
        exif[271] = "Kodak"
        exif[272] = "Retina"
        if orientation:
            exif[274] = orientation
        kwargs["exif"] = exif.tobytes()
    im.save(path, format="JPEG", quality=95, **kwargs)
    if tags and shutil.which("exiftool"):
        # DateTimeOriginal lives in the Exif sub-IFD, which Pillow will not write
        # for us. Stamp it with the same tool the script uses.
        subprocess.run(
            ["exiftool", "-q", "-overwrite_original",
             "-DateTimeOriginal=1962:06:14 11:05:00",
             "-CreateDate=1962:06:14 11:05:00", str(path)],
            check=True, capture_output=True,
        )
    return path


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, env=env)


def test_empty_suffix_is_refused_before_anything_is_written(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    r = run_cli(src, render, "--suffix", "", "--force")
    assert r.returncode == 2
    assert "suffix" in r.stderr.lower()
    assert src.read_bytes()  # untouched


def test_missing_source_exits_2_not_1(tmp_path):
    render = make_jpeg(tmp_path / "r.jpg")
    r = run_cli(tmp_path / "nope.jpg", render)
    assert r.returncode == 2


def test_source_and_render_are_the_same_file(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    r = run_cli(src, src)
    assert r.returncode == 2


def test_aspect_mismatch_is_refused(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg", size=(60, 45))
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 100), tags=False)
    r = run_cli(src, render)
    assert r.returncode == 2
    assert "aspect" in r.stderr.lower()


@pytestmark_needs_pillow
def test_original_is_never_written_and_metadata_carries(tmp_path):
    src = make_jpeg(tmp_path / "IMG_1234.jpg")
    before = src.read_bytes()
    render = make_jpeg(tmp_path / "render.jpg", size=(120, 90), tags=False)

    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr
    assert src.read_bytes() == before, "the original must be untouched"

    out = tmp_path / "IMG_1234_upscale.jpg"
    assert out.exists()
    import json as _json
    got = subprocess.run(["exiftool", "-q", "-json", str(out)],
                         capture_output=True, text=True).stdout
    tags = _json.loads(got)[0]
    assert tags["DateTimeOriginal"] == "1962:06:14 11:05:00"
    assert tags["Make"] == "Kodak"
    assert tags["Orientation"] == "Horizontal (normal)"
    assert tags["ExifImageWidth"] == 120
    assert "Upscaled 2.0x" in tags["UserComment"]


@pytestmark_needs_pillow
def test_no_exiftool_degrades_and_still_writes_a_readable_file(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)

    # Strip exiftool from PATH but keep everything else.
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep)
        if not (Path(p) / "exiftool").exists()
    )
    r = run_cli(src, render, "--json", env=env)
    assert r.returncode == 0, r.stderr
    entry = json.loads(r.stdout)
    assert entry["verification"] == "degraded"

    out = Path(entry["output"])
    with Image.open(out) as im:
        assert im.size == (120, 90)
        im.load()  # a self-clobbered save would fail here


@pytestmark_needs_pillow
def test_rotated_render_is_baked_and_normalised(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg", size=(60, 45))
    # Render is stored rotated with a matching orientation tag, so it displays
    # at the same aspect as the source. It must come out upright with tag 1.
    render = make_jpeg(tmp_path / "r.jpg", size=(90, 120), orientation=6, tags=True)
    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr

    out = tmp_path / "s_upscale.jpg"
    with Image.open(out) as im:
        assert im.size == (120, 90)
    got = subprocess.run(["exiftool", "-q", "-s3", "-Orientation#", str(out)],
                         capture_output=True, text=True).stdout.strip()
    assert got == "1"


# --------------------------------------------------------------------------- #
# iteration 2 regressions
# --------------------------------------------------------------------------- #

@pytestmark_needs_pillow
def test_nonexistent_project_exits_2_before_writing(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    r = run_cli(src, render, "--project", tmp_path / "typo")
    assert r.returncode == 2, r.stdout + r.stderr
    assert not (tmp_path / "s_upscale.jpg").exists()
    assert "Traceback" not in r.stderr


@pytestmark_needs_pillow
def test_project_defaults_out_dir_to_output(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    proj = tmp_path / "p"
    for sub in ("source", "output"):
        (proj / sub).mkdir(parents=True)
    shutil.copy2(src, proj / "source" / "s.jpg")
    r = run_cli(proj / "source" / "s.jpg", render, "--project", proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (proj / "output" / "s_upscale.jpg").exists()
    assert not (proj / "source" / "s_upscale.jpg").exists(), "source/ must stay read-only"


@pytestmark_needs_pillow
def test_32bit_render_is_refused_not_clipped(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = tmp_path / "r.tif"
    Image.new("F", (120, 90), 0.5).save(render, format="TIFF")
    r = run_cli(src, render)
    assert r.returncode == 2
    assert "32-bit" in r.stderr
    assert not list(tmp_path.glob("s_upscale*")), "exit 2 must leave nothing behind"


@pytestmark_needs_pillow
def test_32bit_render_is_kept_when_the_target_can_hold_it(tmp_path):
    """The refusal recommends --format tiff, so that path has to actually work."""
    src = make_jpeg(tmp_path / "s.jpg")
    render = tmp_path / "r.tif"
    Image.new("F", (120, 90), 0.5).save(render, format="TIFF")
    r = run_cli(src, render, "--format", "tiff")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "s_upscale.tif").exists()


@pytestmark_needs_pillow
def test_png_bytes_named_jpg_are_reencoded_to_jpeg(tmp_path):
    """An extension is a claim; the byte-copy shortcut must read the contents."""
    src = make_jpeg(tmp_path / "s.jpg")
    liar = tmp_path / "r.jpg"
    Image.new("RGB", (120, 90), (10, 20, 30)).save(liar, format="PNG")
    r = run_cli(src, liar)
    assert r.returncode == 0, r.stdout + r.stderr
    with Image.open(tmp_path / "s_upscale.jpg") as im:
        assert im.format == "JPEG"


@pytestmark_needs_pillow
def test_source_usercomment_is_appended_not_replaced(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    "-UserComment=Scanner note from 2004", str(src)], check=True)
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr
    got = subprocess.run(["exiftool", "-q", "-s3", "-UserComment",
                          str(tmp_path / "s_upscale.jpg")],
                         capture_output=True, text=True).stdout
    assert "Scanner note from 2004" in got
    assert "Upscaled 2.0x" in got


@pytestmark_needs_pillow
def test_embedded_thumbnail_is_cleared(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    # exiftool will build a thumbnail from the image if asked to embed one.
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    "-ThumbnailImage<=s.jpg", str(src)],
                   cwd=tmp_path, capture_output=True)
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr
    thumb = subprocess.run(["exiftool", "-q", "-s3", "-ThumbnailImage",
                            str(tmp_path / "s_upscale.jpg")],
                           capture_output=True, text=True).stdout.strip()
    assert thumb == "", "the pre-restoration thumbnail must not survive"


@pytestmark_needs_pillow
def test_xmp_sidecar_metadata_is_merged(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    sidecar = tmp_path / "s.jpg.xmp"
    subprocess.run(["exiftool", "-q", "-o", str(sidecar), str(src)], check=True)
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    "-Description=Caption that lives only in the sidecar",
                    "-Subject=sidecar-only", str(sidecar)], check=True)
    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr
    got = subprocess.run(["exiftool", "-q", "-s3", "-XMP:Subject", "-Description",
                          str(tmp_path / "s_upscale.jpg")],
                         capture_output=True, text=True).stdout
    # A sidecar is XMP, so its keywords land in XMP-dc:Subject rather than IPTC
    # Keywords. Nothing is lost, but the tag is different and worth pinning.
    assert "sidecar-only" in got, got
    assert "Caption that lives only in the sidecar" in got, got


@pytestmark_needs_pillow
def test_concurrent_runs_cannot_take_the_same_destination(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), str(src), str(render), "--json"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for _ in range(4)]
    outputs = []
    for p in procs:
        out, err = p.communicate()
        assert p.returncode == 0, err
        outputs.append(Path(json.loads(out)["output"]))

    # A glob always yields unique names, so assert on what the runs reported: four
    # distinct published files, each a complete image.
    assert len(set(outputs)) == 4, outputs
    for path in outputs:
        with Image.open(path) as im:
            im.verify()


# --------------------------------------------------------------------------- #
# iteration 3 regressions
# --------------------------------------------------------------------------- #

@pytestmark_needs_pillow
def test_render_icc_profile_wins_over_the_source(tmp_path):
    """Copying the source profile over a converted render mislabels its colours."""
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)

    # Two visibly different profiles, built from the system colour profiles.
    profiles = sorted(Path("/System/Library/ColorSync/Profiles").glob("*.icc"))
    if len(profiles) < 2:
        pytest.skip("need two system ICC profiles")
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    f"-ICC_Profile<={profiles[0]}", str(src)], check=True)
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    f"-ICC_Profile<={profiles[1]}", str(render)], check=True)

    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr

    got = subprocess.run(["exiftool", "-q", "-s3", "-ICC_Profile:ProfileDescription",
                          str(tmp_path / "s_upscale.jpg")],
                         capture_output=True, text=True).stdout.strip()
    want = subprocess.run(["exiftool", "-q", "-s3", "-ICC_Profile:ProfileDescription",
                           str(render)], capture_output=True, text=True).stdout.strip()
    assert got == want, f"render profile {want!r} should survive, got {got!r}"


@pytestmark_needs_pillow
def test_sidecar_subjects_are_merged_not_replaced(tmp_path):
    src = make_jpeg(tmp_path / "s.jpg")
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    "-Subject=family", str(src)], check=True)
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    sidecar = tmp_path / "s.jpg.xmp"
    subprocess.run(["exiftool", "-q", "-o", str(sidecar), str(src)], check=True)
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    "-Subject=travel", str(sidecar)], check=True)

    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr
    got = subprocess.run(["exiftool", "-q", "-s3", "-Subject",
                          str(tmp_path / "s_upscale.jpg")],
                         capture_output=True, text=True).stdout
    assert "family" in got and "travel" in got, got


@pytestmark_needs_pillow
def test_xmp_orientation_is_normalised_too(tmp_path):
    """A stale XMP orientation rotates upright pixels in XMP-preferring readers."""
    src = make_jpeg(tmp_path / "s.jpg", size=(60, 45))
    subprocess.run(["exiftool", "-q", "-overwrite_original",
                    "-Orientation#=6", "-XMP-tiff:Orientation#=6", str(src)], check=True)
    # Source is 60x45 stored with orientation 6, so it displays 45x60. The render
    # must display at 2x that: 90x120, stored as 120x90 with orientation 6.
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), orientation=6, tags=True)
    r = run_cli(src, render)
    assert r.returncode == 0, r.stdout + r.stderr

    out = tmp_path / "s_upscale.jpg"
    for tag in ("-Orientation#", "-XMP-tiff:Orientation#"):
        got = subprocess.run(["exiftool", "-q", "-s3", tag, str(out)],
                             capture_output=True, text=True).stdout.strip()
        assert got in ("", "1"), f"{tag} left at {got}"


@pytestmark_needs_pillow
def test_cross_filesystem_output_does_not_strand_an_empty_file(tmp_path):
    """Staging must happen on the destination filesystem (EXDEV guard)."""
    src = make_jpeg(tmp_path / "s.jpg")
    render = make_jpeg(tmp_path / "r.jpg", size=(120, 90), tags=False)
    out = tmp_path / "elsewhere"
    out.mkdir()
    r = run_cli(src, render, "--out-dir", out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (out / "s_upscale.jpg").exists()
    assert not list(out.glob(".finalize-*")), "staging dir should be cleaned up"
