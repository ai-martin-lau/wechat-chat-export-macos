---
name: wechat-chat-export-macos
description: Safely export only text messages sent by the current user's own account from local WeChat databases on macOS. Use when the user asks to export WeChat chat history, collect only their own messages for writing-style analysis, decrypt a local WeChat 4.x WCDB database, diagnose macOS WeChat database/key compatibility, or repeat the verified WeChat 4.1.10 Apple Silicon export workflow.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
---

# macOS WeChat Own-Text Export

Export only text authored by the user's current WeChat account. Treat app signing, database keys, decrypted databases, and other participants' messages as sensitive.

## Non-Negotiable Guardrails

- Operate only on the user's own Mac, account, and local data.
- Ask before re-signing or replacing `/Applications/WeChat.app`.
- Back up and verify the official app before re-signing it.
- Do not disable SIP for the verified 4.1.10 path.
- Never guess a breakpoint address. Stop if `scripts/find_cipher_hook.py` does not return exactly one verified address.
- Never print a passphrase, raw database key, or chat sample to logs or the response.
- Never silently ignore a non-empty `-wal` file. Follow the WAL decision in Step 6.
- Restore the official app and remove key/decrypted intermediates on both success and failure.
- Do not package real chat content, key files, or decrypted databases inside this Skill.

## Prerequisites

- macOS on Apple Silicon, WeChat 4.1.10 (the verified path; other versions go through `references/compatibility.md` first).
- Xcode or Command Line Tools with `lldb` (`lldb -P` must print a path); `sudo` for the capture step.
- Python 3.9+ with `venv`; script dependencies are only `pycryptodome` and `zstandard` (`scripts/requirements.txt`).
- `CLAUDE_SKILL_DIR` is set by Claude Code. In other runtimes (Codex, plain shell) replace it with the absolute path of this Skill directory.
- Typical use: feed the exported own-text corpus to a local writing-style analysis. Keep the corpus on this machine; do not upload it.

Read [references/compatibility.md](references/compatibility.md) before handling any version other than WeChat 4.1.10 on Apple Silicon. Read [references/database-format.md](references/database-format.md) only when debugging key verification, decryption, WAL behavior, or sender selection.

## Workflow

### 1. Diagnose Before Modifying Anything

Run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/inspect_wechat.py"
```

Claude Code provides `CLAUDE_SKILL_DIR` as this Skill directory. Confirm:

1. Architecture is `arm64`.
2. WeChat version is `4.1.10` for the verified local path.
3. The active account directory and candidate wxid match the account the user intends to export.
4. At least one `db_storage/message/message_N.db` exists.
5. The current TeamIdentifier is recorded before any signature change.

If multiple account directories exist and active-process evidence is inconclusive, ask the user to identify the account. Do not choose by directory size alone.

### 2. Prepare an Isolated Work Directory

Create a new directory outside the Skill, preferably on the Desktop. Keep outputs and sensitive intermediates separate:

```text
wechat-export-work/
├── official-backup/
├── encrypted-snapshot/
├── decrypted/
├── secrets/
└── output/
```

Create a local virtual environment and install only the script dependencies:

```bash
python3 -m venv "$WORK/.venv"
"$WORK/.venv/bin/pip" install -r "${CLAUDE_SKILL_DIR}/scripts/requirements.txt"
```

Record the original message database and WAL sizes before launching a controlled capture session. Do not copy all media or unrelated databases when the request is text-only.

### 3. Back Up and Re-Sign WeChat

Quit WeChat. Create a resource-preserving backup:

```bash
ditto -c -k --sequesterRsrc --keepParent \
  /Applications/WeChat.app "$WORK/official-backup/WeChat-official.zip"
```

Extract the backup to a temporary directory, run `codesign --verify --deep --strict`, and confirm its TeamIdentifier matches the value recorded in Step 1. Only then apply an ad-hoc signature:

```bash
codesign --force --deep --sign - /Applications/WeChat.app
```

Do not continue if backup verification fails.

### 4. Locate the Verified Cipher Hook

Run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/find_cipher_hook.py" \
  --app /Applications/WeChat.app --json
```

For the verified WeChat 4.1.10 ARM64 build, the script must find one signature and resolve file address `0x4a5d840`. Stop on a version mismatch, zero hits, multiple hits, or a different address.

### 5. Capture and Verify the Passphrase

Use Xcode LLDB's Python module:

```bash
LLDB_PY="$(lldb -P)"
```

Start `scripts/capture_passphrase_macos.py` as root in wait-for-launch mode. Pass the active account's `message_0.db`, the verified hook address, an output path under `secrets/`, and the invoking user's uid/gid. Redirect the process log to a file that never prints secret values.

Then launch WeChat and enter the confirmed account. The capture script must:

1. Read a 32-byte candidate at the cipher configuration breakpoint.
2. Derive the message database key with PBKDF2-HMAC-SHA512.
3. Verify page 1 HMAC before writing the result.
4. Write the secret JSON with mode `0600`.
5. Detach LLDB immediately after a verified capture.

Do not accept an unverified candidate.

### 6. Handle WAL Explicitly and Decrypt a Copy

Quit WeChat before reading the database. Inspect `message_0.db-wal` and compare it with the sizes recorded before capture.

- If no non-empty WAL exists, decrypt normally.
- If the WAL predates the controlled capture or may contain messages, stop. Use a WAL-aware SQLCipher path from [references/compatibility.md](references/compatibility.md), or obtain explicit user acceptance that the export covers only the checkpointed main database.
- If the WAL was created only by the controlled login, the user sent no messages during capture, and message counts are independently shown unchanged, pass `--ignore-wal` and report that scope.

Decrypt only a copy:

```bash
"$WORK/.venv/bin/python" "${CLAUDE_SKILL_DIR}/scripts/decrypt_message_db.py" \
  --encrypted "$MESSAGE_DB" \
  --key-file "$WORK/secrets/passphrase.json" \
  --output "$WORK/decrypted/message/message_0.db"
```

Add `--ignore-wal` only after satisfying the decision above. Require `PRAGMA quick_check` to return `ok`.

### 7. Export Only the Current User's Text

Run:

```bash
"$WORK/.venv/bin/python" "${CLAUDE_SKILL_DIR}/scripts/export_my_text.py" \
  --decrypted "$WORK/decrypted" \
  --my-wxid "$CONFIRMED_WXID" \
  --output "$WORK/output"
```

The selection must remain:

```sql
local_type = 1 AND real_sender_id = self_rowid
```

Resolve `self_rowid` from `Name2Id.user_name = CONFIRMED_WXID`. Do not replace this with conversation direction, UI labels, nickname matching, or a table-name guess.

Default outputs are:

- `我的微信原文.txt`: raw text separated by blank lines.
- `我的微信原文.jsonl`: one `{"text": ...}` object per message.

Generate `导出校验.jsonl` only when `--audit` is explicitly useful. It still contains only the user's own text, but adds local metadata.

### 8. Verify Without Exposing Content

Verify:

1. SQLite quick check is `ok`.
2. JSONL parses successfully and every object has exactly one `text` key.
3. Exported count equals the deduplicated selected record count.
4. No result contains a NUL byte.
5. Report only counts, byte sizes, hashes, and paths. Do not print message samples.

### 9. Restore and Clean Up

Always quit WeChat before restoration. Extract the official backup, verify its original TeamIdentifier, replace the ad-hoc app, and run:

```bash
codesign --verify --deep --strict /Applications/WeChat.app
```

Only after successful restoration, remove:

- passphrase/key JSON files;
- decrypted databases and temporary WAL snapshots;
- LLDB logs containing addresses or process details;
- the ad-hoc app copy.

Keep only the requested own-text outputs and, if useful, the verified official backup archive. Confirm the installed app's TeamIdentifier matches the pre-change value.

### 10. Report Completion

Give the exact absolute paths, exported message count, source scope (Mac-local/checkpointed/WAL-aware), verification result, and restoration status. State clearly that phone-only history is absent unless it was successfully migrated and visible in this Mac's local database.
