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

