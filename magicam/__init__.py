"""magicam — TVPaint clip tooling and Blender-native multiplane camera / lighting.

This package is the Blender Extension entry point: Blender calls ``register()`` /
``unregister()`` here. Intra-package imports are relative so the code resolves
whether Blender loads it namespaced (``bl_ext.<repo>.magicam``) or it's imported
as a plain ``magicam`` library.
"""

__version__ = "0.1.0"


def register():
    from .blender import register as _register

    _register()


def unregister():
    from .blender import unregister as _unregister

    _unregister()
