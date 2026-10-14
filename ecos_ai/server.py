"""ECOS 전용 MCP 도구 서버."""
from typing import Any
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from ecos_ai.ecos import EcosAPI, EcosError

mcp = MCPServer('ECOS Statistics', instructions='모든 통계는 ECOS에서만 검색하고 조회합니다.')


def ecos_tool_call(action):
    """예측 가능한 ECOS 오류를 모델과 사용자에게 안전하게 알려줍니다."""
    try:
        return action()
    except EcosError as exc:
        # ECOS 연결/인증/기간 문제는 ToolError로 전달해 실제 원인을 표시
        raise ToolError(str(exc)) from None


@mcp.tool()
def find_statistics(keyword: str, limit: int = 20) -> dict[str, Any]:
    """한국은행 ECOS 통계표명 검색. 핵심어로 짧게 검색하고 실제 통계표 코드를 확보합니다."""
    return ecos_tool_call(lambda: EcosAPI().tables(keyword, limit))

@mcp.tool()
def get_statistic_items(stat_code: str, limit: int = 100) -> dict[str, Any]:
    """ECOS 통계표의 실제 항목 코드, 그룹, 주기, 단위를 확인합니다."""
    return ecos_tool_call(lambda: EcosAPI().items(stat_code, limit))

@mcp.tool()
def get_statistic_data(stat_code: str, cycle: str, start: str, end: str,
                       item_code1: str = '', item_code2: str = '',
                       item_code3: str = '', item_code4: str = '') -> dict[str, Any]:
    """ECOS 통계 시계열 조회. A=YYYY, Q=YYYYQn, M=YYYYMM, D=YYYYMMDD 등. 실제 항목 코드를 먼저 확인하세요."""
    return ecos_tool_call(lambda: EcosAPI().series(stat_code, cycle, start, end, item_code1, item_code2, item_code3, item_code4))

@mcp.tool()
def get_key_statistics(limit: int = 30) -> dict[str, Any]:
    """ECOS 100대 주요 통계지표에서 최신값 후보를 확인합니다."""
    return ecos_tool_call(lambda: EcosAPI().keywords(limit))

if __name__ == '__main__':
    mcp.run()
