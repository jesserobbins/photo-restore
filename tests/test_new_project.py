"""Tests for new-project.py.

The scaffolder's one dangerous operation is copying files into source/, which the
skill declares read-only evidence. These tests exist so a regression there fails
loudly instead of quietly replacing the photograph being restored.

Run: python -m pytest tests/ -q
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "new-project.py"
spec = importlib.util.spec_from_file_location("new_project", SCRIPT)
new_project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new_project)


def make_image(path, colour=(90, 80, 70), size=(20, 15)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path, quality=90)
    return path


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


def test_scaffold_creates_layout_and_manifest(tmp_path):
    proj = tmp_path / "grandma"
    r = run_cli(proj)
    assert r.returncode == 0, r.stderr
    for sub in new_project.SUBDIRS:
        assert (proj / sub).is_dir(), sub

    data = json.loads((proj / "manifest.json").read_text())
    assert data["schema"] == new_project.SCHEMA
    assert data["assets"] == []
    assert (proj / "README.md").exists()


def test_generated_readme_command_targets_output_dir(tmp_path):
    proj = tmp_path / "p"
    run_cli(proj)
    readme = (proj / "README.md").read_text()
    # The scaffold's own instructions must not write into the read-only dir.
    assert "--out-dir" in readme
    # And the line continuation must be a single backslash, or the shell runs the
    # flag as its own command.
    assert "render.png \\\\" not in readme


def test_master_never_lands_on_top_of_the_source(tmp_path):
    edited = make_image(tmp_path / "edited" / "IMG.jpg", (10, 20, 30))
    master = make_image(tmp_path / "original" / "IMG.jpg", (200, 190, 180))
    proj = tmp_path / "p"
    r = run_cli(proj, "--source", edited, "--master", master)
    assert r.returncode == 0, r.stderr

    assert (proj / "source" / "IMG.jpg").read_bytes() == edited.read_bytes()
    assert (proj / "source" / "IMG_master.jpg").read_bytes() == master.read_bytes()

    data = json.loads((proj / "manifest.json").read_text())
    assert data["sources"] == ["source/IMG.jpg"]
    assert data["masters"] == ["source/IMG_master.jpg"]


def test_refuses_to_overwrite_existing_evidence(tmp_path):
    original = make_image(tmp_path / "in" / "keep.jpg", (1, 2, 3))
    proj = tmp_path / "p"
    run_cli(proj, "--source", original)

    impostor = make_image(tmp_path / "elsewhere" / "keep.jpg", (250, 250, 250))
    r = run_cli(proj, "--force", "--source", impostor)
    assert "already exists" in (r.stdout + r.stderr)
    assert (proj / "source" / "keep.jpg").read_bytes() == original.read_bytes(), \
        "source/ is read-only evidence"


def test_force_merges_manifest_instead_of_wiping_it(tmp_path):
    src = make_image(tmp_path / "a.jpg")
    proj = tmp_path / "p"
    run_cli(proj, "--source", src)

    manifest = proj / "manifest.json"
    data = json.loads(manifest.read_text())
    data["assets"] = [{"verification": "pass", "output": "output/a_upscale.jpg"}]
    created = data["created"]
    manifest.write_text(json.dumps(data))

    extra = make_image(tmp_path / "face.jpg")
    r = run_cli(proj, "--force", "--face", extra)
    assert r.returncode == 0, r.stderr

    after = json.loads(manifest.read_text())
    assert len(after["assets"]) == 1, "verification history must survive re-scaffolding"
    assert after["created"] == created
    assert after["references"]["face"] == ["refs/face/face.jpg"]


def test_refuses_a_nonempty_directory_without_force(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "something.txt").write_text("here")
    r = run_cli(proj)
    assert r.returncode != 0
    assert "--force" in r.stdout + r.stderr


def test_rerunning_with_identical_arguments_is_idempotent(tmp_path):
    src = make_image(tmp_path / "target.jpg")
    ref = make_image(tmp_path / "face.jpg")
    proj = tmp_path / "p"

    first = run_cli(proj, "--source", src, "--face", ref)
    assert first.returncode == 0, first.stderr
    second = run_cli(proj, "--source", src, "--face", ref, "--force")
    assert second.returncode == 0, second.stderr
    assert "already exists" not in (second.stdout + second.stderr)

    data = json.loads((proj / "manifest.json").read_text())
    assert data["sources"] == ["source/target.jpg"]
    assert data["references"]["face"] == ["refs/face/face.jpg"]
