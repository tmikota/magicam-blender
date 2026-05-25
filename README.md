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

The **MagiCam** panel has an **Import TVPaint Camera** button (pick a
`clip_export.json`; leave the shot name blank to use the clip name).

You can also drive it headlessly:

```python
from magicam.blender import build
build.import_multicam_rig(r"...\clip_export.json", shot_name="")  # blank = clip name
```

### Camera Caddy (native bpy panel)

`magicam/blender/caddy_blender.py` provides the **Camera Caddy** panel in the
MagiCam sidebar tab — a fully native (no PySide) Blender UI:

- a **Camera** dropdown (one shot == one camera), with **Start / End / View
  Range** buttons right below it,
- a **Lens** dropdown,
- the camera's **image planes**, each with a visibility toggle; clicking a plane
  selects its rig control bone,
- per-plane **Opacity** and **Create Static** for the active plane.

Selection state lives in a Scene `PropertyGroup`, so it survives redraws, undo,
and save/load. No PySide6 anywhere in the package.

Deferred for now: the thumbnail strip (would use `bpy.utils.previews`),
move/rotate nudges, and character-snap.

### Known limitations

- **Verify in Blender.** The `magicam.blender` modules import `bpy`; they pass a
  syntax check outside Blender but behavior must be confirmed in Blender (target:
  Blender 5.1 / EEVEE Next).
- **10 planes.** The bundled rig provides `image_plane_01..10`; layers beyond the
  10th are skipped with a console note.
- **Pipeline seam off by default.** Alchemy hooks (task structure, etc.) only run
  when *Enable Alchemy pipeline steps* is ticked in the add-on preferences and the
  `alc` package is importable.

