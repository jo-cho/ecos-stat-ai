"""MCP 도구 응답을 ECOS 표준 딕셔너리로 정규화하는 유틸리티."""
from __future__ import annotations

import json
from typing import Any


def _json_object(value: Any) -> dict[str, Any] | None:
    """객체·JSON 문자열·결과 래퍼를 단계별로 해석합니다."""
    for _ in range(5):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                return None
        if not isinstance(value, dict):
            return None
        # ECOS 도구가 반환하는 알려진 최상위 키
        if any(key in value for key in ('rows', 'matches', 'items', 'source', 'error', 'stat_code')):
            return value
        # 서버/클라이언트 버전에 따라 결과에 객체 또는 JSON 문자열이 들어올 수 있음
        wrapped = next((value[key] for key in ('result', 'structuredContent', 'structured_content', 'data')
                        if key in value), None)
        if wrapped is not None:
            value = wrapped
            continue
        # 구조화된 응답이 없는 경우 MCP 텍스트 블록을 검토
        content = value.get('content')
        if isinstance(content, list):
            for block in content:
                if isinstance(block, str):
                    parsed = _json_object(block)
                elif isinstance(block, dict) and block.get('type') == 'text':
                    parsed = _json_object(block.get('text'))
                else:
                    parsed = None
                if parsed is not None:
                    return parsed
        return value
    return None


def normalize_mcp_payload(structured_content: Any, content: Any) -> dict[str, Any]:
    """MCP 결과의 구조화·텍스트 채널을 모두 지원합니다."""
    parsed = _json_object(structured_content)
    if parsed is not None and parsed:
        return parsed
    blocks = []
    for block in (content or []):
        if isinstance(block, str):
            blocks.append(block)
        elif hasattr(block, 'text'):
            blocks.append(getattr(block, 'text'))
        elif isinstance(block, dict) and block.get('type') == 'text':
            blocks.append(block.get('text'))
    for text in blocks:
        parsed = _json_object(text)
        if parsed is not None:
            return parsed
    raise ValueError('MCP 도구 응답을 ECOS 데이터 형식으로 읽을 수 없습니다.')


def normalize_series_payload(payload: Any) -> dict[str, Any]:
    """화면 표시용 통계 시계열의 행 구조를 검증합니다."""
    parsed = _json_object(payload)
    if parsed is None:
        raise ValueError('MCP 통계 데이터 응답 형식이 올바르지 않습니다.')
    if 'error' in parsed:
        raise ValueError('ECOS 통계 조회 도구에서 오류가 반환되었습니다.')
    rows = parsed.get('rows')
    # 기존 ECOS API 원본 응답을 받은 경우도 지원
    if rows is None and isinstance(parsed.get('StatisticSearch'), dict):
        section = parsed['StatisticSearch']
        parsed = {**parsed, 'rows': section.get('row', []),
                  'total_count': section.get('list_total_count', 0)}
        rows = parsed['rows']
    if rows is None and isinstance(parsed.get('row'), list):
        parsed = {**parsed, 'rows': parsed['row']}
        rows = parsed['rows']
    if not isinstance(rows, list):
        raise ValueError('MCP 결과에 통계 행(rows)이 없습니다.')
    return parsed
