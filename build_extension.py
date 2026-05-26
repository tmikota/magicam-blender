"""Build the MagiCam Blender Extension: fetch dependency wheels + write the manifest.

Bundles pydantic (+ pydantic_core and its pure deps) wheels for Windows/macOS/Linux
across Blender's likely Python versions, so the extension installs on a vanilla
Blender with no pip step. Then run Blender's extension builder to produce the zip:

    python build_extension.py                # fetch wheels + write manifest
    python build_extension.py --blender PATH  # ...and run `blender --command extension build`

Run with any Python that has pip (e.g. the alchemy venv).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent
PKG = REPO / "magicam"
WHEELS = PKG / "wheels"
MANIFEST = PKG / "blender_manifest.toml"

PYDANTIC_SPEC = "pydantic>=2,<3"
PY_TAGS = ["3.11", "3.12", "3.13"]  # Blender 4.2 -> 5.x
# Blender platform id -> pip --platform tag(s)
PLATFORMS = {
    "windows-x64": ["win_amd64"],
    "macos-arm64": ["macosx_11_0_arm64"],
    "macos-x64": ["macosx_10_12_x86_64"],
    "linux-x64": ["manylinux2014_x86_64", "manylinux_2_17_x86_64"],
}

MANIFEST_TEMPLATE = '''\
schema_version = "1.0.0"

id = "magicam"
version = "{version}"
name = "MagiCam"
tagline = "Multiplane cameras, storyboard timelines and quick lighting"
maintainer = "Tom Mikota"
type = "add-on"

blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
tags = ["Camera", "Lighting", "Pipeline"]

platforms = ["windows-x64", "macos-arm64", "macos-x64", "linux-x64"]

wheels = [
{wheels}
]

[permissions]
files = "Import storyboards, HDRIs and TVPaint exports from disk"

[build]
paths_exclude_pattern = [
    "__pycache__/",
    "*.pyc",
    "/.git/",
    "*.zip",
]
'''


def _version() -> str:
    ns: dict = {}
    exec((PKG / "__init__.py").read_text(encoding="utf-8").split("def register")[0], ns)
    return ns.get("__version__", "0.1.0")


def fetch_wheels() -> None:
    WHEELS.mkdir(parents=True, exist_ok=True)
    for whl in WHEELS.glob("*.whl"):
        whl.unlink()
    for py_tag in PY_TAGS:
        for tags in PLATFORMS.values():
            cmd = [
                sys.executable, "-m", "pip", "download", PYDANTIC_SPEC,
                "--only-binary=:all:", "--python-version", py_tag,
                "--dest", str(WHEELS),
            ]
            for tag in tags:
                cmd += ["--platform", tag]
            print("+", " ".join(cmd))
            subprocess.run(cmd, check=True)


def write_manifest() -> None:
    names = sorted(p.name for p in WHEELS.glob("*.whl"))
    wheels = "\n".join(f'    "./wheels/{n}",' for n in names)
    MANIFEST.write_text(
        MANIFEST_TEMPLATE.format(version=_version(), wheels=wheels), encoding="utf-8"
    )
    print(f"wrote {MANIFEST} with {len(names)} wheels")


def build(blender: str) -> None:
    out_dir = REPO / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)  # Blender won't create it itself
    cmd = [blender, "--command", "extension", "build",
           "--source-dir", str(PKG), "--output-dir", str(out_dir)]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", help="Path to the Blender executable to build the zip")
    ap.add_argument("--skip-wheels", action="store_true", help="Reuse existing wheels/")
    args = ap.parse_args()

    if not args.skip_wheels:
        fetch_wheels()
    write_manifest()

    if args.blender:
        build(args.blender)
    else:
        print(
            "\nManifest + wheels ready. Build the zip with:\n"
            f'    blender --command extension build --source-dir "{PKG}" '
            f'--output-dir "{REPO / "dist"}"\n'
            "or pass --blender PATH to this script."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
