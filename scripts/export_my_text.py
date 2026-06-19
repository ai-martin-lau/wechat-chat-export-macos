#!/usr/bin/env python3
"""Export only text messages authored by one confirmed WeChat wxid."""

import argparse
import glob
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import zstandard as zstd


def decode_content(content, compression_type):
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if not isinstance(content, bytes):
        return str(content)
    if compression_type == 4 or content.startswith(b"\x28\xb5\x2f\xfd"):
        try:
            return zstd.ZstdDecompressor().decompress(content).decode(
                "utf-8", errors="replace"
            )
        except zstd.ZstdError:
            pass
    return content.decode("utf-8", errors="replace")


def strip_group_prefix(text, my_wxid):
    for separator in (":\r\n", ":\n"):
        prefix = my_wxid + separator
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def read_database(db_path, my_wxid):
    records = []
    selected_rows = 0
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
        sender = connection.execute(
            "SELECT rowid FROM Name2Id WHERE user_name = ?", (my_wxid,)
        ).fetchone()
        if sender is None:
            return records, selected_rows

        tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name LIKE 'Msg_%'"
        ).fetchall()
        for (table,) in tables:
            quoted = quote_identifier(table)
            columns = {
                row[1] for row in connection.execute(f"PRAGMA table_info({quoted})")
            }
            required = {
                "local_id",
                "server_id",
                "local_type",
                "create_time",
                "real_sender_id",
                "message_content",
            }
            if not required.issubset(columns):
                continue
            compression = (
                "WCDB_CT_message_content"
                if "WCDB_CT_message_content" in columns
                else "0"
            )
            query = f"""
                SELECT local_id, server_id, create_time, message_content, {compression}
                FROM {quoted}
                WHERE local_type = 1 AND real_sender_id = ?
            """
            for local_id, server_id, timestamp, content, compression_type in connection.execute(
                query, (sender[0],)
            ):
                selected_rows += 1
                text = decode_content(content, compression_type)
                if text is None:
                    continue
                text = strip_group_prefix(text, my_wxid)
                if "\x00" in text:
                    raise ValueError(
                        f"NUL byte found in text record {db_path.name}/{table}/{local_id}"
                    )
                records.append(
                    {
                        "time": timestamp or 0,
                        "server_id": server_id or 0,
                        "local_id": local_id or 0,
                        "source": db_path.name,
                        "table": table,
                        "text": text,
                    }
                )
    return records, selected_rows


def deduplicate(records):
    seen = set()
    result = []
    for record in sorted(
        records,
        key=lambda item: (
            item["time"],
            item["server_id"],
            item["source"],
            item["local_id"],
        ),
    ):
        if record["server_id"]:
            key = ("server", record["server_id"])
        else:
            key = ("local", record["source"], record["table"], record["local_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def iso_time(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def export_records(records, output_dir, audit=False):
    output_dir.mkdir(parents=True, exist_ok=True)
    text_path = output_dir / "我的微信原文.txt"
    jsonl_path = output_dir / "我的微信原文.jsonl"

    with text_path.open("w", encoding="utf-8") as handle:
        for index, record in enumerate(records):
            if index:
                handle.write("\n\n")
            handle.write(record["text"])

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps({"text": record["text"]}, ensure_ascii=False) + "\n")

    audit_path = None
    if audit:
        audit_path = output_dir / "导出校验.jsonl"
        with audit_path.open("w", encoding="utf-8") as handle:
            for record in records:
                payload = {
                    "time": iso_time(record["time"]),
                    "source": record["source"],
                    "table": record["table"],
                    "local_id": record["local_id"],
                    "server_id": record["server_id"],
                    "text": record["text"],
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return text_path, jsonl_path, audit_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decrypted", type=Path, required=True)
    parser.add_argument("--my-wxid", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()

    message_dir = args.decrypted.resolve() / "message"
    db_paths = [Path(path) for path in sorted(glob.glob(str(message_dir / "message_[0-9]*.db")))]
    if not db_paths:
        raise SystemExit(f"No decrypted message databases found: {message_dir}")

    records = []
    selected_rows = 0
    for db_path in db_paths:
        db_records, db_selected = read_database(db_path, args.my_wxid)
        records.extend(db_records)
        selected_rows += db_selected
    decoded_records = len(records)
    records = deduplicate(records)
    text_path, jsonl_path, audit_path = export_records(records, args.output, args.audit)

    print(
        f"selected_rows={selected_rows} decoded_records={decoded_records} "
        f"exported_records={len(records)} "
        f"duplicates_removed={decoded_records - len(records)}"
    )
    print(f"txt={text_path}")
    print(f"jsonl={jsonl_path}")
    if audit_path:
        print(f"audit={audit_path}")


if __name__ == "__main__":
    main()
