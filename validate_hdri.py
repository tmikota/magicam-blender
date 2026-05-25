"""Convert the CGL-HDRI yaml to JSON and validate the HDRI library model.

Run with a Python that has PyYAML + pydantic (e.g. the alchemy venv).
"""

import sys
from pathlib import Path

from magicam.hdri import load_hdri_library, yaml_to_json

YAML = Path(r"E:\Alchemy\cgl\config\CGL-HDRI\hdri.yaml")


def main() -> int:
    if not YAML.exists():
        print(f"SKIP (not found): {YAML}")
        return 0

    json_path = yaml_to_json(YAML)  # writes hdri.json beside the yaml
    print(f"wrote {json_path}")

    lib = load_hdri_library(json_path)
    print(f"entries: {len(lib.entries)}\n")

    for e in lib.entries[:8]:
        img_ok = bool(e.image_path) and Path(e.image_path).exists()
        thumb_ok = bool(e.thumb_path) and Path(e.thumb_path).exists()
        print(f"  {e.name:32} yrot={e.yrot:>6}  "
              f"img={'ok' if img_ok else 'MISSING'}  "
              f"thumb={'ok' if thumb_ok else 'MISSING'}")

    missing_img = sum(not (e.image_path and Path(e.image_path).exists()) for e in lib.entries)
    missing_thumb = sum(not (e.thumb_path and Path(e.thumb_path).exists()) for e in lib.entries)
    print(f"\nmissing images: {missing_img}/{len(lib.entries)}   "
          f"missing thumbs: {missing_thumb}/{len(lib.entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
