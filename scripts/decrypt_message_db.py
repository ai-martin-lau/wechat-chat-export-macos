#!/usr/bin/env python3
"""Decrypt one checkpointed WeChat SQLCipher message database copy."""

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import struct
import sys
from pathlib import Path

from Crypto.Cipher import AES


PAGE_SIZE = 4096
RESERVE_SIZE = 80
SQLITE_HEADER = b"SQLite format 3\x00"


def derive_mac_key(enc_key, salt):
    mac_salt = bytes(value ^ 0x3A for value in salt)
    return hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=32)


def verify_page(page, page_number, mac_key):
    signed = page[16:4032] if page_number == 1 else page[:4032]
    verifier = hmac.new(mac_key, signed, hashlib.sha512)
    verifier.update(struct.pack("<I", page_number))
    return hmac.compare_digest(verifier.digest(), page[4032:4096])


def decrypt_page(page, page_number, enc_key):
    iv = page[4016:4032]
    if page_number == 1:
        decrypted = AES.new(enc_key, AES.MODE_CBC, iv).decrypt(page[16:4016])
        return SQLITE_HEADER + decrypted + (b"\x00" * RESERVE_SIZE)
    decrypted = AES.new(enc_key, AES.MODE_CBC, iv).decrypt(page[:4016])
    return decrypted + (b"\x00" * RESERVE_SIZE)


def load_key(key_file):
    payload = json.loads(key_file.read_text(encoding="utf-8"))
    value = payload.get("message_key")
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("key file does not contain a 32-byte message_key")
    return bytes.fromhex(value)


def decrypt_database(encrypted, output, enc_key, ignore_wal=False):
    if encrypted.resolve() == output.resolve():
        raise RuntimeError("output must not overwrite the encrypted source database")
    wal = Path(str(encrypted) + "-wal")
    if wal.exists() and wal.stat().st_size > 32 and not ignore_wal:
        raise RuntimeError(
            f"non-empty WAL exists ({wal.stat().st_size} bytes); "
            "use a WAL-aware path or explicitly pass --ignore-wal after validation"
        )
    size = encrypted.stat().st_size
    if size == 0 or size % PAGE_SIZE:
        raise RuntimeError(f"database size is not a nonzero multiple of {PAGE_SIZE}: {size}")

    with encrypted.open("rb") as source:
        salt = source.read(16)
    mac_key = derive_mac_key(enc_key, salt)
    total_pages = size // PAGE_SIZE
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    temporary.unlink(missing_ok=True)

    try:
        with encrypted.open("rb") as source, temporary.open("wb") as destination:
            for page_number in range(1, total_pages + 1):
                page = source.read(PAGE_SIZE)
                if len(page) != PAGE_SIZE:
                    raise RuntimeError(f"short read at page {page_number}")
                if not verify_page(page, page_number, mac_key):
                    raise RuntimeError(f"HMAC verification failed at page {page_number}")
                destination.write(decrypt_page(page, page_number, enc_key))
            destination.flush()
            os.fsync(destination.fileno())
        temporary.replace(output)

        connection = sqlite3.connect(output)
        check = connection.execute("PRAGMA quick_check").fetchone()[0]
        table_count = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        connection.close()
        if check != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {check}")
        return total_pages, table_count
    except Exception:
        temporary.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encrypted", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ignore-wal", action="store_true")
    args = parser.parse_args()
    pages, tables = decrypt_database(
        args.encrypted,
        args.output,
        load_key(args.key_file),
        ignore_wal=args.ignore_wal,
    )
    print(f"decrypted_pages={pages} tables={tables} sqlite_quick_check=ok")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[-] {exc}", file=sys.stderr)
        raise SystemExit(1)
