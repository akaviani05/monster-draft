#!/usr/bin/env python3
"""Copy a stopped contest's entire private data directory into a new backup directory."""
import argparse
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def backup(data, output):
    data, output = Path(data).resolve(), Path(output).resolve()
    if not (data / "arena.sqlite3").is_file():
        raise ValueError("Source must be an initialized arena data directory")
    if output == data or data in output.parents:
        raise ValueError("Backup destination must be outside the data directory")
    # Reserve a new private directory, then retain the complete offline snapshot.
    output.mkdir(mode=0o700)
    for entry in data.iterdir():
        destination = output / entry.name
        if entry.is_dir() and not entry.is_symlink():
            shutil.copytree(entry, destination, symlinks=True)
        else:
            shutil.copy2(entry, destination, follow_symlinks=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("ARENA_DATA", ROOT / "var")))
    parser.add_argument("--output", type=Path, required=True, help="New private backup directory")
    parser.add_argument("--stopped", action="store_true", required=True,
                        help="Confirm that both website and worker have been stopped")
    args = parser.parse_args()
    try:
        backup(args.data, args.output)
    except (ValueError, OSError, shutil.Error) as exc:
        parser.error(str(exc))
    print("Complete private data backup created. Keep credential exports separately backed up too.")


if __name__ == "__main__":
    main()
