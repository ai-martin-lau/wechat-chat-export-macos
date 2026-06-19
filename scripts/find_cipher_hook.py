#!/usr/bin/env python3
"""Locate the verified WeChat 4.1.10 ARM64 cipher configuration hook."""

import argparse
import json
import plistlib
import platform
import re
import subprocess
import tempfile
from pathlib import Path


SUPPORTED_VERSION = "4.1.10"
EXPECTED_FILE_ADDRESS = 0x4A5D840
SIGNATURE = bytes.fromhex(
    "ff8301d1"  # sub sp, sp, #0x60
    "f85f02a9"  # stp x24, x23, [sp, #0x20]
    "f65703a9"  # stp x22, x21, [sp, #0x30]
    "f44f04a9"  # stp x20, x19, [sp, #0x40]
    "fd7b05a9"  # stp x29, x30, [sp, #0x50]
    "fd430191"  # add x29, sp, #0x50
    "f50303aa"  # mov x21, x3
    "f60302aa"  # mov x22, x2
    "f70301aa"  # mov x23, x1
    "f30300aa"  # mov x19, x0
    "e00301aa"  # mov x0, x1
)


def app_version(app):
    with (app / "Contents/Info.plist").open("rb") as handle:
        return plistlib.load(handle).get("CFBundleShortVersionString")


def find_all(data, pattern):
    hits = []
    start = 0
    while True:
        offset = data.find(pattern, start)
        if offset < 0:
            return hits
        hits.append(offset)
        start = offset + 1


def text_mapping(thin_binary):
    output = subprocess.check_output(["otool", "-l", str(thin_binary)], text=True)
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "segname __TEXT":
            continue
        vmaddr = None
        fileoff = None
        for detail in lines[index + 1 : index + 20]:
            stripped = detail.strip()
            if stripped.startswith("vmaddr "):
                vmaddr = int(stripped.split()[1], 0)
            elif stripped.startswith("fileoff "):
                fileoff = int(stripped.split()[1], 0)
            if vmaddr is not None and fileoff is not None:
                return vmaddr, fileoff
    raise RuntimeError("Could not locate the Mach-O __TEXT segment")


def locate(app):
    version = app_version(app)
    if platform.machine() != "arm64":
        raise RuntimeError(f"Unsupported architecture: {platform.machine()} (expected arm64)")
    if version != SUPPORTED_VERSION:
        raise RuntimeError(
            f"Unsupported WeChat version: {version} (verified: {SUPPORTED_VERSION})"
        )

    binary = app / "Contents/Resources/wechat.dylib"
    if not binary.exists():
        raise FileNotFoundError(f"Missing WeChat module: {binary}")

    with tempfile.TemporaryDirectory(prefix="wechat-hook-") as temp_dir:
        thin = Path(temp_dir) / "wechat.arm64"
        subprocess.run(
            ["lipo", str(binary), "-thin", "arm64", "-output", str(thin)],
            check=True,
        )
        data = thin.read_bytes()
        hits = find_all(data, SIGNATURE)
        if len(hits) != 1:
            raise RuntimeError(f"Expected one hook signature, found {len(hits)}")
        vmaddr, fileoff = text_mapping(thin)
        file_address = vmaddr + hits[0] - fileoff

    if file_address != EXPECTED_FILE_ADDRESS:
        raise RuntimeError(
            f"Hook moved to {file_address:#x}; expected {EXPECTED_FILE_ADDRESS:#x}"
        )
    return {
        "version": version,
        "binary": str(binary),
        "signature_hits": 1,
        "hook_file_address": hex(file_address),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("/Applications/WeChat.app"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = locate(args.app)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["hook_file_address"])


if __name__ == "__main__":
    main()

