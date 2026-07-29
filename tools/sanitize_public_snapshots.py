#!/usr/bin/env python3
"""Remove internal-network metadata from preserved public HTML snapshots."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SNAPSHOT_PATHS = (
    "data/raw/migration/snap_zerkalo_beroc_100-500k.html",
    "data/raw/migration/snap_zerkalo_350k_minsk.html",
    "data/raw/border/minskdialogue_border_overview.html",
)

PRIVATE_IPV4 = (
    r"(?:10(?:\.\d{1,3}){3}|172\.(?:1[6-9]|2\d|3[0-1])"
    r"(?:\.\d{1,3}){2}|192\.168(?:\.\d{1,3}){2})"
)
PRIVATE_COMMENT = re.compile(
    rf"<!--(?:(?!-->).)*?{PRIVATE_IPV4}(?:(?!-->).)*?-->",
    re.DOTALL,
)
GOOGLE_MAPS_KEY = re.compile(
    r"(https://maps\.googleapis\.com/maps/api/js\?[^\"']*?key=)"
    r"(?!REDACTED(?:[&\"']|$))[^&\"']+",
    re.IGNORECASE,
)


def sensitive_fragment_count(content: str) -> int:
    """Return comments with private addresses and Maps URL key values."""
    return len(PRIVATE_COMMENT.findall(content)) + len(GOOGLE_MAPS_KEY.findall(content))


def sanitize_snapshot(path: Path) -> int:
    """Remove private-address comments and redact Maps URL key values."""
    content = path.read_bytes().decode("utf-8")
    sanitized, comment_count = PRIVATE_COMMENT.subn("", content)
    sanitized, maps_key_count = GOOGLE_MAPS_KEY.subn(r"\1REDACTED", sanitized)
    count = comment_count + maps_key_count
    if count:
        path.write_bytes(sanitized.encode("utf-8"))
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when a preserved snapshot still contains an RFC1918 comment",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    remaining = 0

    for relative_path in SNAPSHOT_PATHS:
        path = repository_root / relative_path
        content = path.read_bytes().decode("utf-8")
        count = sensitive_fragment_count(content)

        if args.check:
            remaining += count
            print(f"{relative_path}: {count} sensitive fragment(s)")
            continue

        removed = sanitize_snapshot(path)
        print(f"{relative_path}: removed {removed} sensitive fragment(s)")

    return 1 if remaining else 0


if __name__ == "__main__":
    raise SystemExit(main())
