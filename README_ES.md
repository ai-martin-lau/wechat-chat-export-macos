<p align="center">
  <a href="README.md">简体中文</a> · <a href="README_EN.md">English</a> · <a href="README_JA.md">日本語</a> · <a href="README_KO.md">한국어</a> · <a href="README_ES.md">Español</a>
</p>

<p align="center">
  <img src="assets/cover.png" alt="wechat-chat-export-macos" width="100%">
</p>

# wechat-chat-export-macos

> Exporta solo los mensajes de texto que tú enviaste desde tu propia base de datos local de WeChat en macOS.

Es un Agent Skill orientado a la seguridad para **Codex** y **Claude Code**. Captura y verifica la passphrase de WeChat 4.1.10, descifra una copia de la base de mensajes, selecciona únicamente el texto escrito por la cuenta confirmada, restaura la firma oficial de WeChat y elimina las claves y bases descifradas intermedias.

## Para qué sirve

- analizar tu estilo de escritura;
- revisar expresiones y decisiones pasadas;
- crear un corpus para un agente personal de escritura;
- evitar mezclar los mensajes de otras personas en el conjunto de datos.

## Modelo de seguridad

- Resuelve el rowid propio desde `Name2Id` y exige `local_type = 1 AND real_sender_id = self_rowid`.
- Solo guarda una clave candidata después de PBKDF2 y de verificar el HMAC de la primera página.
- La ruta verificada para 4.1.10 no desactiva SIP.
- Se detiene ante versiones desconocidas, firmas movidas o duplicadas, HMAC fallido, WAL sin resolver o una copia oficial no válida.
- Restaura el TeamIdentifier oficial tanto si el proceso tiene éxito como si falla.

**Este repositorio no contiene chats reales, wxid, bases de datos, passphrases ni claves.** La prueba automática usa datos sintéticos.

## Compatibilidad

| Entorno | Estado |
|---|---|
| Apple Silicon macOS + WeChat 4.1.10 | Verificado |
| Intel Mac | No compatible |
| Otras versiones de WeChat | Se detiene por defecto; nunca adivina un breakpoint |

## Instalación

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

Petición de ejemplo:

```text
Exporta solo los mensajes de texto que envié desde la base local de WeChat de este Mac para analizar mi estilo de escritura.
```

## Salida

```text
我的微信原文.txt
我的微信原文.jsonl
```

Cada línea JSONL contiene solo `{"text": ...}`. Los metadatos locales se generan únicamente al usar `--audit` de forma explícita.

## Prueba automática

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/self_test.py
```

```text
self_test=ok real_chat_data_used=false
```

## Limitaciones

- Solo exporta el historial ya presente en la base local de este Mac.
- Nunca ignora silenciosamente un WAL cifrado.
- Una actualización de WeChat puede mover funciones internas.
- No es una interfaz gráfica desatendida de un solo clic.

## Contribuciones originales y fuentes técnicas

Este repositorio integra una firma ARM64 única y verificada para WeChat 4.1.10, un flujo recuperable sin desactivar SIP, una cadena verificada desde la passphrase hasta el descifrado, exportación exclusiva del autor mediante `real_sender_id` y guardas de seguridad para Codex / Claude Code.

La investigación base sobre WCDB/SQLCipher, captura con LLDB y el modelo de passphrase de WeChat 4.1+ se documenta en [`references/compatibility.md`](references/compatibility.md).

Utiliza este proyecto únicamente con datos locales de tu propio dispositivo y cuenta. No está afiliado ni respaldado por Tencent o WeChat.

## License

MIT
