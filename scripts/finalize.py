#!/usr/bin/env python3
"""Turn a raw upscale render into a delivered file: rename, preserve metadata, verify.

This is the last step of a restoration. It takes the authoritative source photo and
the render some upscaler produced, then writes a correctly named output whose
metadata is copied from the source and corrected where the upscale made it false.

Order is fixed and not negotiable: encode, then copy, then correct, then verify.
Copying before encoding loses everything; verifying before correcting measures the
wrong thing.

Orientation has one rule: a render is measured and handled by its *displayed*
dimensions, and any render carrying an orientation other than 1 is transcoded so
the transform is baked before the tag is normalised. The byte-copy shortcut is
therefore only taken when there is nothing to transform.

Dependencies: Pillow. exiftool is strongly preferred. ImageMagick or sips is needed
only to read HEIC/HEIF, which Pillow cannot decode.

Exit codes:
  0  verified (or degraded, with the shortfall listed)
  1  verification failed -- output renamed *_UNVERIFIED, do not deliver or import
  2  usage or environment error -- nothing was written
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image as _PILImage

# A 4x upscale of a 600 dpi 8x10 scan is ~460 MP, well past Pillow's ~179 MP
# decompression-bomb limit. These are the owner's own files, opened deliberately,
# so the guard is off. Failures still surface as decode errors.
_PILImage.MAX_IMAGE_PIXELS = None

VERSION = "2.0"
TOOL = "photo-restore"
PROG = f"{TOOL} {VERSION}"

# Source tags that must survive into the output. Missing any of these is a hard
# failure when the source had them, because silently dropping a capture date or a
# GPS fix is indistinguishable from data loss. Every one of these is actually read
# from both sides in read_state(), or the check would be unfalsifiable.
CORE_TAGS = (
    "DateTimeOriginal", "CreateDate", "Make", "Model", "GPSLatitude", "Rating",
)

# The exact sentence that marks a synthesised texture. Matched whole, never by the
# word "grain", because a custom note saying "grain preserved" must not be able to
# satisfy the disclosure check.
GRAIN_DISCLOSURE = (
    "Film grain reconstructed to match the stock; not recovered from source evidence."
)

HEIF_SUFFIXES = {".heic", ".heif", ".hif", ".avif"}
FORMAT_EXT = {"jpeg": ".jpg", "png": ".png", "tiff": ".tif"}


def die(message):
    """Environment or usage failure: nothing was written. Exit code 2."""
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #

def have(cmd):
    return shutil.which(cmd) is not None


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def exiftool_write(path, args):
    """Write tags with exiftool. Returns (ok, stderr_warnings).

    A single -q keeps silent about progress but leaves warnings visible, which is
    what catches things like a truncated IPTC caption.
    """
    cmd = ["exiftool", "-q", "-overwrite_original", *args, str(path)]
    proc = run(cmd)
    return proc.returncode == 0, proc.stderr.strip()


def exiftool_read(path, tags, numeric=False):
    """Read tags as a dict of tag -> value or None. Numeric reads use the # form."""
    out = {}
    for tag in tags:
        key = f"{tag}#" if numeric else tag
        proc = run(["exiftool", "-q", "-q", "-s3", f"-{key}", str(path)])
        out[tag] = (proc.stdout.rstrip("\n") or None) if proc.returncode == 0 else None
    return out


def image_size(path):
    """Pixel dimensions of any supported file, without assuming Pillow can read it."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        pass
    if have("exiftool"):
        proc = run(["exiftool", "-q", "-q", "-s3", "-ImageWidth", "-ImageHeight", str(path)])
        vals = proc.stdout.split()
        if len(vals) >= 2 and all(v.isdigit() for v in vals[:2]):
            return int(vals[0]), int(vals[1])
    if have("magick"):
        # The only fallback left for a HEIC on a host with neither exiftool nor
        # sips, which is the case the ImageMagick decode path exists for.
        proc = run(["magick", "identify", "-format", "%w %h", str(path)])
        vals = proc.stdout.split()
        if proc.returncode == 0 and len(vals) >= 2 and all(v.isdigit() for v in vals[:2]):
            return int(vals[0]), int(vals[1])
    if have("sips"):
        proc = run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)])
        nums = re.findall(r":\s*(\d+)", proc.stdout)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
    return None


def image_orientation(path):
    """EXIF orientation as a string ('1'..'8'), or '1' when unknown/absent."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            value = im.getexif().get(274)
            if value:
                return str(value)
    except Exception:
        pass
    if have("exiftool"):
        value = exiftool_read(path, ["Orientation"], numeric=True).get("Orientation")
        if value and value.isdigit():
            return value
    if have("magick"):
        # sips and magick can read HEIC EXIF where Pillow cannot.
        proc = run(["magick", "identify", "-format", "%[EXIF:Orientation]", str(path)])
        if proc.returncode == 0 and proc.stdout.strip().isdigit():
            return proc.stdout.strip()
    if have("sips"):
        proc = run(["sips", "-g", "orientation", str(path)])
        found = re.search(r"orientation:\s*(\w+)", proc.stdout)
        if found:
            names = {"up": "1", "down": "3", "left": "6", "right": "8"}
            if found.group(1).lower() in names:
                return names[found.group(1).lower()]
    return "1"


def decode_with_system(src, dst, target_format):
    """Decode a format Pillow cannot read (HEIC) using a system tool.

    The intermediate is lossless when the final container is lossless: decoding a
    HEIC to JPEG only to write a PNG spends a generation for nothing.
    """
    fmt = "png" if target_format in ("png", "tiff") else "jpeg"
    if have("magick"):
        proc = run(["magick", str(src), "-colorspace", "sRGB", str(dst)])
        if proc.returncode == 0 and dst.exists():
            return "magick"
    if have("sips"):
        proc = run(["sips", "-s", "format", fmt, str(src), "--out", str(dst)])
        if proc.returncode == 0 and dst.exists():
            return "sips"
    return None


def readable_render(render, workdir, target_format):
    """A path Pillow can open for the render, decoding once if it must.

    Every reader downstream (metadata, ICC, encode) then works from the same file,
    so a HEIC render cannot lose its profile to one code path and keep it in
    another.
    """
    try:
        from PIL import Image
        with Image.open(render):
            return render, None
    except Exception:
        pass
    if render.suffix.lower() not in HEIF_SUFFIXES:
        return render, None
    dst = workdir / ("decoded.png" if target_format in ("png", "tiff") else "decoded.jpg")
    tool = decode_with_system(render, dst, target_format)
    if not tool:
        die(
            f"{render.name} is {render.suffix}, which Pillow cannot decode. Install "
            "ImageMagick or use macOS sips, or export the photo as JPEG first. "
            "Refusing to write pixels from a file I could not read."
        )
    return dst, tool


# --------------------------------------------------------------------------- #
# metadata
# --------------------------------------------------------------------------- #

def transposed_size(size, orientation):
    """Displayed dimensions after applying EXIF orientation."""
    if orientation in ("5", "6", "7", "8"):
        return size[1], size[0]
    return size


def expected_source_state(source, use_exiftool):
    """What the output must contain: the source image unioned with its sidecar.

    Verification compared against the image file alone, so a caption or a capture
    date that lives only in an XMP sidecar -- what `osxphotos export --sidecar
    xmp` produces -- was unverifiable: its loss would have reported pass.
    """
    state = read_state(source) if use_exiftool else read_state_pillow(source)
    if use_exiftool:
        sidecar = source.with_name(source.name + ".xmp")
        if sidecar.exists():
            for key, value in read_state(sidecar).items():
                if value and not state.get(key):
                    state[key] = value
    return state


def read_state(path):
    tags = exiftool_read(
        path,
        ["Orientation", "DateTimeOriginal", "CreateDate", "Make", "Model", "Rating",
         "Caption-Abstract", "Description", "UserComment", "Software"],
    )
    # List tags are read as lists so a keyword containing a comma survives.
    tags["Keywords"] = exiftool_read_list(path, "Keywords")
    tags["Subject"] = exiftool_read_list(path, "Subject")
    tags["Orientation#"] = exiftool_read(path, ["Orientation"], numeric=True).get("Orientation")
    # Bare -GPSLatitude resolves to the composite, which is the readable form.
    tags["GPSLatitude"] = exiftool_read(path, ["GPSLatitude"]).get("GPSLatitude")
    return tags


def read_state_pillow(path):
    """Minimal state for hosts without exiftool, so degraded runs still verify."""
    state = {k: None for k in
             (*CORE_TAGS, "Orientation", "Keywords", "Caption-Abstract",
              "Description", "UserComment", "Software", "Orientation#")}
    try:
        from PIL import Image
        with Image.open(path) as im:
            exif = im.getexif()
            state["Make"] = exif.get(271)
            state["Model"] = exif.get(272)
            state["Orientation#"] = str(exif.get(274)) if exif.get(274) else None
            state["Orientation"] = state["Orientation#"]
            # DateTimeOriginal lives in the Exif sub-IFD, not IFD0.
            sub = exif.get_ifd(0x8769)
            state["DateTimeOriginal"] = sub.get(36867)
            state["CreateDate"] = sub.get(36868)
    except Exception:
        pass
    return state


def provenance_note(scale, src_name, src_dims, out_dims, when, note, grain=None):
    if note:
        base = note
    else:
        base = (
            f"Upscaled {scale:.1f}x ({src_dims[0]}x{src_dims[1]} to "
            f"{out_dims[0]}x{out_dims[1]}) by {PROG}, conservative mode, "
            f"on {when}. Source: {src_name}. Capture date unchanged."
        )
    # A reconstructed texture is not preservation, and the file itself must say so.
    # Matched on the whole sentence, so a note that merely contains the word
    # "grain" cannot stand in for the disclosure.
    if grain == "reconstructed" and GRAIN_DISCLOSURE not in base:
        base = f"{base} {GRAIN_DISCLOSURE}"
    return base


def already_noted(text, note):
    """Has this exact note already landed in a human-readable tag?

    Keyed on the note itself rather than on the tool name or a fixed phrase, so a
    custom --note dedupes and verifies the same way the default one does.
    """
    if not text or not note:
        return False
    return note.strip() in text


def append_text(text, addition):
    """Append to a human-readable tag without stacking the same note twice."""
    if not text:
        return addition
    if addition.strip() in text:
        return text
    return f"{text.rstrip()} {addition}"


def merge_keywords(existing, new):
    """Merge keyword lists, preserving order and dropping case-insensitive dupes."""
    out, seen = [], set()
    for kw in list(existing or []) + list(new or []):
        kw = (kw or "").strip()
        if not kw or kw.lower() in seen:
            continue
        seen.add(kw.lower())
        out.append(kw)
    return out


def exiftool_read_list(path, tag):
    """Read a list tag as a real list.

    `-s3` joins list values with ", ", which splits an owner keyword like
    "Washington, D.C." into two when split back apart. JSON gives the actual list.
    """
    proc = run(["exiftool", "-q", "-q", "-json", f"-{tag}", str(path)])
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return []
    if not data:
        return []
    value = data[0].get(tag)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def parse_keywords(raw):
    """Normalise a list tag to a list.

    read_state returns real lists now; a string can still arrive from a caller
    that read the tag with -s3, so accept both rather than guessing.
    """
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(k).strip() for k in raw if str(k).strip()]
    return [k.strip() for k in str(raw).split(",") if k.strip()]


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #

def choose_format(source, requested):
    if requested and requested != "auto":
        return requested
    ext = source.suffix.lower()
    if ext == ".png":
        return "png"
    if ext in {".tif", ".tiff"}:
        return "tiff"
    # JPEG and anything Pillow cannot re-encode losslessly falls back to JPEG,
    # the only container whose metadata travels everywhere.
    return "jpeg"


# Modes that JPEG flattens into RGB, invalidating a grayscale or press profile.
# "1" is bilevel: encode() converts it to RGB, where a gray profile no longer fits.
JPEG_BREAKS_PROFILE = {"CMYK", "YCCK", "LAB", "HSV", "LA", "La", "1"}


def profile_survives(render_mode, target_format):
    """Does the render's own ICC profile still describe the output pixels?

    PNG and TIFF keep the mode they were handed, so the profile always fits. JPEG
    forces RGB or L, which breaks a press profile and a grayscale-plus-alpha
    profile, but keeps a plain grayscale one (16-bit included, rescaled to 8-bit).
    """
    if target_format != "jpeg":
        return True
    return render_mode not in JPEG_BREAKS_PROFILE


def detected_format(path):
    """Actual container from file contents. An extension is a claim, not a fact."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return (im.format or "").upper()
    except Exception:
        return ""


def container_matches(path, target_format):
    """Compare real contents, not the filename: render.jpg may hold PNG bytes."""
    expect = {"jpeg": "JPEG", "png": "PNG", "tiff": "TIFF"}[target_format]
    return detected_format(path) == expect


def reserve_destination(out_dir, stem, suffix, ext, force):
    """Returns (path, created). `created` says whether this run made the file, so
    a failure can remove its own empty reservation without touching an existing
    --force target."""
    """Claim the output path atomically, so two runs cannot pick the same name.

    The manifest lock never protected output allocation: both runs could see the
    same free name and the second move would silently replace the first result.
    Creating the file with O_EXCL is the claim; a later os.replace fills it.
    """
    base = f"{stem}{suffix}"
    for n in range(1, 1000):
        candidate = out_dir / (f"{base}{ext}" if n == 1 else f"{base}-{n}{ext}")
        if force and n == 1:
            created = not candidate.exists()
            candidate.touch(exist_ok=True)
            return candidate, created
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        os.close(fd)
        return candidate, True
    die(f"could not find a free output name for {base}{ext}")


def pick_quarantine(path):
    """A collision-free name for a failed output, never overwriting an earlier one."""
    candidate = path.with_name(path.stem + "_UNVERIFIED" + path.suffix)
    n = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_UNVERIFIED-{n}{path.suffix}")
        n += 1
    return candidate


EXIF_PIXEL_X = 0xA002
EXIF_PIXEL_Y = 0xA003


def source_embed(source, render, out_size, target_format):
    """EXIF blob and ICC profile for the no-exiftool path.

    Two things must not be inherited blindly. Dimensions: the source's
    ExifImageWidth describes the *source*, so it is rewritten to the real output
    size, or dropped when Pillow cannot address it. Colour: the source's ICC
    profile describes the source's pixels, so the render's own profile wins when
    it has one.
    """
    embed = {}
    notes = []
    # The render's profile is read first and separately: a source Pillow cannot
    # open (HEIC) must not cost the render its own colour description.
    try:
        from PIL import Image
        with Image.open(render) as rnd:
            if profile_survives(rnd.mode, target_format):
                if rnd.info.get("icc_profile"):
                    embed["icc_profile"] = rnd.info["icc_profile"]
            elif rnd.info.get("icc_profile"):
                notes.append(
                    "the render's ICC profile was dropped: its colour model changed "
                    "during the encode, so the profile no longer describes the output"
                )
    except Exception:
        pass

    try:
        from PIL import Image
        with Image.open(source) as src:
            if src.info.get("exif"):
                exif = Image.Exif()
                exif.load(src.info["exif"])
                exif[274] = 1  # pixels are baked upright by the time this is attached
                sub = exif.get_ifd(0x8769)
                try:
                    sub[EXIF_PIXEL_X] = out_size[0]
                    sub[EXIF_PIXEL_Y] = out_size[1]
                except Exception:
                    notes.append("could not correct EXIF dimension tags; dropped instead")
                    sub.pop(EXIF_PIXEL_X, None)
                    sub.pop(EXIF_PIXEL_Y, None)
                embed["exif"] = exif.tobytes()
        source_icc = src.info.get("icc_profile")
        if source_icc and "icc_profile" not in embed:
            notes.append(
                "the source ICC profile was not carried: the output holds the render's "
                "pixels, whose own profile either does not exist or no longer "
                "describes them, so the source profile would have mislabelled them"
            )
    except Exception as exc:
        notes.append(f"could not build an embedded metadata blob: {exc}")
    return embed, notes


def encode(render, target_format, workdir, quality, embed=None, transcode=False):
    """Produce a file in the target container. Returns (path, transcoded, note)."""
    render_fmt = render.suffix.lower()
    if not transcode and not embed and container_matches(render, target_format):
        # Nothing to transform and nothing to merge: copy bytes and let the
        # metadata pass handle tags. Anything else costs a quality generation.
        out = workdir / f"stage{render.suffix}"
        shutil.copy2(render, out)
        # The output carries the render's *pixels*, never its claims. Stripping
        # here means the source's metadata is written onto a blank slate, so
        # there is nothing to un-invent: an editing tool's camera, location,
        # caption or processing date cannot survive into a delivered file.
        ok_strip, warn_strip = exiftool_write(out, ["-all="])
        if not ok_strip:
            # The whole blank-slate guarantee rests on this. Delivering an
            # unstripped file would carry the render's camera, location, caption
            # and processing date as if they were the photograph's.
            die(f"could not strip the render's metadata, nothing was written: {warn_strip}")
        return out, False, "pixels untouched; render metadata stripped", True

    out = workdir / f"stage{FORMAT_EXT[target_format]}"
    from PIL import Image, ImageOps

    staged = render

    save_kw = dict(embed or {})
    colour_model_preserved = True
    render_mode = ""
    with Image.open(staged) as im:
        render_mode = im.mode
        # Only a conversion that changes colour space invalidates the profile.
        # PNG/TIFF keep the mode they were handed.
        colour_model_preserved = (
            True if target_format != "jpeg" else profile_survives(render_mode, target_format)
        )
        # Baking the transform here is why the orientation tag can be normalised
        # afterwards: after this point the pixels are upright.
        im = ImageOps.exif_transpose(im)
        if target_format == "jpeg" and (im.mode.startswith("I;16") or im.mode in ("I", "F")):
            # JPEG has no depth to keep, so 16-bit is rescaled rather than clipped,
            # and 32-bit is refused because any mapping would guess a black point.
            if im.mode.startswith("I;16"):
                im = im.convert("I").point(lambda v: v / 256.0).convert("L")
            else:
                die(
                    f"the render is 32-bit {im.mode} data. Keep it with "
                    "--format tiff, or provide an 8-bit render; mapping it to JPEG "
                    "would have to guess a black point."
                )
        # Pillow's PNG and TIFF writers fall back to im.info for ICC_Profile (not
        # for EXIF, which only arrives through save() arguments). Clearing it keeps
        # the render's colour description from riding along unchosen, and an embed
        # holding only an ICC profile is still no reason to inherit anything else.
        if "icc_profile" not in save_kw:
            im.info.pop("icc_profile", None)
        if "exif" not in save_kw:
            im.info.pop("exif", None)
        if target_format == "jpeg":
            if im.mode in ("RGBA", "LA", "P"):
                base = Image.new("RGB", im.size, (255, 255, 255))
                rgba = im.convert("RGBA")
                base.paste(rgba, mask=rgba.split()[-1])
                im = base
            elif im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(out, format="JPEG", quality=quality, subsampling=0,
                    optimize=True, **save_kw)
        elif target_format == "png":
            im.save(out, format="PNG", optimize=True, **save_kw)
        else:
            im.save(out, format="TIFF", compression="tiff_lzw", **save_kw)

    if not embed and have("exiftool"):
        # Same rule as the byte-copy path: strip whatever survived the encode.
        ok_strip, warn_strip = exiftool_write(out, ["-all="])
        if not ok_strip:
            die(f"could not strip the render's metadata, nothing was written: {warn_strip}")

    detail = f"{render_fmt} -> {target_format}"
    if transcode:
        detail += " (orientation baked)"
    return out, True, detail, colour_model_preserved


def copy_metadata(source, dest, render, colour_model_preserved=True, reencoded=True):
    """Pass 1: copy everything the source knows, including an XMP sidecar.

    `osxphotos export --sidecar xmp` puts metadata next to the file rather than in
    it. Ignoring the sidecar silently drops captions and keywords that exist
    nowhere else, and verification cannot see the loss.
    """
    ok, warn = exiftool_write(dest, ["-TagsFromFile", str(source), "-all:all", "-unsafe"])

    # The render's own ICC profile describes the render's pixels. Copying the
    # source's over it would relabel the colour space without converting it.
    # Read it with exiftool, not Pillow: a HEIC render is supported by encode()
    # through magick/sips and would crash here after the output was published.
    render_has_icc = bool(
        exiftool_read(render, ["ICC_Profile:ProfileDescription"]).get("ICC_Profile:ProfileDescription")
    )
    icc_note = None
    if render_has_icc and colour_model_preserved:
        ok_icc, warn_icc = exiftool_write(
            dest, ["-TagsFromFile", str(render), "-ICC_Profile"]
        )
        ok = ok and ok_icc
        warn = "\n".join(w for w in (warn, warn_icc) if w)
    else:
        # The output carries the *render's* pixels, so the source's profile never
        # describes them -- not even on a byte-copy, which copies render bytes.
        # Leaving it on labels the file confidently and wrongly; dropping it lets
        # the viewer assume sRGB, which is a default rather than a false claim.
        source_has_icc = bool(
            exiftool_read(source, ["ICC_Profile:ProfileDescription"])
            .get("ICC_Profile:ProfileDescription")
        )
        if source_has_icc:
            ok_strip, warn_strip = exiftool_write(dest, ["-ICC_Profile:all="])
            ok = ok and ok_strip
            warn = "\n".join(w for w in (warn, warn_strip) if w)
        # Report the loss whether it was the source's profile or the render's: a
        # profile dropped without a word is a colour claim silently discarded.
        if render_has_icc:
            icc_note = (
                "the render's ICC profile was dropped: its colour model changed during "
                "the encode, so the profile no longer describes the output pixels"
            )
        elif source_has_icc:
            icc_note = (
                "the source ICC profile was not carried: the render carries no profile "
                "of its own, so the source profile would have mislabelled the output"
            )

    sidecar = source.with_name(source.name + ".xmp")
    used = False
    if sidecar.exists():
        # A sidecar replaces list tags wholesale, so keep what the image had and
        # union it with the sidecar's values instead of letting one win.
        before_sub = exiftool_read_list(dest, "Subject")
        before_desc = exiftool_read(dest, ["Description"]).get("Description") or ""
        ok2, warn2 = exiftool_write(
            dest, ["-TagsFromFile", str(sidecar), "-all:all", "-unsafe"]
        )
        after_sub = exiftool_read_list(dest, "Subject")
        merged = merge_keywords(before_sub, after_sub)
        if merged and merged != after_sub:
            args = ["-Subject="] + [f"-Subject+={kw}" for kw in merged]
            ok_m, warn_m = exiftool_write(dest, args)
            ok = ok and ok_m
            warn = "\n".join(w for w in (warn, warn_m) if w)
        # A sidecar's Description replaces the embedded one; the embedded text is
        # the owner's words, so it is preserved ahead of the sidecar's.
        after_desc = exiftool_read(dest, ["Description"]).get("Description") or ""
        if before_desc.strip() and before_desc.strip() not in after_desc:
            ok_d, warn_d = exiftool_write(
                dest, ["-Description=" + append_text(before_desc, after_desc)]
            )
            ok = ok and ok_d
            warn = "\n".join(w for w in (warn, warn_d) if w)
        ok = ok and ok2
        warn = "\n".join(w for w in (warn, warn2) if w)
        used = True
    return ok, warn, used, icc_note


def correct_metadata(dest, out_size, note, keywords, appearance=True):
    """Pass 2: fix what the upscale made false, and record provenance."""
    # A source UserComment is the owner's words too, so it is appended to rather
    # than replaced -- the same rule as the caption.
    existing_comment = exiftool_read(dest, ["UserComment"]).get("UserComment")

    args = [
        # A stale thumbnail is the pre-restoration pixels; some DAMs show it
        # instead of the real image.
        "-ThumbnailImage=",
        "-PreviewImage=",
        # Numeric form is mandatory: -Orientation=1 is silently ignored.
        "-Orientation#=1",
        # The XMP copy carries its own orientation, which XMP-preferring readers
        # use. Leaving it stale rotates already-upright pixels.
        "-XMP-tiff:Orientation#=1",
        f"-ExifImageWidth={out_size[0]}",
        f"-ExifImageHeight={out_size[1]}",
        # XMP carries its own copy of the dimensions, and Lightroom/Photos
        # sources usually have it. Stale XMP size is the same lie as stale EXIF.
        f"-XMP-exif:ExifImageWidth={out_size[0]}",
        f"-XMP-exif:ExifImageHeight={out_size[1]}",
        f"-XMP-tiff:ImageWidth={out_size[0]}",
        f"-XMP-tiff:ImageHeight={out_size[1]}",
        f"-Software={PROG}",
        f"-CreatorTool={PROG}",
        f"-UserComment={append_text(existing_comment, note)}",
        "-XMP-xmpMM:History+="
        f"{{Action=saved,SoftwareAgent={PROG},"
        f"When={datetime.now().astimezone().isoformat(timespec='seconds')}}}",
    ]

    for kw in keywords or []:
        args.append(f"-Keywords+={kw}")
        args.append(f"-Subject+={kw}")

    if appearance:
        current = exiftool_read(dest, ["Caption-Abstract", "Description"])
        caption = append_text(current.get("Caption-Abstract"), note)
        # Description often starts empty even when a caption exists, because many
        # tools write only IPTC. Seed it from the caption so a reader that shows
        # only XMP still sees the owner's words.
        seed = current.get("Description") or current.get("Caption-Abstract")
        desc = append_text(seed, note)
        args.append(f"-Caption-Abstract={caption}")
        args.append(f"-XMP-dc:Description={desc}")

    return exiftool_write(dest, args)


def verify(source, dest, source_state, out_size, note, use_exiftool,
           grain="unknown", target_format=None):
    """Compare output against source and against reality. Returns (status, report)."""
    problems, shortfalls = [], []
    out = read_state(dest) if use_exiftool else read_state_pillow(dest)

    for tag in CORE_TAGS:
        had = source_state.get(tag)
        now = out.get(tag)
        if had and not now:
            problems.append(f"lost {tag} (source had '{had}')")

    if source_state.get("DateTimeOriginal") and out.get("DateTimeOriginal"):
        if out["DateTimeOriginal"] != source_state["DateTimeOriginal"]:
            problems.append(
                "DateTimeOriginal changed "
                f"('{source_state['DateTimeOriginal']}' -> '{out['DateTimeOriginal']}'); "
                "the capture date must never move"
            )

    orientation = out.get("Orientation#")
    if orientation not in (None, "1"):
        problems.append(f"Orientation is {out.get('Orientation')!r}, expected horizontal")
    if use_exiftool:
        xmp_orientation = exiftool_read(dest, ["XMP-tiff:Orientation"], numeric=True).get("XMP-tiff:Orientation")
        if xmp_orientation not in (None, "", "1"):
            problems.append(
                f"XMP orientation is {xmp_orientation!r}; XMP-preferring readers "
                "will show upright pixels rotated"
            )

    real = image_size(dest)
    if real is None:
        shortfalls.append("could not re-read output dimensions")
    else:
        if real != tuple(out_size):
            problems.append(f"output is {real} but the run believed {tuple(out_size)}")
        if use_exiftool:
            tagged_w = exiftool_read(dest, ["ExifImageWidth"]).get("ExifImageWidth")
        else:
            # The degraded path can still be checked for stale dimensions, which
            # is the one thing it is most likely to get wrong.
            try:
                from PIL import Image
                with Image.open(dest) as im:
                    tagged_w = str(im.getexif().get_ifd(0x8769).get(EXIF_PIXEL_X) or "")
            except Exception:
                tagged_w = ""
        if tagged_w and tagged_w.isdigit() and int(tagged_w) != real[0]:
            problems.append(
                f"ExifImageWidth says {tagged_w} but the file is {real[0]} pixels wide; "
                "half-copied metadata is worse than none"
            )
        if use_exiftool:
            for xmp_tag in ("XMP-exif:ExifImageWidth", "XMP-tiff:ImageWidth"):
                val = exiftool_read(dest, [xmp_tag], numeric=True).get(xmp_tag)
                if val and val.isdigit() and int(val) != real[0]:
                    problems.append(f"{xmp_tag} says {val} but the file is {real[0]} pixels wide")
        # Headers can be intact over truncated pixel data, so read the pixels.
        try:
            from PIL import Image
            with Image.open(dest) as chk:
                chk.load()
        except Exception as exc:
            problems.append(f"the output cannot be decoded: {exc}")
        if abs(real[0] / real[1] - out_size[0] / out_size[1]) > 0.005:
            problems.append("output aspect ratio drifted from the value recorded")

    if target_format and detected_format(dest) != {"jpeg": "JPEG", "png": "PNG",
                                                   "tiff": "TIFF"}[target_format]:
        problems.append(
            f"output container is {detected_format(dest) or 'unreadable'}, "
            f"expected {target_format}"
        )

    if use_exiftool:
        # Provenance is checked against the note that was actually written, so a
        # custom --note is held to the same standard as the default one.
        if not already_noted(out.get("UserComment"), note):
            problems.append("provenance note missing from UserComment")
        if not out.get("Software"):
            shortfalls.append("Software not written")
        if not exiftool_read(dest, ["HistorySoftwareAgent"]).get("HistorySoftwareAgent"):
            shortfalls.append("no XMP-xmpMM:History event was recorded")
        for stale in ("ThumbnailImage", "PreviewImage"):
            if exiftool_read(dest, [stale]).get(stale):
                problems.append(
                    f"the output still carries {stale}, which shows pre-restoration "
                    "pixels in some viewers"
                )
        src_comment = source_state.get("UserComment")
        if src_comment and str(src_comment).strip():
            now = out.get("UserComment") or ""
            if str(src_comment).strip() not in now:
                problems.append("the source's UserComment was replaced, not appended to")
        if grain == "reconstructed" and GRAIN_DISCLOSURE not in (out.get("UserComment") or ""):
            problems.append(
                "grain was reconstructed but the output does not disclose it; "
                "a reconstruction must never read as preservation"
            )

        # Existing captions must survive, because they are the owner's words.
        src_caption = source_state.get("Caption-Abstract")
        if src_caption and str(src_caption).strip():
            now = out.get("Caption-Abstract")
            if not now:
                problems.append("captions: Caption-Abstract went missing")
            elif str(src_caption).strip() not in now:
                problems.append("captions: original Caption-Abstract was replaced, not appended to")
        # Both vocabularies, because a macOS/Lightroom source may carry its words
        # in XMP only, and the sidecar path makes that common.
        for src_tag, out_tag, label in (
            ("Keywords", "Keywords", "keywords"),
            ("Subject", "Subject", "XMP subjects"),
        ):
            src_kw = parse_keywords(source_state.get(src_tag))
            if src_kw:
                now_kw = {k.lower() for k in parse_keywords(out.get(out_tag))}
                lost = [k for k in src_kw if k.lower() not in now_kw]
                if lost:
                    problems.append(f"{label} lost: {', '.join(lost)}")
        src_desc = source_state.get("Description")
        if src_desc and str(src_desc).strip():
            now_desc = out.get("Description") or ""
            if str(src_desc).strip() not in now_desc:
                problems.append("the source's XMP Description was replaced, not appended to")

    status = "fail" if problems else ("degraded" if shortfalls else "pass")
    return status, {"problems": problems, "shortfalls": shortfalls, "output": out}


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #

def append_manifest(project, entry):
    """Append atomically and under a lock, so concurrent runs cannot drop entries."""
    import fcntl

    path = project / "manifest.json"
    lock = project / ".manifest.lock"
    with open(lock, "w") as lockfh:
        fcntl.flock(lockfh, fcntl.LOCK_EX)
        if path.exists():
            with path.open() as fh:
                data = json.load(fh)
        else:
            data = {"schema": 1, "created": None, "assets": []}
        data.setdefault("assets", []).append(entry)
        data["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        fd, tmp = tempfile.mkstemp(dir=project, prefix=".manifest-", suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        fcntl.flock(lockfh, fcntl.LOCK_UN)
    return path


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("source", type=Path, help="Authoritative original (never modified)")
    p.add_argument("render", type=Path, help="Upscaled render to finalize")
    p.add_argument("--out-dir", type=Path, help="Destination directory (default: alongside source)")
    p.add_argument("--suffix", default="_upscale",
                   help="Filename suffix (default: _upscale; use _enhance for the higher-detail variant)")
    p.add_argument("--format", default="auto", choices=("auto", "jpeg", "png", "tiff"),
                   help="Output container (default: auto, follows the source)")
    p.add_argument("--quality", type=int, default=95, help="JPEG quality (default: 95)")
    p.add_argument("--project", type=Path, help="Project dir; append to its manifest.json")
    p.add_argument("--note", help="Replace the default provenance sentence")
    p.add_argument("--keyword", action="append", default=None,
                   help="Extra keyword to add (repeatable)")
    p.add_argument("--no-appearance-tags", action="store_true",
                   help="Do not touch Caption-Abstract or Description at all")
    p.add_argument("--no-keywords", action="store_true", help="Do not add any keywords")
    p.add_argument("--grain", default="unknown",
                   choices=("preserved", "recovered", "reconstructed", "none", "unknown"),
                   help="Film-grain decision, recorded in the manifest; "
                        "'reconstructed' is disclosed in the provenance sentence")
    p.add_argument("--master-name", help="Filename of the unedited master, recorded in the manifest")
    p.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    p.add_argument("--dry-run", action="store_true", help="Report the plan and exit")
    p.add_argument("--json", action="store_true", help="Emit the result as JSON")
    return p


def main():
    a = build_parser().parse_args()

    if not a.suffix:
        die("--suffix must not be empty; an empty suffix is how a run overwrites its own source")
    if not a.source.exists():
        die(f"Source not found: {a.source}")
    if not a.render.exists():
        die(f"Render not found: {a.render}")
    if a.source.resolve() == a.render.resolve():
        die("Source and render are the same file; the original is read-only evidence.")

    # A bad --project must not be discovered after the output has been published:
    # that turns a successful write into exit 1, which means "verification failed".
    if a.project:
        if not a.project.is_dir():
            die(f"--project {a.project} is not a directory")
        manifest = a.project / "manifest.json"
        if manifest.exists():
            try:
                json.loads(manifest.read_text())
            except (ValueError, OSError) as exc:
                die(f"--project manifest is unreadable: {exc}")

    use_exiftool = have("exiftool")
    target_format = choose_format(a.source, a.format)
    ext = FORMAT_EXT[target_format]

    src_size = image_size(a.source)
    if src_size is None:
        die(f"Could not read dimensions of {a.source}")
    src_state = expected_source_state(a.source, use_exiftool)
    # image_orientation() falls back to magick/sips, which is how a HEIC source
    # gets a real orientation on a host without exiftool.
    src_orientation = (src_state.get("Orientation#")
                       or image_orientation(a.source) or "1")
    src_display = transposed_size(src_size, src_orientation)

    render_raw = image_size(a.render)
    if render_raw is None:
        die(f"Could not read dimensions of {a.render}")
    render_orientation = image_orientation(a.render)
    render_display = transposed_size(render_raw, render_orientation)

    if abs(render_display[0] / render_display[1]
           - src_display[0] / src_display[1]) > 0.005:
        die(
            f"Aspect ratio mismatch: source displays {src_display[0]}x{src_display[1]}, "
            f"render displays {render_display[0]}x{render_display[1]}. That is a crop or "
            "a rotation, not an upscale. Refusing to relabel it as faithful."
        )

    scale = render_display[0] / src_display[0]
    if abs(render_display[1] / src_display[1] - scale) > 0.01:
        die(
            f"Anisotropic scale: {scale:.3f}x horizontally but "
            f"{render_display[1] / src_display[1]:.3f}x vertically."
        )
    if scale < 1.0:
        print(
            f"warning: the render is {scale:.3f}x, which is smaller than the source. "
            "That is a downscale, not an upscale. Proceeding because the numbers are "
            "what they are, but the output will be smaller than the original.",
            file=sys.stderr,
        )

    when = datetime.now().astimezone().strftime("%Y-%m-%d")
    note = provenance_note(scale, a.source.name, src_display, render_display,
                           when, a.note, a.grain)
    keywords = [] if a.no_keywords else merge_keywords(["upscaled", TOOL], a.keyword or [])

    out_dir = a.out_dir or (a.project / "output" if a.project else a.source.parent)
    out_path = None  # reserved below, after the dry-run can run without side effects

    # The original is evidence. Refuse before reserving, so this cannot turn into
    # a silent "-2" that writes next to a source we were about to clobber.
    would_be = out_dir / f"{a.source.stem}{a.suffix}{ext}"
    for candidate in (would_be,) + tuple(
        out_dir / f"{a.source.stem}{a.suffix}-{n}{ext}" for n in range(2, 5)
    ):
        if candidate.resolve() in (a.source.resolve(), a.render.resolve()):
            which = "source" if candidate.resolve() == a.source.resolve() else "render"
            die(f"Output path {candidate} is the {which} file itself. "
                "Choose a suffix or a different --out-dir.")

    plan = {
        "source": str(a.source),
        "render": str(a.render),
        "output": str(out_path),
        "format": target_format,
        "source_display_size": list(src_display),
        "render_display_size": list(render_display),
        "render_orientation": render_orientation,
        "scale": round(scale, 3),
        "suffix": a.suffix,
        "grain": a.grain,
        "note": note,
        "keywords": keywords,
        "exiftool": use_exiftool,
    }
    if a.dry_run:
        planned = out_dir / f"{a.source.stem}{a.suffix}{ext}"
        plan["output"] = str(planned)
        print(json.dumps(plan, indent=2) if a.json else "\n".join(f"{k}: {v}" for k, v in plan.items()))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path, reserved_new = reserve_destination(
        out_dir, a.source.stem, a.suffix, ext, a.force
    )
    plan["output"] = str(out_path)
    published = False
    workdir = None
    try:
        # Stage on the destination filesystem: os.replace cannot cross volumes,
        # and an external or archival drive is exactly where these go. Creation is
        # inside the try so a failure still releases the reservation.
        workdir = Path(tempfile.mkdtemp(dir=out_dir, prefix=".finalize-"))
        # Decode once. Metadata, ICC and the encode all read the same file, so a
        # HEIC render cannot lose its profile in one path and keep it in another.
        readable, decoder = readable_render(a.render, workdir, target_format)
        plan["decoded_by"] = decoder
        # Without exiftool there is no way to merge tags, so the source's EXIF is
        # embedded during the single save instead. One encode, never read-then-
        # rewrite the same path.
        embed, embed_notes = (None, []) if use_exiftool else source_embed(
            a.source, readable, render_display, target_format
        )
        # Without exiftool the render's own tags must never survive untouched:
        # an undated source would inherit the render's processing date.
        transcode = render_orientation not in ("1", "0") or not use_exiftool
        try:
            staged, transcoded, encode_note, colour_ok = encode(
                readable, target_format, workdir, a.quality, embed=embed,
                transcode=transcode,
            )
        except SystemExit:
            raise
        except Exception as exc:
            # Nothing has been published, so this is exit 2 by contract, not the
            # quarantined-output exit 1.
            die(f"could not write the output as {target_format}: {exc}")
        os.replace(staged, out_path)
        published = True

        write_problems = []
        copy_warn = ""
        icc_warning = None
        sidecar_used = False
        if use_exiftool:
            copy_ok, copy_warn, sidecar_used, icc_warning = copy_metadata(
                a.source, out_path, readable,
                colour_model_preserved=colour_ok, reencoded=transcoded,
            )
            if not copy_ok:
                write_problems.append("exiftool could not copy metadata from the source")
            correct_ok, correct_warn = correct_metadata(
                out_path, render_display, note, keywords,
                appearance=not a.no_appearance_tags,
            )
            if not correct_ok:
                write_problems.append("exiftool could not write the corrected tags")
            copy_warn = "\n".join(w for w in (copy_warn, correct_warn) if w)

        status, report = verify(a.source, out_path, src_state, render_display, note,
                                use_exiftool, a.grain, target_format)
        report["shortfalls"].extend(embed_notes)
        if icc_warning:
            report["shortfalls"].append(icc_warning)
        if status == "pass" and report["shortfalls"]:
            # A known preservation shortfall is a degraded result, not a pass.
            status = "degraded"
        if write_problems:
            report["problems"].extend(write_problems)
            status = "fail"

        if not use_exiftool:
            report["shortfalls"].append(
                "exiftool not installed: only the raw EXIF blob (orientation normalised) and "
                "ICC profile were carried; GPS/IPTC/XMP fields and provenance were not written"
            )
            if status == "pass":
                status = "degraded"
        if copy_warn:
            report["exiftool_warnings"] = copy_warn.splitlines()

        if status == "fail":
            failed = pick_quarantine(out_path)
            shutil.move(str(out_path), failed)
            out_path = failed

        entry = {
            "source": str(a.source),
            "source_size": list(src_display),
            "render": str(a.render),
            "decoded_by": decoder,
            "render_orientation": render_orientation,
            "output": str(out_path),
            "format": target_format,
            "transcoded": transcoded,
            "encode_detail": encode_note,
            "scale": round(scale, 3),
            "suffix": a.suffix,
            "sidecar_used": sidecar_used,
            "operations": [
                "metadata:copied" if use_exiftool else "metadata:degraded",
                f"provenance:{'written' if use_exiftool else 'not-written'}",
                f"grain:{a.grain}",
            ],
            "keywords": keywords,
            "appearance_tags_touched": not a.no_appearance_tags,
            "grain": a.grain,
            # Computed from the file, not the plan: a degraded run writes no
            # provenance, and the flag must not claim a disclosure it never made.
            "grain_disclosed": bool(
                use_exiftool and GRAIN_DISCLOSURE in (
                    exiftool_read(out_path, ["UserComment"]).get("UserComment") or ""
                )
            ),
            "master_filename": a.master_name,
            "verification": status,
            "verification_detail": report,
            "finalized_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        manifest_error = None
        if a.project:
            try:
                append_manifest(a.project, entry)
            except Exception as exc:
                # The output is published and verified. Bookkeeping failing is not
                # a verification failure, and exit 1 would tell a caller to discard
                # a good file.
                manifest_error = str(exc)
                entry["manifest_error"] = manifest_error

        if a.json:
            print(json.dumps(entry, indent=2, default=str))
        else:
            print(f"output: {out_path}")
            print(f"scale:  {scale:.3f}x  ({src_display[0]}x{src_display[1]} -> "
                  f"{render_display[0]}x{render_display[1]})")
            print(f"format: {target_format} ({encode_note})")
            print(f"grain:  {a.grain}")
            print(f"verify: {status.upper()}")
            for p in report["problems"]:
                print(f"  FAIL: {p}")
            for s in report["shortfalls"]:
                print(f"  DEGRADED: {s}")
            for w in report.get("exiftool_warnings", []):
                print(f"  exiftool: {w}")
            if manifest_error:
                print(f"  WARNING: verified, but the manifest was not updated: {manifest_error}")
            if status == "fail":
                print("\nDo not deliver this file and do not import it into Photos.")
            elif status == "degraded":
                print("\nThe following could not be preserved. Say so when delivering.")

        return 1 if status == "fail" else 0
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
        if not published and reserved_new:
            # An exit before publication must not leave a zero-byte file wearing a
            # delivery name, or the next run is pushed to "-2" for no reason.
            out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
