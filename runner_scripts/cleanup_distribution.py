#!/usr/bin/env python3
"""Remove unused packages from a PyInstaller distribution directory.

Reads the 'pyinstaller.blacklist' section of conandata.yml (the Cura repo's source-of-truth
for excluded packages) and removes every matching file or directory tree from the given
distribution path.
https://github.com/Ultimaker/Cura/blob/8d88d81c2db7bae574a1d55b81d8e0774fdb1486/conandata.yml#L133

Each entry in 'pyinstaller.blacklist' has:
  patterns  — list of substrings that must ALL appear in the lowercased,
              forward-slash-normalised file/directory path to trigger removal.
  oses      — (optional) list of OS names; if present, only remove on those platforms.
              Recognised values: Windows, Linux, Macos.

Usage:
  python cleanup_distribution.py <dist_dir> [--conandata PATH] [--os Windows|Linux|Macos]

Examples:
  # Linux / macOS AppImage
  python cleanup_distribution.py dist/UltiMaker-Cura --conandata _cura_sources/conandata.yml

  # macOS .app bundle (path found dynamically in the workflow)
  python cleanup_distribution.py "dist/UltiMaker Cura.app" --conandata _cura_sources/conandata.yml --os Macos

  # Windows
  python cleanup_distribution.py dist\\UltiMaker-Cura --conandata _cura_sources\\conandata.yml --os Windows
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required (pip install pyyaml).") from exc


def path_matches(path: Path, entry) -> bool:
    """Return True if every pattern string appears in the normalised lowercase path.
    Entry is either a plain list (legacy) or a dict with a 'patterns' key.
    """
    patterns = entry if isinstance(entry, list) else entry.get("patterns", [])
    normalised = path.as_posix().lower()
    return all(part in normalised for part in patterns)


def cleanup(dist_dir: Path, entries: list, current_os: str) -> int:
    removed = 0
    for root, dirs, files in os.walk(dist_dir, topdown=True):
        root_path = Path(root)

        # Check directories first — prune the walk so we don't recurse into removed trees.
        for d in dirs[:]:
            target = root_path / d
            for entry in entries:
                oses = entry.get("oses") if isinstance(entry, dict) else None
                if oses and current_os not in oses:
                    continue
                if path_matches(target, entry):
                    print(f"  Removing dir:  {target.relative_to(dist_dir)}")
                    shutil.rmtree(target)
                    dirs.remove(d)
                    removed += 1
                    break

        # Check individual files.
        for f in files:
            target = root_path / f
            for entry in entries:
                oses = entry.get("oses") if isinstance(entry, dict) else None
                if oses and current_os not in oses:
                    continue
                if path_matches(target, entry):
                    print(f"  Removing file: {target.relative_to(dist_dir)}")
                    target.unlink(missing_ok=True)
                    removed += 1
                    break

    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove blacklisted packages from a built distribution directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "dist_dir",
        help="Root of the distribution to clean (e.g. dist/UltiMaker-Cura or the .app bundle)",
    )
    parser.add_argument(
        "--conandata",
        default="_cura_sources/conandata.yml",
        help="Path to conandata.yml (default: _cura_sources/conandata.yml)",
    )
    parser.add_argument(
        "--os",
        dest="os_name",
        default=None,
        help="Override OS name: Windows, Linux, or Macos (defaults to current platform)",
    )
    args = parser.parse_args()

    current_os = args.os_name or {
        "linux": "Linux",
        "darwin": "Macos",
        "win32": "Windows",
    }.get(sys.platform, sys.platform)

    conandata_path = Path(args.conandata)
    if not conandata_path.exists():
        print(f"ERROR: conandata.yml not found at {conandata_path}", file=sys.stderr)
        sys.exit(1)

    with open(conandata_path) as fh:
        conandata = yaml.safe_load(fh)

    entries = conandata.get("pyinstaller", {}).get("blacklist", [])
    if not entries:
        print("No 'pyinstaller.blacklist' entries found in conandata.yml — nothing to do.")
        return

    dist_dir = Path(args.dist_dir)
    if not dist_dir.exists():
        print(f"ERROR: Distribution directory not found: {dist_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Cleaning {dist_dir} for {current_os} ...")
    removed = cleanup(dist_dir, entries, current_os)
    print(f"Done — removed {removed} item(s).")


if __name__ == "__main__":
    main()
