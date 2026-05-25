# magicam-blender

Pydantic models and tooling for TVPaint clip exports, intended to run natively
inside Blender (no PySide dependency).

## TVPaint models

`magicam.tvpaint` reads TVPaint `clip_export.json` files. One model set covers
both the TVPaint 11 and TVPaint 12 export schemas.

```python
from magicam.tvpaint import load_clip

export = load_clip(r"C:\Users\tmiko\_export\tvpaint_12\clip_export.json")
print(export.clip.name)
for layer in export.layers:
    print(layer.name, layer.start, layer.end, len(layer.link))
```

### Native model accessors

The models carry the query logic directly:

```python
clip = export.clip
clip.layer_names(exclude=["ref"])     # layer names, dropping any containing a token
clip.layer("Anim_19")                 # find a layer by name
clip.frame_range_from_layers()        # (min start, max end) -> (0, 90)
clip.shot_frame_range()               # mark range "0-90" (v12) or "0-0" (unmarked v11)

layer = clip.layer("Anim_19")
layer.first_image_file()              # "Anim_19.0000.png"
layer.image_paths(export.source_dir)  # absolute Paths for every link
layer.frame_range_string()            # 1-based, e.g. "1,46-56"
```

### Legacy-compatible query functions

`magicam.tvpaint.query` mirrors the old `cgl.plugins.tvpaint.query` names for an
easy port. Each accepts a file path, a parsed dict, or a loaded `TVPaintExport`:

```python
from magicam.tvpaint import query

query.layer_names(path_or_dict_or_model)
query.frame_range_from_layers(path_or_dict_or_model)
query.layer_images(path, "Anim_19")   # absolute image paths
```

## Blender add-on (`magicam.blender`)

A PySide-free Blender add-on that builds a multiplane camera rig from a TVPaint
export. The camera rig template is bundled in `magicam/blender/resources/`.

### Loading it

The repo must be on Blender's `sys.path`. From Blender's Python console or a
Text-editor script:

```python
import sys; sys.path.append(r"C:\Users\tmiko\PycharmProjects\magicam-blender")
import magicam.blender as mb
mb.register()   # adds the "MagiCam" tab to the 3D viewport sidebar (N)
```

The panel has an **Import TVPaint Camera** button (pick a `clip_export.json`,
set a shot name) and lists each rig's image planes with visibility toggles.

You can also drive it headlessly:

```python
from magicam.blender import build
build.import_multicam_rig(r"...\clip_export.json", shot_name="SEQ_0010")
```

### Camera Caddy (PySide6)

The original PySide6 "Camera Caddy" is ported in `magicam/blender/caddy.py` and
wired to the new architecture. It's the practical way to drive a rig (shots /
cameras / planes, visibility, lens, frame jumps, create-static, character-snap).
Open it from the **MagiCam** panel ("Open Camera Caddy") or:

```python
from magicam.blender import caddy
caddy.launch_caddy()            # manage rigs in the scene
caddy.launch_camera_importer()  # the import dialog
```

This still requires **PySide6 in Blender's Python** (a native bpy rebuild is
deferred). If PySide6 is missing the rest of the add-on still loads — only the
Caddy buttons report it. If the Caddy window is unresponsive, that's the usual
Qt-event-loop-in-Blender issue and we can add a modal event pump.

### Camera Caddy (native bpy)

`magicam/blender/caddy_blender.py` is a PySide-free alternative: a **Camera
Caddy (native)** panel in the MagiCam sidebar tab (collapsed by default). It
covers the core set — shots/cameras/planes lists, per-plane visibility toggles,
lens, frame start/end jump + view-range, per-plane opacity, and create-static —
with selection state stored in a Scene `PropertyGroup`. The PySide `caddy.py` is
left in place so you can compare the two. Deferred in the native panel for now:
the thumbnail strip, move/rotate, and character-snap.

### Scope and known limitations of this first cut

- **Untested outside Blender.** The `magicam.blender` modules import `bpy`; they
  pass a syntax check here but must be verified inside Blender.
- **Import + plane-list panel only.** Character-snapping, per-plane
  opacity/move/rotate, lens control, "create static", and the thumbnail strip
  from the old Qt "Camera Caddy" are not ported yet.
- **10 planes.** The bundled rig provides `image_plane_01..10`; layers beyond the
  10th are skipped with a console note.
- **Pipeline seam off by default.** Alchemy hooks (task structure, etc.) only run
  when *Enable Alchemy pipeline steps* is ticked in the add-on preferences and the
  `alc` package is importable.

