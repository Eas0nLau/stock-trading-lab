from pathlib import Path


def _标准化代码(code):
    code_text = str(code).strip()
    if code_text.isdigit() and len(code_text) < 6:
        return code_text.zfill(6)
    return code_text


def _解析ini项(item):
    if isinstance(item, dict):
        code = None
        name = None
        for code_key in ['code', '股票代码', 'ts_code', 'symbol', '板块代码']:
            if code_key in item:
                code = item[code_key]
                break
        for name_key in ['name', '股票名称', 'stock_name', '板块名称']:
            if name_key in item:
                name = item[name_key]
                break
        if code is not None and name is not None:
            return _标准化代码(code), str(name).strip()

    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return _标准化代码(item[0]), str(item[1]).strip()

    raise ValueError(f"无法解析ini项: {item}")


def 写入列表ini(items, output_dir, file_name):
    item_list = list(items)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_name = str(file_name)
    if not file_name.endswith('.ini'):
        file_name = f"{file_name}.ini"
    ini_path = output_path / file_name

    lines = []
    for index, item in enumerate(item_list, start=1):
        code, name = _解析ini项(item)
        lines.append(f"{index} = {code},{name}")

    with ini_path.open('w', encoding='utf-8') as file:
        file.write('\n'.join(lines) + '\n')

    return ini_path
