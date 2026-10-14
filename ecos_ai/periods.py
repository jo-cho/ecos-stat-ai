"""ECOS 주기별 날짜 변환."""
import re
import pandas as pd

def to_timestamp(value: str, cycle: str) -> pd.Timestamp | None:
    # 주기별 날짜를 표준 시간 인덱스로 변환
    value = str(value).strip()
    try:
        if cycle == 'A' and re.fullmatch(r'\d{4}', value):
            return pd.Timestamp(int(value), 1, 1)
        if cycle == 'M' and re.fullmatch(r'\d{6}', value):
            return pd.Timestamp(int(value[:4]), int(value[4:]), 1)
        if cycle == 'D' and re.fullmatch(r'\d{8}', value):
            return pd.Timestamp(int(value[:4]), int(value[4:6]), int(value[6:]))
        if cycle == 'Q' and re.fullmatch(r'\d{4}Q[1-4]', value):
            return pd.Timestamp(int(value[:4]), (int(value[-1]) - 1) * 3 + 1, 1)
        if cycle == 'S' and re.fullmatch(r'\d{4}S[12]', value):
            return pd.Timestamp(int(value[:4]), 1 if value[-1] == '1' else 7, 1)
        if cycle == 'SM' and re.fullmatch(r'\d{6}S[12]', value):
            return pd.Timestamp(int(value[:4]), int(value[4:6]), 1 if value[-1] == '1' else 16)
    except (ValueError, TypeError):
        return None
    return None

