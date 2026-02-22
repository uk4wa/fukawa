#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_PRUNE_DIRS = {".git", "__pycache__", ".venv", "alembic"}


def iter_children(path: Path) -> list[Path]:
    try:
        children = list(path.iterdir())
    except PermissionError:
        return []
    # dirs first, then files; case-insensitive for Windows
    children.sort(key=lambda p: (p.is_file(), p.name.lower()))
    return children


def render_tree(
    root: Path,
    *,
    max_depth: int | None,
    dirs_only: bool,
    prune_dir_names: set[str],
) -> list[str]:
    lines: list[str] = []
    root = root.resolve()

    def walk(dir_path: Path, prefix: str, depth: int) -> None:
        if max_depth is not None and depth > max_depth:
            return

        children = [
            c for c in iter_children(dir_path)
            if (not dirs_only or c.is_dir())
        ]

        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            branch = "└── " if is_last else "├── "
            lines.append(f"{prefix}{branch}{child.name}")

            # Если это prune-папка — показываем, но не раскрываем
            if child.is_dir() and child.name in prune_dir_names:
                continue

            if child.is_dir():
                if max_depth is None or depth < max_depth:
                    ext = "    " if is_last else "│   "
                    walk(child, prefix + ext, depth + 1)

    lines.append(root.name)
    if root.is_dir():
        walk(root, prefix="", depth=1)
    return lines


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Pretty project tree printer (shows pruned dirs but does not expand them)."
    )
    ap.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    ap.add_argument("--max-depth", type=int, default=None, help="Limit recursion depth")
    ap.add_argument("--dirs-only", action="store_true", help="Show directories only")
    ap.add_argument(
        "--prune",
        action="append",
        default=[],
        help="Dir name to show but not expand (repeatable), e.g. --prune .venv",
    )
    return ap.parse_args()


def main() -> None:
    ns = parse_args()
    root = Path(ns.path)
    prune_dir_names = set(DEFAULT_PRUNE_DIRS) | set(ns.prune)

    lines = render_tree(
        root,
        max_depth=ns.max_depth,
        dirs_only=ns.dirs_only,
        prune_dir_names=prune_dir_names,
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()