def mainboard_non_st_codes(rows, limit=0):
    codes = []
    for row in rows:
        code = str(row.get("ts_code") or "").strip().upper()
        symbol = str(row.get("symbol") or "").strip()
        name = str(row.get("name") or "")
        if row.get("market") == "主板" and row.get("list_status") == "L" and symbol.isdigit() and "." in code and "ST" not in name.upper() and "退" not in name and code.endswith((".SH", ".SZ")):
            codes.append(code)
    return codes[:limit] if limit > 0 else codes


def load_mainboard_non_st_codes(repository, limit=0):
    return mainboard_non_st_codes(repository.securities(market="主板"), limit)
