#!/usr/bin/env python3
"""
Phase 1: Convert all raw source files to CSVs.
Faithful conversion - no field remapping, no deletion.
Each source file → one CSV in output/phase1_converted/
"""
import os, sys, csv, hashlib, json, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_config import SRC, RAW, PHASE1
from pipeline_utils import read_file_smart, has_cjk, detect_encoding

os.makedirs(PHASE1, exist_ok=True)
manifest = {}
counter = 0

def next_id():
    global counter
    counter += 1
    return f"{counter:02d}"

def log_skip(name, reason):
    print(f"  SKIP: {name} — {reason}")

def write_csv(fname, rows, cols=None):
    """Write rows to CSV. rows is list of list or list of dict."""
    path = os.path.join(PHASE1, fname)
    if not rows:
        print(f"  WARN: {fname} — 0 rows written")
        return 0
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        if isinstance(rows[0], dict):
            if cols is None:
                cols = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)
        else:
            if cols is None:
                cols = [f"col_{i}" for i in range(len(rows[0]))]
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
    print(f"  -> {fname}: {len(rows)} rows, {len(cols)} cols")
    return len(rows)

# ============================================================
# 1. Standard CSVs (UTF-8) — copy directly
# ============================================================
def convert_standard_csv(src_path, out_name, label):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    lines = text.split('\n')
    # Remove BOM if present
    if lines and lines[0].startswith('﻿'):
        lines[0] = lines[0][1:]
    reader = csv.reader(lines)
    rows = [row for row in reader if any(c.strip() for c in row)]
    if not rows:
        log_skip(label, "no data rows")
        return
    header = rows[0]
    data = rows[1:]
    n = write_csv(out_name, data, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'csv_utf8',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 2. Tab-separated TXT
# ============================================================
def convert_tsv(src_path, out_name, label, skip_lines=0):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    lines = text.split('\n')
    # Skip preamble lines
    data_lines = lines[skip_lines:]
    # Find header row
    header_idx = None
    for i, line in enumerate(data_lines):
        if '\t' in line and ('Vendor' in line or 'vendor' in line or '厂商' in line or 'Manufacturer' in line):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0
    header = [c.strip() for c in data_lines[header_idx].split('\t')]
    rows = []
    for line in data_lines[header_idx+1:]:
        cols = [c.strip() for c in line.split('\t')]
        if any(c for c in cols):
            rows.append(cols)
    # Pad short rows to match header length
    for i, row in enumerate(rows):
        while len(row) < len(header):
            row.append('')
    n = write_csv(out_name, rows, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'tsv',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 3. Colon-separated TXT
# ============================================================
def convert_colon_sep(src_path, out_name, label, has_header=False):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    header = ['column_0', 'column_1', 'column_2', 'notes']
    rows = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('Default Password') or line.startswith('2008'):
            continue
        parts = line.split(':', 2)
        if len(parts) >= 2:
            c0 = parts[0].strip()
            c1 = parts[1].strip() if len(parts) > 1 else ''
            c2 = parts[2].strip() if len(parts) > 2 else ''
            n = ''
            if len(parts) > 3:
                n = ':'.join(parts[3:]).strip()
            rows.append([c0, c1, c2, n])
    n = write_csv(out_name, rows, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'colon_sep',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 4. Slash-separated
# ============================================================
def convert_slash_sep(src_path, out_name, label):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    header = ['username', 'password']
    rows = []
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        parts = line.split('/')
        if len(parts) >= 2:
            rows.append([parts[0].strip(), parts[1].strip()])
    n = write_csv(out_name, rows, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'slash_sep',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 5. GBK-encoded CSVs
# ============================================================
def convert_gbk_csv(src_path, out_name, label):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    lines = text.split('\n')
    # Skip BOM
    if lines and lines[0].startswith('﻿'):
        lines[0] = lines[0][1:]
    reader = csv.reader(lines)
    rows = [row for row in reader if any(c.strip() for c in row)]
    if not rows:
        log_skip(label, "no data")
        return
    header = rows[0]
    data = rows[1:]
    n = write_csv(out_name, data, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'gbk_csv',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 6. Narrative/prose files — preserve section + line structure
# ============================================================
def convert_narrative(src_path, out_name, label, is_markdown=False):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    header = ['section_path', 'line_number', 'line_text']
    rows = []
    section_stack = []
    for i, line in enumerate(text.split('\n')):
        stripped = line.strip()
        if not stripped: continue
        if is_markdown:
            m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                while len(section_stack) >= level:
                    section_stack.pop()
                section_stack.append(title)
                continue
        else:
            # Check for number-prefixed section headers: "1、xxx" or "1.xxx"
            m = re.match(r'^(\d+)[、.．]\s*(.+)$', stripped)
            if m and len(stripped) < 40:
                level = int(m.group(1))
                title = stripped
                while len(section_stack) >= level:
                    section_stack.pop()
                section_stack.append(title)
                continue
        section = ' > '.join(section_stack) if section_stack else ''
        rows.append([section, i+1, stripped])
    n = write_csv(out_name, rows, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'narrative',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 7. GBK-encoded TXT (semi-structured)
# ============================================================
def convert_gbk_txt(src_path, out_name, label):
    text, enc = read_file_smart(src_path)
    if not text.strip():
        log_skip(label, "empty")
        return
    header = ['section_context', 'line_number', 'line_text']
    rows = []
    section = ''
    for i, line in enumerate(text.split('\n')):
        stripped = line.strip()
        if not stripped: continue
        # Heuristic: short lines without colons might be section headers
        if len(stripped) < 30 and ('防火墙' in stripped or '路由' in stripped or '交换' in stripped):
            section = stripped
        rows.append([section, i+1, stripped])
    n = write_csv(out_name, rows, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'gbk_txt',
                       'encoding': enc, 'rows': n, 'cols': header}

# ============================================================
# 8. XLSX files
# ============================================================
def md5_file(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

processed_xlsx_md5s = set()

def convert_xlsx(src_path, out_name, label):
    try:
        import openpyxl
    except ImportError:
        os.system(f"{sys.executable} -m pip install openpyxl -q")
        import openpyxl

    # Check for MD5 duplicates
    md5 = md5_file(src_path)
    if md5 in processed_xlsx_md5s:
        log_skip(label, f"duplicate XLSX (MD5={md5[:8]}...)")
        return
    processed_xlsx_md5s.add(md5)

    wb = openpyxl.load_workbook(src_path, data_only=True)
    all_rows = []
    for sn in wb.sheetnames:
        ws = wb[sn]
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
            cleaned = [str(c).strip() if c is not None else '' for c in row]
            if any(c for c in cleaned):
                all_rows.append(cleaned)

    if not all_rows:
        log_skip(label, "no data")
        return

    # Determine header — first row that doesn't look like data
    header = all_rows[0]
    # Clean header names
    header = [h.replace('\n', ' ').replace('\r', '') for h in header]
    data = all_rows[1:]
    # Pad short rows
    for row in data:
        while len(row) < len(header):
            row.append('')

    n = write_csv(out_name, data, header)
    manifest[label] = {'source': os.path.basename(src_path), 'format': 'xlsx',
                       'sheets': wb.sheetnames, 'rows': n, 'cols': header}

# ============================================================
# MAIN: Process all sources
# ============================================================
print("=" * 60)
print("PHASE 1: Convert all sources to raw CSV")
print("=" * 60)

# 1. Standard CSVs
print("\n— Standard CSVs —")
convert_standard_csv(os.path.join(RAW, 'passwords.csv'), f'{next_id()}_passwords.csv', 'passwords')
convert_standard_csv(os.path.join(RAW, 'ics-default-passwords.csv'), f'{next_id()}_ics_default.csv', 'ics_default')
convert_standard_csv(os.path.join(RAW, 'Scada_Password.csv'), f'{next_id()}_scada.csv', 'scada')
convert_standard_csv(os.path.join(RAW, 'DefaultCreds-cheat-sheet-main', 'DefaultCreds-Cheat-Sheet.csv'),
                     f'{next_id()}_defaultcreds.csv', 'defaultcreds')

# 2. Tab-separated TXTs
print("\n— Tab-separated TXTs —")
convert_tsv(os.path.join(RAW, 'default_password_list.txt'), f'{next_id()}_default_pw_list.csv', 'default_pw_list', skip_lines=2)
convert_tsv(os.path.join(RAW, '国内外设备默认口令整理.txt'), f'{next_id()}_guoneiwai_1.csv', 'guoneiwai_1')
convert_tsv(os.path.join(RAW, '国内外设备默认口令整理2.txt'), f'{next_id()}_guoneiwai_2.csv', 'guoneiwai_2')

# 3. Colon-separated
print("\n— Colon-separated TXTs —")
convert_colon_sep(os.path.join(RAW, 'default_cred.txt'), f'{next_id()}_default_cred.csv', 'default_cred')
convert_colon_sep(os.path.join(RAW, '一些设备汇总.txt'), f'{next_id()}_yixie_shebei.csv', 'yixie_shebei')

# 4. Slash-separated
print("\n— Slash-separated —")
convert_slash_sep(os.path.join(RAW, 'weblogic默认口令.txt'), f'{next_id()}_weblogic.csv', 'weblogic')

# 5. GBK CSVs
print("\n— GBK CSVs —")
convert_gbk_csv(os.path.join(RAW, '常见服务默认口令2.csv'), f'{next_id()}_fuwu.csv', 'fuwu')
convert_gbk_csv(os.path.join(RAW, '常见设备默认口令2.csv'), f'{next_id()}_shebei.csv', 'shebei')
convert_gbk_csv(os.path.join(RAW, '遥遥领先设备口令.csv'), f'{next_id()}_yaoyao.csv', 'yaoyao')

# 6. Narrative/prose
print("\n— Narrative files —")
convert_narrative(os.path.join(RAW, '常见web系统默认口令总结.txt'), f'{next_id()}_web_systems.csv', 'web_systems')
convert_narrative(os.path.join(RAW, '常见网络及安全设备默认口令.txt'), f'{next_id()}_net_sec_devices.csv', 'net_sec_devices')
convert_narrative(os.path.join(RAW, '常见设备默认弱口令.md'), f'{next_id()}_ruokou_md.csv', 'ruokou_md', is_markdown=True)

# 7. GBK TXTs
print("\n— GBK TXTs —")
convert_gbk_txt(os.path.join(RAW, '国内防火墙默认密码.txt'), f'{next_id()}_fanghuoqiang.csv', 'fanghuoqiang')
convert_gbk_txt(os.path.join(RAW, '路由器默认密码.txt'), f'{next_id()}_luyouqi.csv', 'luyouqi')

# 8. XLSX files
print("\n— XLSX files —")
for fname in sorted(os.listdir(RAW)):
    if fname.endswith('.xlsx'):
        base = fname.replace('.xlsx', '')
        convert_xlsx(os.path.join(RAW, fname), f'{next_id()}_{base}.csv', base)

# 9. Empty file
huawei_path = os.path.join(RAW, 'Huawei华为.txt')
if os.path.exists(huawei_path) and os.path.getsize(huawei_path) == 0:
    log_skip('Huawei华为.txt', 'empty file (0 bytes)')

# ============================================================
# Verification
# ============================================================
print("\n" + "=" * 60)
print("PHASE 1 VERIFICATION")
print("=" * 60)

errors = 0
for label, info in sorted(manifest.items()):
    rows = info['rows']
    enc = info.get('encoding', '?')
    fmt = info['format']
    if rows < 1:
        print(f"  ❌ {label}: 0 rows!")
        errors += 1
    else:
        # Check encoding for GBK sources
        if fmt in ('gbk_csv', 'gbk_txt') and enc == 'utf-8':
            # GBK files decoded as UTF-8 means possible garbled content
            print(f"  ⚠ {label}: format={fmt} but detected as utf-8, {rows} rows")
        else:
            print(f"  ✅ {label}: {rows} rows, {enc}, {fmt}")

# Spot-check: Print first 3 rows of a few representative files
print("\n— Spot-check samples —")
sample_files = [f for f in sorted(os.listdir(PHASE1)) if f.endswith('.csv')]
for sf in sample_files[:5] + sample_files[10:12]:
    path = os.path.join(PHASE1, sf)
    with open(path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()[:4]
    print(f"\n  {sf}:")
    for line in lines:
        print(f"    {line.rstrip()[:150]}")

# Save manifest
manifest_path = os.path.join(PHASE1, 'phase1_manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"\nManifest: {manifest_path}")
print(f"Total sources processed: {len(manifest)}")
print(f"Errors: {errors}")
print("Phase 1 complete!")
