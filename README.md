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
