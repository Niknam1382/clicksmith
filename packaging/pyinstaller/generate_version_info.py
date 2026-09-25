"""Write version_info.txt (the Win32 VERSIONINFO resource) from the package version.

PyInstaller's `version=` argument needs a literal file, and its four-number FILEVERSION cannot
be derived from an arbitrary semver string inside the .spec file itself, so it is generated here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from clicksmith import APP_NAME, __version__  # noqa: E402

TEMPLATE = """\
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v[0]}, {v[1]}, {v[2]}, 0),
    prodvers=({v[0]}, {v[1]}, {v[2]}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          "040904B0",
          [
            StringStruct("CompanyName", "Clicksmith contributors"),
            StringStruct("FileDescription", "{app}: auto clicker, macro recorder and scheduler"),
            StringStruct("FileVersion", "{version}"),
            StringStruct("InternalName", "clicksmith"),
            StringStruct("LegalCopyright", "Released under the MIT License."),
            StringStruct("OriginalFilename", "Clicksmith.exe"),
            StringStruct("ProductName", "{app}"),
            StringStruct("ProductVersion", "{version}"),
          ],
        )
      ],
    ),
    VarFileInfo([VarStruct("Translation", [1033, 1200])]),
  ],
)
"""


def main() -> None:
    numbers = re.findall(r"\d+", __version__)[:3]
    while len(numbers) < 3:
        numbers.append("0")
    text = TEMPLATE.format(v=[int(n) for n in numbers], app=APP_NAME, version=__version__)
    out = Path(__file__).with_name("version_info.txt")
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
