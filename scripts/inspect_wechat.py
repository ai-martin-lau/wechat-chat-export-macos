#!/usr/bin/env python3
"""Inspect local macOS WeChat version, signature, accounts, and message DBs."""

import argparse
import glob
import json
import os
import platform
import plistlib
import re
import subprocess
from datetime import datetime
from pathlib import Path


DEFAULT_APP = Path("/Applications/WeChat.app")
DEFAULT_FILES_ROOT = Path.home() / (
    "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
)


def run_output(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout + result.stderr


def app_metadata(app):
    plist_path = app / "Contents/Info.plist"
    if not plist_path.exists():
        raise FileNotFoundError(f"WeChat Info.plist not found: {plist_path}")
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    signature = run_output(["codesign", "-dv", "--verbose=4", str(app)])
    team_match = re.search(r"^TeamIdentifier=(.+)$", signature, re.MULTILINE)
    return {
        "path": str(app),
        "version": plist.get("CFBundleShortVersionString"),
        "build": str(plist.get("CFBundleVersion", "")),
        "team_identifier": team_match.group(1).strip() if team_match else None,
        "signature_is_adhoc": "Signature=adhoc" in signature,
    }


def wechat_processes():
    result = subprocess.run(
        ["pgrep", "-x", "WeChat"], capture_output=True, text=True, check=False
    )
    return [int(value) for value in result.stdout.split() if value.isdigit()]


def open_paths(pids):
    paths = set()
    for pid in pids:
        result = subprocess.run(
            ["lsof", "-Fn", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            if line.startswith("n/"):
                paths.add(line[1:])
    return paths


def candidate_wxid(account_name):
    return re.sub(r"_[0-9a-fA-F]{4}$", "", account_name)


def discover_accounts(files_root, active_paths):
    accounts = []
    pattern = str(files_root / "*" / "db_storage" / "message" / "message_[0-9]*.db")
    grouped = {}
    for raw_path in glob.glob(pattern):
        db_path = Path(raw_path)
        account_root = db_path.parents[2]
        grouped.setdefault(account_root, []).append(db_path)

    for account_root, db_paths in sorted(grouped.items(), key=lambda item: str(item[0])):
        db_paths.sort()
        prefix = str(account_root) + os.sep
        accounts.append(
            {
                "directory": str(account_root),
                "directory_name": account_root.name,
                "candidate_wxid": candidate_wxid(account_root.name),
                "active": any(path.startswith(prefix) for path in active_paths),
                "message_databases": [
                    {
                        "path": str(path),
                        "bytes": path.stat().st_size,
                        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        "wal_bytes": Path(str(path) + "-wal").stat().st_size
                        if Path(str(path) + "-wal").exists()
                        else 0,
                    }
                    for path in db_paths
                ],
            }
        )
    return accounts


def inspect(app, files_root):
    pids = wechat_processes()
    active_paths = open_paths(pids)
    return {
        "architecture": platform.machine(),
        "wechat": app_metadata(app),
        "process_ids": pids,
        "accounts": discover_accounts(files_root, active_paths),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--files-root", type=Path, default=DEFAULT_FILES_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = inspect(args.app, args.files_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    wechat = report["wechat"]
    print(f"Architecture: {report['architecture']}")
    print(f"WeChat: {wechat['version']} (build {wechat['build']})")
    print(f"TeamIdentifier: {wechat['team_identifier'] or 'not set'}")
    print(f"Ad-hoc signature: {wechat['signature_is_adhoc']}")
    print(f"Running PIDs: {report['process_ids'] or 'none'}")
    print(f"Account candidates: {len(report['accounts'])}")
    for account in report["accounts"]:
        marker = "ACTIVE" if account["active"] else "inactive"
        total = sum(item["bytes"] for item in account["message_databases"])
        wal = sum(item["wal_bytes"] for item in account["message_databases"])
        print(
            f"- {marker}: {account['directory_name']} "
            f"candidate={account['candidate_wxid']} db_bytes={total} wal_bytes={wal}"
        )


if __name__ == "__main__":
    main()

