#!/usr/bin/env python3
"""Check release identity, archive contents and checksums without using AWS.

Run with Python 3.11+ from a source checkout. Errors identify paths/rule names,
never matching secret values. Gitleaks separately scans the full Git history.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
ROOT_FILES = {
    "AGENTS.md", "LICENSE", "MANIFEST.in", "PKG-INFO", "README.md",
    "pyproject.toml", "setup.cfg", "uv.lock", ".python-version",
}
DIST_INFO_FILES = {
    "METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt",
    "licenses/LICENSE",
}
EGG_INFO_FILES = {
    "PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt",
    "requires.txt", "top_level.txt",
}
CONTENT_RULES = {
    "AWS access-key identifier": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "private key": re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "personal Unix path": re.compile(rb"/(?:home|Users)/[A-Za-z0-9][^\s\"'<>]*"),
    "personal Windows path": re.compile(rb"(?i)[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9][^\s\"'<>]*"),
}


def fail(message: str) -> None:
    raise ValueError(message)


def checked_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
        fail(f"Unsafe archive path: {name!r}")
    if path.as_posix() != name.rstrip("/"):
        fail(f"Noncanonical archive path: {name!r}")
    return path


def package_files() -> set[str]:
    files = {p.relative_to(ROOT).as_posix() for p in (ROOT / "odin_mcp").glob("*.py")}
    for pattern in ("*.md", "*.json"):
        files.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "odin_mcp/research").glob(pattern))
    if "odin_mcp/server.py" not in files or "odin_mcp/research/catalog.json" not in files:
        fail("Expected package source and bundled research are missing")
    return files


def check_content(path: str, data: bytes) -> None:
    if b"\x00" in data:
        fail(f"Unexpected binary content: {path}")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        fail(f"Non-UTF-8 public source: {path}")
    for rule, pattern in CONTENT_RULES.items():
        if pattern.search(data):
            fail(f"Sensitive-content rule '{rule}' matched {path}; inspect locally")


def check_metadata(path: str, data: bytes, version: str) -> None:
    metadata = BytesParser().parsebytes(data)
    if metadata["Name"] != "odin-mcp" or metadata["Version"] != version:
        fail(f"Package identity/version mismatch in {path}")


def check_package_source(path: str, data: bytes) -> None:
    if (ROOT / path).read_bytes() != data:
        fail(f"Packaged source differs from checkout: {path}")


def check_wheel(archive: Path, version: str, expected: set[str]) -> None:
    metadata_root = f"odin_mcp-{version}.dist-info/"
    seen: set[str] = set()
    total = 0
    with zipfile.ZipFile(archive) as wheel:
        for item in wheel.infolist():
            path = checked_path(item.filename).as_posix()
            if item.is_dir():
                continue
            if path in seen or (item.external_attr >> 16) & 0o170000 == 0o120000:
                fail(f"Duplicate or symlink wheel member: {path}")
            seen.add(path)
            total += item.file_size
            if total > MAX_ARCHIVE_BYTES:
                fail("Wheel exceeds the public package size limit")
            metadata_file = path.removeprefix(metadata_root)
            if path not in expected and not (path.startswith(metadata_root) and metadata_file in DIST_INFO_FILES):
                fail(f"Unapproved wheel member: {path}")
            data = wheel.read(item)
            check_content(path, data)
            if path in expected:
                check_package_source(path, data)
            if path == metadata_root + "METADATA":
                check_metadata(path, data, version)
            if path == metadata_root + "licenses/LICENSE" and data != (ROOT / "LICENSE").read_bytes():
                fail("Wheel license differs from the reviewed source license")
    required = expected | {metadata_root + name for name in ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "licenses/LICENSE")}
    if not required <= seen:
        fail(f"Wheel is missing required files: {sorted(required - seen)}")


def allowed_sdist(path: PurePosixPath, expected: set[str]) -> bool:
    name = path.as_posix()
    if name in ROOT_FILES or name in expected:
        return True
    if len(path.parts) == 2:
        parent, child = path.parts
        if parent == "odin_mcp.egg-info" and child in EGG_INFO_FILES:
            return True
        if parent in {"docs", "scripts"} and path.suffix == ({"docs": ".md", "scripts": ".py"}[parent]):
            return True
        if parent == "tests" and path.suffix == ".py" and (child.startswith("test_") or child == "conftest.py"):
            return True
    return False


def check_sdist(archive: Path, version: str, expected: set[str]) -> None:
    prefix = f"odin_mcp-{version}"
    seen: set[str] = set()
    total = 0
    with tarfile.open(archive, "r:gz") as source:
        for item in source:
            path = checked_path(item.name)
            if path.parts[0] != prefix:
                fail(f"Unexpected source distribution root: {path}")
            if item.isdir():
                continue
            if not item.isfile():
                fail(f"Non-regular source distribution member: {path}")
            relative = PurePosixPath(*path.parts[1:])
            name = relative.as_posix()
            if name in seen or not allowed_sdist(relative, expected):
                fail(f"Unapproved or duplicate source distribution member: {name}")
            seen.add(name)
            total += item.size
            if total > MAX_ARCHIVE_BYTES:
                fail("Source distribution exceeds the public package size limit")
            stream = source.extractfile(item)
            if stream is None:
                fail(f"Unreadable source distribution member: {name}")
            data = stream.read()
            check_content(name, data)
            generated = name in {"PKG-INFO", "setup.cfg"} or relative.parts[0] == "odin_mcp.egg-info"
            if not generated:
                check_package_source(name, data)
            if name == "PKG-INFO":
                check_metadata(name, data, version)
    required = expected | {"pyproject.toml", "README.md", "LICENSE", "PKG-INFO", "docs/llm-guide.md"}
    if not required <= seen:
        fail(f"Source distribution is missing required files: {sorted(required - seen)}")


def check_tag(tag: str, version: str, require_main: bool) -> None:
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) or tag != f"v{version}":
        fail(f"Release tag must exactly match the stable package version v{version}")
    if require_main:
        def git(*args: str) -> str:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        if git("rev-parse", "HEAD") != git("rev-parse", f"refs/tags/{tag}^{{commit}}"):
            fail("Checkout does not match the release tag")
        subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--tag")
    parser.add_argument("--require-main", action="store_true")
    parser.add_argument("--verify-checksums", action="store_true")
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    if args.require_main and not args.tag:
        fail("--require-main needs --tag")
    if args.tag:
        check_tag(args.tag, version, args.require_main)
    expected = package_files()
    wheels = sorted(args.dist.glob("*.whl"))
    sources = sorted(args.dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        fail("Expected exactly one wheel and one source distribution")
    if wheels[0].name != f"odin_mcp-{version}-py3-none-any.whl" or sources[0].name != f"odin_mcp-{version}.tar.gz":
        fail("Unexpected distribution filename/version")
    allowed = {wheels[0].name, sources[0].name, "SHA256SUMS"}
    if any(p.name not in allowed for p in args.dist.iterdir()):
        fail("Distribution directory contains unexpected files")
    check_wheel(wheels[0], version, expected)
    check_sdist(sources[0], version, expected)
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(wheels + sources)]
    checksum_path = args.dist / "SHA256SUMS"
    if args.verify_checksums:
        if checksum_path.read_text(encoding="utf-8") != "".join(lines):
            fail("Release checksums do not match the validated distributions")
    else:
        checksum_path.write_text("".join(lines), encoding="utf-8")
    print(f"Validated Odin MCP {version}: wheel, source distribution, source contents and SHA256SUMS")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"Release check failed: {exc}", file=sys.stderr)
        sys.exit(1)
