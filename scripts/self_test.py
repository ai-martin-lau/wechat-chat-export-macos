#!/usr/bin/env python3
"""Run synthetic crypto and own-sender export tests without real WeChat data."""

import hashlib
import hmac
import json
import sqlite3
import struct
import tempfile
from pathlib import Path

import zstandard as zstd
from Crypto.Cipher import AES

from capture_passphrase_macos import derive_key, verify_derived_key
from decrypt_message_db import decrypt_database, decrypt_page
from export_my_text import deduplicate, export_records, read_database


def test_crypto():
    passphrase = b"P" * 32
    salt = b"S" * 16
    key = derive_key(passphrase, salt)
    iv = b"I" * 16
    plaintext = b"A" * 4000
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(plaintext)
    mac_salt = bytes(value ^ 0x3A for value in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", key, mac_salt, 2, dklen=32)
    signed = encrypted + iv
    verifier = hmac.new(mac_key, signed, hashlib.sha512)
    verifier.update(struct.pack("<I", 1))
    page = salt + encrypted + iv + verifier.digest()
    assert len(page) == 4096
    assert verify_derived_key(key, page)
    decrypted = decrypt_page(page, 1, key)
    assert decrypted[:16] == b"SQLite format 3\x00"
    assert decrypted[16:4016] == plaintext


def test_own_sender_export(temp_dir):
    database = temp_dir / "message_0.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE Name2Id(user_name TEXT)")
    connection.execute("INSERT INTO Name2Id(user_name) VALUES ('wxid_self')")
    self_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute("INSERT INTO Name2Id(user_name) VALUES ('wxid_other')")
    other_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        """
        CREATE TABLE Msg_test(
            local_id INTEGER,
            server_id INTEGER,
            local_type INTEGER,
            create_time INTEGER,
            real_sender_id INTEGER,
            message_content BLOB,
            WCDB_CT_message_content INTEGER
        )
        """
    )
    compressed = zstd.ZstdCompressor().compress("第二条".encode())
    rows = [
        (1, 101, 1, 1, self_id, "第一条", 0),
        (2, 102, 1, 2, other_id, "不应导出", 0),
        (3, 103, 1, 3, self_id, compressed, 4),
        (4, 104, 3, 4, self_id, "非文本", 0),
    ]
    connection.executemany("INSERT INTO Msg_test VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    connection.commit()
    connection.close()

    records, selected = read_database(database, "wxid_self")
    records = deduplicate(records)
    assert selected == 2
    assert [record["text"] for record in records] == ["第一条", "第二条"]
    output = temp_dir / "output"
    text_path, jsonl_path, audit_path = export_records(records, output, audit=False)
    assert text_path.read_text() == "第一条\n\n第二条"
    payloads = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
    assert payloads == [{"text": "第一条"}, {"text": "第二条"}]
    assert audit_path is None


def test_source_overwrite_guard(temp_dir):
    database = temp_dir / "source.db"
    try:
        decrypt_database(database, database, b"K" * 32)
    except RuntimeError as exc:
        assert "must not overwrite" in str(exc)
    else:
        raise AssertionError("source overwrite guard did not stop")


def main():
    test_crypto()
    with tempfile.TemporaryDirectory(prefix="wechat-skill-test-") as directory:
        temp_dir = Path(directory)
        test_own_sender_export(temp_dir)
        test_source_overwrite_guard(temp_dir)
    print("self_test=ok real_chat_data_used=false")


if __name__ == "__main__":
    main()
