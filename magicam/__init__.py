"""magicam — TVPaint clip tooling and Blender-native multiplane camera / lighting.

This package doubles as the Blender Extension entry point. When Blender installs
an extension it imports the package under a namespaced name
(``bl_ext.<repo>.magicam``); the alias below republishes it as ``magicam`` so the
absolute ``from magicam... import`` statements throughout the code resolve both
inside Blender and as a plain library.
"""

import sys as _sys

# Alias the (possibly namespaced) extension package as plain "magicam".
if __name__ != "magicam":
    _sys.modules.setdefault("magicam", _sys.modules[__name__])

__version__ = "0.1.0"


def register():
    from magicam.blender import register as _register

    _register()


def unregister():
    from magicam.blender import unregister as _unregister

    _unregister()
