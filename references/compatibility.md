# Compatibility and Upstream Options

## Verified Local Path

Verified on 2026-06-19:

- macOS 26.3.2
- Apple Silicon (`arm64`)
- WeChat 4.1.10, `CFBundleVersion 268851` (runtime client version `4066646579`)
- `/Applications/WeChat.app/Contents/Resources/wechat.dylib`
- unique ARM64 hook signature at file address `0x4a5d840`
- passphrase capture through LLDB after ad-hoc signing
- no SIP disable required
- official app restored to TeamIdentifier `5A4RE8SF68`

Treat any application update as unverified until both the function signature and derived database key pass validation.

## GitHub Projects

These are useful upstream components, not interchangeable guarantees:

| Project | Useful capability | Boundary observed 2026-06-19 |
|---|---|---|
| [ydotdog/wechat-export-macos](https://github.com/ydotdog/wechat-export-macos) | macOS decryption/export scripts | README describes raw-key memory scanning; that path did not yield the 4.1.10 passphrase-derived key |
| [lopleec/wxchat-export](https://github.com/lopleec/wxchat-export) | static hook discovery, LLDB capture, Markdown/JSONL export | README declares full macOS ARM64 support for WeChat 4.1.5; verify newer versions before use |
| [BIBOYANG425/wechat-chat-history-mac](https://github.com/BIBOYANG425/wechat-chat-history-mac) | WeChat 4.1 guidance and multi-shard helpers | README reports testing on 4.1.7 and recommends disabling SIP; do not adopt that step by default |
| [Thearas/wechat-db-decrypt-macos](https://github.com/Thearas/wechat-db-decrypt-macos) | LLDB key capture and database decryption foundations | version-specific breakpoints and lazy database opening require validation |
| [ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) | cross-platform SQLCipher decryption/export components | raw-key scanners may not cover passphrase-based 4.1+ behavior |
| [wcdb-key-tool](https://github.com/TANGandXUE/wcdb-key-tool) | Linux static analysis and 4.1+ passphrase/PBKDF2 model | Linux/GDB implementation, not a macOS drop-in |

Prefer a maintained upstream tool when it explicitly supports the installed version and passes its key/HMAC checks. Use this Skill's verified fallback only for the stated local version.

## Stop Conditions

Stop and re-research rather than improvising when:

- the Mac is Intel;
- WeChat is not 4.1.10 and no upstream explicitly supports it;
- `wechat.dylib` is absent;
- the hook signature is missing, duplicated, or moved;
- the key candidate fails page HMAC verification;
- the official application backup cannot be verified;
- WAL may contain messages and no WAL-aware reader is available.
