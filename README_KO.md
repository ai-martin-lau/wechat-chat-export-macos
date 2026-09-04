<p align="center">
  <a href="README.md">English</a> · <a href="README_ZH.md">简体中文</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_ES.md">Español</a>
</p>

# wechat-chat-export-macos

> macOS의 본인 WeChat 로컬 데이터베이스에서 본인이 보낸 텍스트만 내보냅니다.

Codex와 Claude Code에서 모두 사용할 수 있는 안전 우선 Agent Skill입니다. WeChat 4.1.10의 passphrase를 검증하여 캡고, 메시지 DB 사본을 복호화한 뒤, 확인된 계정이 작성한 글만 내보냅니다. 작업 후에는 공식 WeChat 서명을 복원하고 키와 복호화 DB를 삭제합니다.

## 용도

- 본인의 글쓰기 스타일 분석
- 과거 표현과 판단 정리
- 개인 글쓰기 Agent용 말뭉치 생성
- 다른 사람의 메시지가 데이터셋에 섞이는 것 방지

## 안전 경계

- `Name2Id`에서 본인 rowid를 확인하고 `local_type = 1 AND real_sender_id = self_rowid`만 선택합니다.
- PBKDF2로 파생한 키가 DB 1페이지 HMAC 검증을 통과해야 저장합니다.
- 검증된 4.1.10 경로는 SIP를 비활성화하지 않습니다.
- 알 수 없는 버전, 지문 불일치, HMAC 실패, 미해결 WAL, 잘못된 공식 백업이 있으면 중단합니다.
- 성공과 실패 모두에서 공식 TeamIdentifier를 복원합니다.

**이 저장소에는 실제 채팅, wxid, DB, passphrase, 키가 없습니다.** 자가 테스트는 합성 데이터만 사용합니다.

## 호환성

| 환경 | 상태 |
|---|---|
| Apple Silicon macOS + WeChat 4.1.10 | 검증됨 |
| Intel Mac | 미지원 |
| 다른 WeChat 버전 | 기본적으로 중단, 브레이크포인트를 추측하지 않음 |

## 설치

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

Agent에게 요청:

```text
이 Mac의 로컬 WeChat DB에서 내가 보낸 텍스트만 글쓰기 스타일 분석용으로 내보내 줘.
```

## 출력

```text
我的微信原文.txt
我的微信原文.jsonl
```

JSONL의 각 줄은 `{"text": ...}` 필드만 포함합니다. 시간과 로컬 DB 정보는 `--audit`를 명시했을 때만 출력합니다.

## 자가 테스트

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/self_test.py
```

```text
self_test=ok real_chat_data_used=false
```

## 제한

- 이 Mac의 로컬 DB에 존재하는 기록만 내보낼 수 있습니다.
- 암호화된 WAL을 조용히 무시하지 않습니다.
- WeChat 업데이트는 내부 함수를 바꿀 수 있습니다.
- 무인 원클릭 GUI가 아닙니다.

## 독창적 기여와 기술 출처

이 저장소는 WeChat 4.1.10 ARM64의 고유 지문, SIP를 끄지 않는 복구 가능한 절차, passphrase에서 복호화까지의 검증 체인, `real_sender_id`를 사용한 본인 글 전용 출력, Codex / Claude Code 가드레일을 통합했습니다.

WCDB/SQLCipher, LLDB 캡처, 4.1+ passphrase 모델의 기초 연구 출처는 [`references/compatibility.md`](references/compatibility.md)에 기록했습니다.

본인 기기와 계정의 로컬 데이터에만 사용하세요. 이 프로젝트는 Tencent 또는 WeChat과 공식적으로 관련되지 않습니다.

## License

MIT

## Star 기록

[![Star History Chart](https://api.star-history.com/svg?repos=ai-martin-lau/wechat-chat-export-macos&type=Date)](https://star-history.com/#ai-martin-lau/wechat-chat-export-macos&Date)
