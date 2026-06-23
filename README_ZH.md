<p align="center">
  <a href="README.md">English</a> · <a href="README_ZH.md">简体中文</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_ES.md">Español</a>
</p>

# wechat-chat-export-macos

> 从你自己的 Mac 本地微信数据库里，只导出你本人发送的纯文本。

这是一个同时适配 **Codex** 和 **Claude Code** 的 Agent Skill。它把 macOS 微信 4.1.10 上实际跑通的流程固化下来：识别当前账号，验证数据库口令，解密消息库副本，只筛出自己写过的文本，最后恢复微信官方签名并删除密钥与明文数据库。

## 它解决什么

微信没有提供“只导出我说过的话”的按钮。如果你想：

- 蒸馏自己的写作风格；
- 整理自己过去的表达、判断和口头禅；
- 给个人写作 Agent 准备只属于你的语料；
- 避免把别人的聊天内容混进数据集；

这个 Skill 就是为这个窄而具体的目标做的。

## 安全边界

| 保护项 | 做法 |
|---|---|
| 只导出本人 | 通过 `Name2Id` 解析本人 rowid，固定筛选 `local_type = 1 AND real_sender_id = self_rowid` |
| 不猜密钥 | 只有 passphrase 派生后通过数据库第一页 HMAC 校验才保存 |
| 不关闭 SIP | 已验证的 4.1.10 路径使用“先备份，再临时重签”，不要求关闭系统完整性保护 |
| 失败关闭 | 版本、函数指纹、HMAC、WAL 或官方备份任一异常就停止 |
| 恢复官方微信 | 成功或失败都要恢复原 TeamIdentifier，并重新运行 `codesign --verify` |
| 不留敏感中间件 | 最终默认只保留 TXT 和 text-only JSONL，删除 passphrase、key 和明文库 |

**本仓库不包含任何真实聊天记录、wxid、数据库、passphrase 或密钥。** `self_test.py` 只使用合成数据。

## 兼容性

| 环境 | 状态 |
|---|---|
| Apple Silicon macOS + WeChat 4.1.10 | 已验证 |
| Intel Mac | 未支持 |
| 其他微信版本 | 默认停止，不猜断点地址 |
| Windows / Linux | 不是本 Skill 的目标平台 |

已验证环境和上游方案边界见 [`references/compatibility.md`](references/compatibility.md)。

## 安装

### Codex

```bash
git clone https://github.com/ai-martin-lau/wechat-chat-export-macos.git \
  ~/.codex/skills/wechat-chat-export-macos
```

### Claude Code

```bash
git clone https://github.com/ai-martin-lau/wechat-chat-export-macos.git \
  ~/.claude/skills/wechat-chat-export-macos
```

安装后对 Agent 说：

```text
导出这台 Mac 微信里我自己发过的纯文本，给我做写作风格语料。
```

Agent 会先诊断版本、账号、数据库和签名，需要修改微信签名前会征求你的明确同意。

## 工作流

```mermaid
flowchart LR
  A["诊断版本与账号"] --> B["备份官方微信"]
  B --> C["临时重签"]
  C --> D["LLDB 捕获 passphrase"]
  D --> E["PBKDF2 + HMAC 验证"]
  E --> F["解密消息库副本"]
  F --> G["只筛本人文本"]
  G --> H["恢复官方签名"]
  H --> I["清理密钥与明文库"]
```

## 输出

```text
我的微信原文.txt
我的微信原文.jsonl
```

JSONL 每行只有一个字段：

```json
{"text":"这是你自己发送的一条文本"}
```

带时间和本地数据库标识的校验文件只在显式使用 `--audit` 时生成。

## 手动诊断与自测

```bash
python3 scripts/inspect_wechat.py
python3 scripts/find_cipher_hook.py --app /Applications/WeChat.app --json

python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/self_test.py
```

预期自测输出：

```text
self_test=ok real_chat_data_used=false
```

## 文件

| 路径 | 作用 |
|---|---|
| `SKILL.md` | Agent 必须遵守的完整安全流程 |
| `scripts/inspect_wechat.py` | 只读诊断微信版本、签名、账号候选和数据库 |
| `scripts/find_cipher_hook.py` | 在 4.1.10 ARM64 模块中定位唯一已验证函数指纹 |
| `scripts/capture_passphrase_macos.py` | 使用 LLDB 捕获候选口令并执行 HMAC 校验 |
| `scripts/decrypt_message_db.py` | 逐页验证并解密消息库副本 |
| `scripts/export_my_text.py` | 解压、只筛本人文本、去重和导出 |
| `scripts/self_test.py` | 只用合成数据验证密码学和作者筛选 |
| `references/database-format.md` | WCDB/SQLCipher 页格式与作者判定依据 |

## 局限

- 只能导出这台 Mac 本地数据库已有的记录。手机独有历史必须先成功迁移到 Mac。
- 加密 WAL 不会被静默忽略。它可能包含尚未合并的最新消息，需要 WAL-aware 路径或用户明确接受仅导出已 checkpoint 的主库。
- 微信每次升级都可能改变内部函数。指纹不匹配时应停止，而不是猜一个新地址。
- 这是安全导向的 Agent Skill，不是无人值守的一键 GUI。

## 原创贡献与技术来源

本仓库的原创贡献是：

- 在 Apple Silicon macOS 上实测并固化微信 4.1.10 的 `wechat.dylib` 唯一函数指纹；
- 组合出不关闭 SIP、先备份官方应用、完成后恢复签名的完整安全流程；
- 把 passphrase 捕获、PBKDF2 派生、HMAC 校验、逐页解密串成可验证链路；
- 通过 `real_sender_id` 实现“只导出我说过的话”，并生成 text-only 语料；
- 将上述过程封装成 Codex / Claude Code 可执行 Skill，加入版本、WAL、隐私和恢复护栏。

WCDB/SQLCipher 格式、LLDB 捕获和 4.1+ passphrase 派生的基础研究来自已有开源项目。本仓库在版本适配时参考了：

- [ydotdog/wechat-export-macos](https://github.com/ydotdog/wechat-export-macos)
- [lopleec/wxchat-export](https://github.com/lopleec/wxchat-export)
- [Thearas/wechat-db-decrypt-macos](https://github.com/Thearas/wechat-db-decrypt-macos)
- [ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt)
- [TANGandXUE/wcdb-key-tool](https://github.com/TANGandXUE/wcdb-key-tool)
- [BIBOYANG425/wechat-chat-history-mac](https://github.com/BIBOYANG425/wechat-chat-history-mac)

详细边界和适用版本见 [`references/compatibility.md`](references/compatibility.md)。

## 合规说明

仅用于处理你自己设备、自己账号上的本地数据。不得在未经授权的设备或账号上使用。本项目与腾讯、微信没有官方关联；WeChat 和微信的相关商标归其各自权利人所有。

## License

MIT

## Star 趋势

[![Star 趋势图](https://api.star-history.com/svg?repos=ai-martin-lau/wechat-chat-export-macos&type=Date)](https://star-history.com/#ai-martin-lau/wechat-chat-export-macos&Date)
