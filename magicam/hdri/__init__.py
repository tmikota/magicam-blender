"""HDRI library: a JSON-backed model of an HDRI set, plus a yaml->json converter.

The runtime model reads JSON only (stdlib), so the Blender plugin needs no
PyYAML. Convert a source hdri.yaml once with ``yaml_to_json`` (run where PyYAML
is available, e.g. the pipeline/venv).
"""

from magicam.hdri.convert import yaml_to_json
from magicam.hdri.models import HdriEntry, HdriLibrary, load_hdri_library

__all__ = ["HdriEntry", "HdriLibrary", "load_hdri_library", "yaml_to_json"]
