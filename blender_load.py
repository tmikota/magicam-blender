"""Load the MagiCam add-on inside Blender.

In Blender: Scripting workspace -> Text -> Open -> pick this file -> Run Script
(the ▶ button). Re-run it after editing any magicam code; it reloads everything
and re-registers, so you don't need to restart Blender.
"""

import importlib
import os
import sys

# Repo root (folder containing the 'magicam' package).
# In Blender's Text editor, __file__ is the datablock name (e.g. "blender_load.py"),
# not a real path — so only trust it if it actually points at the repo.
REPO_DEFAULT = r"C:\Users\tmiko\PycharmProjects\magicam-blender"


def _is_repo(path):
    return bool(path) and os.path.isdir(os.path.join(path, "magicam"))


REPO = None
if "__file__" in globals():
    candidate = os.path.dirname(os.path.abspath(__file__))
    if _is_repo(candidate):
        REPO = candidate
if not _is_repo(REPO):
    REPO = REPO_DEFAULT

if not _is_repo(REPO):
    raise SystemExit(
        f"Could not find the 'magicam' package. Edit REPO_DEFAULT in this script "
        f"to your repo path (currently {REPO_DEFAULT!r})."
    )

if REPO not in sys.path:
    sys.path.insert(0, REPO)

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


# in blender:
# exec(open(r"C:\Users\tmiko\PycharmProjects\magicam-blender\blender_load.py").read())