"""Convert an HDRI ``hdri.yaml`` to JSON so the Blender plugin needs no PyYAML.

Run this where PyYAML is available (the pipeline / a venv), not inside the
plugin's runtime. The resulting JSON sits beside the yaml and is what
``load_hdri_library`` reads.
"""

from __future__ import annotations

import json
from pathlib import Path


def yaml_to_json(yaml_path, json_path=None) -> Path:
    """Write a JSON copy of an HDRI yaml library. Returns the JSON path."""
    import yaml  # dev/pipeline-time dependency only

    yaml_path = Path(yaml_path)
    json_path = Path(json_path) if json_path else yaml_path.with_suffix(".json")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return json_path
