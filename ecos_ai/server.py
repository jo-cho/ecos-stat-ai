"""ECOS 전용 MCP 도구 서버."""
from typing import Any
from mcp.server import MCPServer
from ecos_ai.ecos import EcosAPI

mcp = MCPServer('ECOS Statistics', instructions='모든 통계는 ECOS에서만 검색하고 조회합니다.')

@mcp.tool()
def find_statistics(keyword: str, limit: int = 20) -> dict[str, Any]:
    """한국은행 ECOS 통계표명 검색. 핵심어로 짧게 검색하고 실제 통계표 코드를 확보합니다."""
    return EcosAPI().tables(keyword, limit)

@mcp.tool()
def get_statistic_items(stat_code: str, limit: int = 100) -> dict[str, Any]:
    """ECOS 통계표의 실제 항목 코드, 그룹, 주기, 단위를 확인합니다."""
    return EcosAPI().items(stat_code, limit)

@mcp.tool()
def get_statistic_data(stat_code: str, cycle: str, start: str, end: str,
                       item_code1: str = '', item_code2: str = '',
                       item_code3: str = '', item_code4: str = '') -> dict[str, Any]:
    """ECOS 통계 시계열 조회. A=YYYY, Q=YYYYQn, M=YYYYMM, D=YYYYMMDD 등. 실제 항목 코드를 먼저 확인하세요."""
    return EcosAPI().series(stat_code, cycle, start, end, item_code1, item_code2, item_code3, item_code4)

@mcp.tool()
def get_key_statistics(limit: int = 30) -> dict[str, Any]:
    """ECOS 100대 주요 통계지표에서 최신값 후보를 확인합니다."""
    return EcosAPI().keywords(limit)

if __name__ == '__main__':
    mcp.run()
