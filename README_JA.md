<p align="center">
  <a href="README.md">English</a> · <a href="README_ZH.md">简体中文</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_ES.md">Español</a>
</p>

# wechat-chat-export-macos

> macOS 上の自分の WeChat ローカル DB から、自分が送信したテキストだけを書き出します。

Codex と Claude Code の両方で使える、安全性を優先した Agent Skill です。WeChat 4.1.10 の passphrase を検証付きで取得し、メッセージ DB のコピーを復号し、確認済みアカウント自身が書いた文章だけを出力します。終了後は公式 WeChat の署名を復元し、鍵と復号済み DB を削除します。

## 用途

- 自分の文体を分析する
- 過去の表現や判断を整理する
- 個人用ライティング Agent 用の語料を作る
- 他人のメッセージをデータセットに混ぜない

## セキュリティ境界

- `Name2Id` から自分の rowid を求め、`local_type = 1 AND real_sender_id = self_rowid` のみを選択します。
- passphrase から導出した鍵は、DB の 1 ページ目の HMAC に合格した場合だけ保存します。
- 検証済みの 4.1.10 手順では SIP を無効にしません。
- 未知のバージョン、指紋不一致、HMAC 失敗、未解決 WAL、無効な公式バックアップで停止します。
- 成功時も失敗時も公式 TeamIdentifier を復元します。

**このリポジトリに実際のチャット、wxid、DB、passphrase、鍵は含まれません。** セルフテストは合成データだけを使います。

## 対応環境

| 環境 | 状態 |
|---|---|
| Apple Silicon macOS + WeChat 4.1.10 | 検証済み |
| Intel Mac | 未対応 |
| その他の WeChat バージョン | 既定で停止。ブレークポイントを推測しない |

## インストール

Codex:

```bash
git clone https://github.com/ai-martin-lau/wechat-chat-export-macos.git \
  ~/.codex/skills/wechat-chat-export-macos
```

Claude Code:

```bash
git clone https://github.com/ai-martin-lau/wechat-chat-export-macos.git \
  ~/.claude/skills/wechat-chat-export-macos
```

Agent への依頼例:

```text
この Mac のローカル WeChat DB から、自分が送ったテキストだけを文体分析用に書き出してください。
```

## 出力

```text
我的微信原文.txt
我的微信原文.jsonl
```

JSONL の各行は `{"text": ...}` のみです。時刻などのローカル情報は、明示的に `--audit` を指定した場合だけ出力されます。

## 自己テスト

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/self_test.py
```

```text
self_test=ok real_chat_data_used=false
```

## 制限

- この Mac のローカル DB に存在する履歴だけが対象です。
- 暗号化 WAL は自動的に無視しません。
- WeChat の更新後は内部関数が変わる可能性があります。
- 無人で実行するワンクリック GUI ではありません。

## オリジナルの貢献と技術的出典

本リポジトリは、WeChat 4.1.10 の一意な ARM64 指紋、SIP を無効にしない安全フロー、passphrase から復号までの検証チェーン、`real_sender_id` による自分の文章だけの出力、Codex / Claude Code 用のガードレールを統合しています。

WCDB/SQLCipher、LLDB キャプチャ、4.1+ passphrase モデルの基礎研究については、[`references/compatibility.md`](references/compatibility.md) に記載したオープンソースを参照しています。

自分のデバイスとアカウントのローカルデータにのみ使用してください。本プロジェクトは Tencent または WeChat とは無関係です。

## License

MIT

## Star 履歴

[![Star History Chart](https://api.star-history.com/svg?repos=ai-martin-lau/wechat-chat-export-macos&type=Date)](https://star-history.com/#ai-martin-lau/wechat-chat-export-macos&Date)
