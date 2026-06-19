# Database and Key Notes

Load this reference only for debugging or adapting the verified workflow.

## WeChat 4.1.10 Message Key

The verified breakpoint receives a 32-byte passphrase. Derive the per-database encryption key using the first 16 bytes of that database file as salt:

```text
enc_key = PBKDF2-HMAC-SHA512(
  password=passphrase,
  salt=db_page_1[0:16],
  iterations=256000,
  dklen=32
)
```

SQLCipher/WCDB page parameters observed in the working path:

- page size: 4096 bytes
- reserve: 80 bytes
- IV: 16 bytes
- HMAC: SHA-512, 64 bytes
- encryption: AES-256-CBC
- HMAC key: `PBKDF2-HMAC-SHA512(enc_key, salt XOR 0x3a, 2, 32)`
- page number in HMAC input: little-endian unsigned 32-bit

For page 1, the unencrypted database salt occupies bytes `0:16`; encrypted content starts at byte 16. For later pages, encrypted content starts at byte 0.

## Own-Text Predicate

Resolve the current sender id:

```sql
SELECT rowid FROM Name2Id WHERE user_name = ?;
```

Then inspect every `Msg_%` table that has the required columns and select:

```sql
SELECT local_id, server_id, create_time, message_content, WCDB_CT_message_content
FROM Msg_<hash>
WHERE local_type = 1 AND real_sender_id = ?;
```

`local_type = 1` identifies text messages in the verified schema. `real_sender_id` is the reliable authorship filter for both direct and group conversations.

Some `message_content` values use Zstandard compression. Treat `WCDB_CT_message_content = 4` or Zstandard magic bytes `28 b5 2f fd` as compressed content.

Deduplicate by nonzero `server_id`. For records without a server id, use database, table, and `local_id` as the fallback identity.

## WAL Boundary

An encrypted SQLCipher WAL uses a plaintext SQLite WAL header and frame headers, but encrypted page bodies. A manually decrypted main database does not automatically include those frames. Never claim a complete latest-state export after ignoring a non-empty WAL unless its message impact was independently ruled out.

