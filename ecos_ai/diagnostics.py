"""MCP/ECOS 오류 메시지의 비밀값 제거 및 진단 표시용 유틸리티."""
from __future__ import annotations

import re
from typing import Any


def safe_error_text(value: Any, *secrets: str, limit: int = 350) -> str:
    """오류 문자열에서 인증키와 인증 URL을 제거합니다."""
    message = str(value or '상세 오류 메시지가 제공되지 않았습니다.')
    for secret in secrets:
        if isinstance(secret, str) and secret:
            message = message.replace(secret, '[비공개]')
    # ECOS 인증키는 서비스명 바로 뒤의 URL 경로에 위치함
    message = re.sub(r'(?i)(https?://[^\s/]*/api/[A-Za-z]+)/[^/\s]+', r'\1/[비공개]', message)
    # 공통 키 형식이 로그에 들어오지 않도록 추가 보호
    message = re.sub(r'(?i)(OPENAI_API_KEY|ECOS_API_KEY)\s*[:=]\s*[^\s,;]+', r'\1=[비공개]', message)
    message = re.sub(r'\bsk-[A-Za-z0-9_-]{12,}\b', '[비공개]', message)
    return message[:limit]


def tool_error_text(result: Any, *secrets: str) -> str:
    """MCP CallToolResult의 텍스트 블록에서 안전하게 오류 문구를 꺼냅니다."""
    texts = []
    for block in getattr(result, 'content', []) or []:
        if isinstance(block, dict) and isinstance(block.get('text'), str):
            texts.append(block['text'])
        elif isinstance(getattr(block, 'text', None), str):
            texts.append(block.text)
    return safe_error_text(' | '.join(texts), *secrets)
