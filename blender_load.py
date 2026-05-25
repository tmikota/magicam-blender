"""Load the MagiCam add-on inside Blender.

In Blender: Scripting workspace -> Text -> Open -> pick this file -> Run Script
(the ▶ button). Re-run it after editing any magicam code; it reloads everything
and re-registers, so you don't need to restart Blender.
"""

import importlib
import os
import sys

# Repo root (folder containing the 'magicam' package).
if "__file__" in globals():
    REPO = os.path.dirname(os.path.abspath(__file__))
else:
    REPO = r"C:\Users\tmiko\PycharmProjects\magicam-blender"

if REPO not in sys.path:
    sys.path.append(REPO)

# Check the one hard dependency up front with a clear message.
try:
    import pydantic  # noqa: F401
except ImportError:
    raise SystemExit(
        "pydantic is not installed in Blender's Python.\n"
        "Install it once, then re-run this script:\n"
        "    import sys, subprocess\n"
        "    subprocess.check_call([sys.executable, '-m', 'ensurepip'])\n"
        "    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pydantic'])"
    )

# Unregister a previous load, if any.
if "magicam.blender" in sys.modules:
    try:
        sys.modules["magicam.blender"].unregister()
    except Exception as exc:
        print(f"(previous unregister skipped: {exc})")

# Drop all magicam modules so code edits take effect on re-run.
for _name in [m for m in sys.modules if m == "magicam" or m.startswith("magicam.")]:
    del sys.modules[_name]

import magicam.blender as mb

importlib.reload(mb)
mb.register()
print("MagiCam registered. Press N in the 3D viewport and open the 'MagiCam' tab.")
