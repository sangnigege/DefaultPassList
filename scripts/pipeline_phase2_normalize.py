#!/usr/bin/env python3
"""
Phase 2: Normalize all Phase 1 CSVs to unified schema.
Each source CSV → one normalized CSV with fields:
vendor, model, version, protocol, username, password, source_file, source_section, notes
"""
import os, sys, csv, json, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_config import SRC, PHASE1, PHASE2, UNIFIED_FIELDS
from pipeline_utils import (read_file_smart, has_cjk, norm_blank, fmt_note,
                            ensure_note, is_port_number)

os.makedirs(PHASE2, exist_ok=True)
manifest = {}

UNIFIED = UNIFIED_FIELDS  # ['vendor','model','version','protocol','username','password','source_file','source_section','notes']

def make_row(**kwargs):
    """Create a normalized row dict."""
    row = {f: '' for f in UNIFIED}
    for k, v in kwargs.items():
        if k in row:
            row[k] = str(v).strip() if v else ''
    return row

def write_normalized(fname, rows):
    path = os.path.join(PHASE2, fname)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=UNIFIED)
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {fname}: {len(rows)} rows")
    return len(rows)

def read_phase1_csv(fname):
    """Read a Phase 1 CSV, return (header, rows)."""
    path = os.path.join(PHASE1, fname)
    text, enc = read_file_smart(path)
    lines = text.split('\n')
    if lines and lines[0].startswith('﻿'):
        lines[0] = lines[0][1:]
    reader = csv.reader(lines)
    all_rows = [row for row in reader if any(c.strip() for c in row)]
    if not all_rows:
        return [], []
    return all_rows[0], all_rows[1:]

def skip_metadata_header(header, data):
    """If first row is metadata (starts with #, or is a title row followed by real header),
    return the real (header, data)."""
    if not data:
        return header, data
    # If header starts with #, it's a comment — real header is first data row
    if header[0].startswith('#'):
        return data[0], data[1:]
    # If header has garbled/empty first cell but data[0] has valid header text
    h0 = header[0].strip()
    if (not h0 or has_cjk(h0)) and data and data[0][0].strip() in ('服务名称','名称','厂商','设备','产品','应用名称','产品系列/名称','Manufacturer','Vendor'):
        return data[0], data[1:]
    # If header only has 1 column but data has more
    if len(header) == 1 and data and len(data[0]) > 1:
        return data[0], data[1:]
    return header, data

# ============================================================
# Normalizers for each source type
# ============================================================

def norm_passwords(header, data, src_name):
    """passwords.csv: Manufacturer, Model, Username, Password, Notes"""
    rows = []
    col = {h.lower().strip(): i for i, h in enumerate(header)}
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('manufacturer',0)] if len(d)>0 else '',
            model=d[col.get('model',1)] if len(d)>1 else '',
            username=d[col.get('username',2)] if len(d)>2 else '',
            password=d[col.get('password',3)] if len(d)>3 else '',
            notes=d[col.get('notes',4)] if len(d)>4 else '',
            source_file=src_name,
        ))
    return rows

def norm_ics_default(header, data, src_name):
    """ics-default-passwords.csv: Manufacturer,Model,Interface,Login,Password,Source,Comments"""
    rows = []
    col = {h.lower().strip(): i for i, h in enumerate(header)}
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('manufacturer',0)] if len(d)>0 else '',
            model=d[col.get('model',1)] if len(d)>1 else '',
            protocol=d[col.get('interface',2)] if len(d)>2 else '',
            username=d[col.get('login',3)] if len(d)>3 else '',
            password=d[col.get('password',4)] if len(d)>4 else '',
            notes=f"{d[col.get('source',5)] if len(d)>5 else ''} | {d[col.get('comments',6)] if len(d)>6 else ''}".strip(' |'),
            source_file=src_name,
        ))
    return rows

def norm_scada(header, data, src_name):
    """Scada_Password.csv: Vendor,Device,DefaultPassword,Port,DeviceType,Protocol,Source"""
    rows = []
    col = {h.lower().strip(): i for i, h in enumerate(header)}
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('vendor',0)] if len(d)>0 else '',
            model=d[col.get('device',1)] if len(d)>1 else '',
            protocol=f"{d[col.get('protocol',5)]}/{d[col.get('port',3)]}".strip('/') if len(d)>5 else '',
            password=d[col.get('defaultpassword',2)] if len(d)>2 else '',
            notes=f"[DeviceType: {d[col.get('devicetype',4)]}] {d[col.get('source',6)]}".strip() if len(d)>6 else '',
            source_file=src_name,
        ))
    return rows

def norm_defaultcreds(header, data, src_name):
    """DefaultCreds-Cheat-Sheet.csv: productvendor,username,password"""
    rows = []
    col = {h.lower().strip(): i for i, h in enumerate(header)}
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('productvendor',0)] if len(d)>0 else '',
            username=d[col.get('username',1)] if len(d)>1 else '',
            password=d[col.get('password',2)] if len(d)>2 else '',
            source_file=src_name,
        ))
    return rows

def norm_default_pw_list(header, data, src_name):
    """default_password_list.txt TSV: Vendor,Model,Version,Access Type,Username,PASSWORD,Privileges,Notes"""
    rows = []
    col = {h.lower().strip(): i for i, h in enumerate(header)}
    for d in data:
        notes = ''
        if len(d) > 6: notes += f"[Privileges: {d[6]}] " if d[6].strip() else ''
        if len(d) > 7: notes += d[7] if d[7].strip() else ''
        rows.append(make_row(
            vendor=d[col.get('vendor',0)] if len(d)>0 else '',
            model=d[col.get('model',1)] if len(d)>1 else '',
            version=d[col.get('version',2)] if len(d)>2 else '',
            protocol=d[col.get('access type',3)] if len(d)>3 else '',
            username=d[col.get('username',4)] if len(d)>4 else '',
            password=d[col.get('password',5)] if len(d)>5 else '',
            notes=notes.strip(),
            source_file=src_name,
        ))
    return rows

def norm_guoneiwai(header, data, src_name):
    """国内外设备默认口令整理.txt TSV: 厂商,型号,版本号,Username,Password"""
    rows = []
    col = {h.lower().strip(): i for i, h in enumerate(header)}
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('厂商',0)] if len(d)>0 else '',
            model=d[col.get('型号',1)] if len(d)>1 else '',
            version=d[col.get('版本号',2)] if len(d)>2 else '',
            username=d[col.get('username',3)] if len(d)>3 else '',
            password=d[col.get('password',4)] if len(d)>4 else '',
            source_file=src_name,
        ))
    return rows

def norm_default_cred(header, data, src_name):
    """default_cred.txt colon-sep: column_0 (vendor), column_1 (user), column_2 (pass)"""
    rows = []
    for d in data:
        rows.append(make_row(
            vendor=d[0] if len(d)>0 else '',
            username=d[1] if len(d)>1 else '',
            password=d[2] if len(d)>2 else '',
            notes=d[3] if len(d)>3 else '',
            source_file=src_name,
        ))
    return rows

def norm_yixie_shebei(header, data, src_name):
    """一些设备汇总.txt colon-sep: column_0 (vendor:model), column_1 (user), column_2 (pass)"""
    rows = []
    for d in data:
        vendor = d[0].strip() if len(d)>0 else ''
        model = ''
        if '服务器' in vendor or '路由' in vendor or '交换' in vendor or '防火墙' in vendor:
            pass  # vendor stays as-is
        rows.append(make_row(
            vendor=vendor, model=model,
            username=d[1] if len(d)>1 else '',
            password=d[2] if len(d)>2 else '',
            notes=d[3] if len(d)>3 else '',
            source_file=src_name,
        ))
    return rows

def norm_weblogic(header, data, src_name):
    """weblogic默认口令.txt slash-sep: username/password"""
    rows = []
    for d in data:
        rows.append(make_row(
            vendor='Oracle', model='WebLogic',
            username=d[0] if len(d)>0 else '',
            password=d[1] if len(d)>1 else '',
            source_file=src_name,
        ))
    return rows

def norm_fuwu(header, data, src_name):
    """常见服务默认口令2.csv GBK CSV: 服务名称,端口,默认账号,默认密码"""
    col = {h.strip(): i for i, h in enumerate(header)}
    rows = []
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('服务名称',0)] if len(d)>0 else '',
            protocol=d[col.get('端口',1)] if len(d)>1 else '',
            username=d[col.get('默认账号',2)] if len(d)>2 else '',
            password=d[col.get('默认密码',3)] if len(d)>3 else '',
            source_file=src_name,
        ))
    return rows

def norm_shebei(header, data, src_name):
    """常见设备默认口令2.csv GBK CSV: 名称,默认账号,默认密码,地址"""
    col = {h.strip(): i for i, h in enumerate(header)}
    rows = []
    for d in data:
        rows.append(make_row(
            vendor=d[col.get('名称',0)] if len(d)>0 else '',
            username=d[col.get('默认账号',1)] if len(d)>1 else '',
            password=d[col.get('默认密码',2)] if len(d)>2 else '',
            notes=d[col.get('地址',3)] if len(d)>3 else '',
            source_file=src_name,
        ))
    return rows

def norm_yaoyao(header, data, src_name):
    """遥遥领先设备口令.csv: 产品系列/型号,版本号,BootROM(密码),Console(用户名/密码),Telnet(用户名/密码),Web(用户名/密码),备注"""
    col = {h.strip(): i for i, h in enumerate(header)}
    rows = []
    for d in data:
        if len(d) < 6: continue
        model = d[col.get('产品系列/型号',0)].strip() if len(d)>0 else ''
        version = d[col.get('版本号',1)].strip() if len(d)>1 else ''
        notes_base = d[col.get('备注',6)].strip() if len(d)>6 else ''

        # Each protocol column: may contain "user/pass", just a password, "NA", or descriptive text
        protocol_cols = [
            ('BootROM', 2),
            ('Console', 3),
            ('Telnet', 4),
            ('Web', 5),
        ]
        for proto_name, col_idx in protocol_cols:
            if col_idx >= len(d): continue
            val = d[col_idx].strip()
            if not val or val in ('NA', '-', '—', '无', '不支持Telnet管理。', '不支持', '不支持Telnet管理'):
                # No credential available — note it
                if val and '不支持' in val:
                    rows.append(make_row(
                        vendor='华为', model=model, version=version,
                        protocol=proto_name, notes=ensure_note(notes_base, f'[{proto_name}: {val}]'),
                        source_file=src_name,
                    ))
                continue

            # Check for "没有缺省" pattern
            if '没有缺省' in val:
                rows.append(make_row(
                    vendor='华为', model=model, version=version,
                    protocol=proto_name, notes=ensure_note(notes_base, f'[{proto_name}: {val}]'),
                    source_file=src_name,
                ))
                continue

            # Multi-line credentials? Split on newline
            sub_vals = val.split('\n') if '\n' in val else [val]
            for sv in sub_vals:
                sv = sv.strip()
                if not sv: continue
                if '/' in sv and not sv.startswith('http'):
                    parts = sv.split('/', 1)
                    rows.append(make_row(
                        vendor='华为', model=model, version=version,
                        protocol=proto_name,
                        username=parts[0].strip(),
                        password=parts[1].strip() if len(parts)>1 else '',
                        notes=notes_base,
                        source_file=src_name,
                    ))
                else:
                    # Just a password (like BootROM)
                    rows.append(make_row(
                        vendor='华为', model=model, version=version,
                        protocol=proto_name,
                        password=sv,
                        notes=notes_base,
                        source_file=src_name,
                    ))
    return rows

def norm_narrative(header, data, src_name):
    """Narrative files: section_path, line_number, line_text"""
    rows = []
    col = {h.strip(): i for i, h in enumerate(header)}
    for d in data:
        section = d[col.get('section_path',0)].strip() if len(d)>0 else ''
        line = d[col.get('line_text',2)].strip() if len(d)>2 else ''
        if not line: continue

        # Try to extract credential patterns from the line
        # Pattern: 用户名[:：]\s*(\S+).*?密码[:：]\s*(\S+)
        m = re.search(r'用户名[：:]\s*(\S+).*?密码[：:]\s*(\S+)', line)
        if m:
            # Extract vendor from section
            vendor = section.split(' > ')[-1] if section else ''
            if len(vendor) > 30: vendor = vendor[:30]
            rows.append(make_row(
                vendor=vendor,
                username=m.group(1),
                password=m.group(2),
                source_file=src_name, source_section=section,
                notes=f"[original_line: {line[:150]}]",
            ))
            continue

        # Pattern: user/pass (slash-separated in line)
        slashes = re.findall(r'(\w[\w.-]{1,40})/(\S{1,40})', line)
        if slashes:
            vendor = section.split(' > ')[-1] if section else ''
            for u, p in slashes:
                if u.lower() in ('用户名', '密码', '默认', 'http'): continue
                rows.append(make_row(
                    vendor=vendor,
                    username=u, password=p,
                    source_file=src_name, source_section=section,
                    notes=f"[original_line: {line[:150]}]",
                ))
            continue

        # If no credential pattern found, still keep the line as a note
        # (preserves context even if no extractable credential)
        rows.append(make_row(
            vendor=section.split(' > ')[-1] if section else '',
            source_file=src_name, source_section=section,
            notes=f"[context_line: {line[:200]}]",
        ))
    return rows

def norm_gbk_txt(header, data, src_name):
    """GBK TXT semi-structured: section_context, line_number, line_text"""
    rows = []
    col = {h.strip(): i for i, h in enumerate(header)}
    section = ''
    for d in data:
        ctx = d[col.get('section_context',0)].strip() if len(d)>0 else ''
        line = d[col.get('line_text',2)].strip() if len(d)>2 else ''
        if not line: continue
        if ctx: section = ctx

        # Try multiple credential patterns
        found = False

        # Pattern: 用户名[:：]\s*(\S+) and 密码[:：]\s*(\S+) on same line
        m = re.search(r'用户名[：:]\s*(\S+)', line)
        m2 = re.search(r'密码[：:]\s*(\S+)', line)
        if m and m2:
            rows.append(make_row(
                vendor=section if section else '',
                username=m.group(1), password=m2.group(1),
                source_file=src_name, source_section=section,
                notes=f"[original_line: {line[:150]}]",
            ))
            found = True

        if not found:
            # Pattern: username[:：](\S+)password[:：](\S+)
            m = re.search(r'username[:：]\s*(\S+?)\s*password[:：]\s*(\S+)', line, re.IGNORECASE)
            if m:
                rows.append(make_row(
                    vendor=section if section else '',
                    username=m.group(1), password=m.group(2),
                    source_file=src_name, source_section=section,
                    notes=f"[original_line: {line[:150]}]",
                ))
                found = True

        if not found:
            # Pattern: 用户名和密码都?为[:：]\s*(\S+)
            m = re.search(r'用户名和密码都?为[：:]\s*(\S+)', line)
            if m:
                rows.append(make_row(
                    vendor=section if section else '',
                    username=m.group(1), password=m.group(1),
                    source_file=src_name, source_section=section,
                    notes=f"[original_line: {line[:150]}]",
                ))
                found = True

        # Always keep original as context
        if not found:
            rows.append(make_row(
                vendor=section if section else '',
                source_file=src_name, source_section=section,
                notes=f"[context_line: {line[:200]}]",
            ))
    return rows

def norm_xlsx_simple(header, data, src_name):
    """Generic XLSX with standard columns — map directly."""
    rows = []
    # Try to auto-detect column mapping
    col_map = {}
    for i, h in enumerate(header):
        h_clean = h.strip().lower()
        if any(k in h_clean for k in ['厂商', '设备', '产品', '应用', '名称', 'vendor', 'product', 'type', 'manufacturer', '品牌', '系统']):
            col_map['vendor'] = i
        if any(k in h_clean for k in ['型号', 'model', '版本']):
            col_map['model'] = i
        if any(k in h_clean for k in ['默认账号', '默认用户', '账号', '用户名', '登录', 'user', 'username', 'login', 'name']):
            col_map.setdefault('username', i)
        if any(k in h_clean for k in ['默认密码', '密码', 'password', 'passwd', 'pwd']):
            col_map.setdefault('password', i)
        if any(k in h_clean for k in ['端口', 'port', '协议', 'protocol', 'interface', 'access']):
            col_map.setdefault('protocol', i)
        if any(k in h_clean for k in ['地址', '备注', '说明', 'notes', 'comment', 'url', '来源', 'source']):
            col_map.setdefault('notes', i)

    for d in data:
        rows.append(make_row(
            vendor=d[col_map['vendor']] if 'vendor' in col_map and len(d)>col_map['vendor'] else '',
            model=d[col_map['model']] if 'model' in col_map and len(d)>col_map['model'] else '',
            username=d[col_map['username']] if 'username' in col_map and len(d)>col_map['username'] else '',
            password=d[col_map['password']] if 'password' in col_map and len(d)>col_map['password'] else '',
            protocol=d[col_map['protocol']] if 'protocol' in col_map and len(d)>col_map['protocol'] else '',
            notes=d[col_map['notes']] if 'notes' in col_map and len(d)>col_map['notes'] else '',
            source_file=src_name,
        ))
    return rows

def norm_huawei_speedref(header, data, src_name):
    """华为安全产品默认用户名密码速查表.xlsx: 产品系列/名称,版本号,BootROM(密码),Console(用户名/密码),Telnet(用户名/密码),Web(用户名/密码),备注
    Also handles the embedded FusionManager sub-table."""
    # Same logic as norm_yaoyao
    col = {h.strip(): i for i, h in enumerate(header)}
    rows = []

    for d in data:
        if len(d) < 6: continue

        # Detect FusionManager sub-table start
        d0 = d[0].strip() if len(d)>0 else ''
        if '常用登录帐户' in d0 or 'Fusion' in d0 or '登录帐户' in d0:
            # This marks the start of a different sub-table format
            continue

        model = d[col.get('产品系列/名称',0)].strip() if len(d)>0 else ''
        version = d[col.get('版本号',1)].strip() if len(d)>1 else ''
        notes_base = d[col.get('备注',6)].strip() if len(d)>6 else ''

        protocol_cols = [
            ('BootROM', 2), ('Console', 3), ('Telnet', 4), ('Web', 5),
        ]
        for proto_name, col_idx in protocol_cols:
            if col_idx >= len(d): continue
            val = d[col_idx].strip()
            if not val or val in ('NA', '-', '—', '无', '不支持Telnet管理。', '不支持', '不支持Telnet管理', '---'):
                if val and ('不支持' in val or '没有缺省' in val):
                    rows.append(make_row(
                        vendor='华为', model=model, version=version,
                        protocol=proto_name,
                        notes=ensure_note(notes_base, f'[{proto_name}: {val}]'),
                        source_file=src_name,
                    ))
                continue

            if '没有缺省' in val:
                rows.append(make_row(
                    vendor='华为', model=model, version=version,
                    protocol=proto_name,
                    notes=ensure_note(notes_base, f'[{proto_name}: {val}]'),
                    source_file=src_name,
                ))
                continue

            sub_vals = val.split('\n') if '\n' in val else [val]
            for sv in sub_vals:
                sv = sv.strip()
                if not sv: continue
                if '/' in sv and not sv.startswith('http'):
                    parts = sv.split('/', 1)
                    rows.append(make_row(
                        vendor='华为', model=model, version=version,
                        protocol=proto_name,
                        username=parts[0].strip(),
                        password=parts[1].strip() if len(parts)>1 else '',
                        notes=notes_base,
                        source_file=src_name,
                    ))
                else:
                    rows.append(make_row(
                        vendor='华为', model=model, version=version,
                        protocol=proto_name,
                        password=sv,
                        notes=notes_base,
                        source_file=src_name,
                    ))
    return rows

def norm_netsec_product2(header, data, src_name):
    """常见网络安全产品口令2.xlsx: type, name, passwd (10,640 rows)
    Many rows have protocol labels like 'STelnet登录/用户名: admin' in the 'name' column.
    """
    col = {h.strip(): i for i, h in enumerate(header)}
    rows = []

    for d in data:
        if len(d) < 3: continue
        vendor_type = d[col.get('type',0)].strip() if len(d)>0 else ''
        name_field = d[col.get('name',1)].strip() if len(d)>1 else ''
        pass_field = d[col.get('passwd',2)].strip() if len(d)>2 else ''

        if not vendor_type and not name_field: continue

        # Check if name_field contains protocol labels like 'STelnet登录/用户名: admin'
        user_match = re.match(r'(\S+登录)/(?:用户名|密码)[：:]\s*(\S+)', name_field)
        pass_match = re.match(r'(\S+登录)/(?:用户名|密码)[：:]\s*(\S+)', pass_field)

        if user_match or pass_match:
            # Extract protocol from the label
            user_pairs = re.findall(r'(\S+登录)/(?:用户名|密码)[：:]\s*(\S+)', name_field)
            pass_pairs = re.findall(r'(\S+登录)/(?:用户名|密码)[：:]\s*(\S+)', pass_field)

            protocols = {}
            for proto, val in user_pairs:
                proto_clean = proto.replace('登录', '').strip()
                if val != '-':
                    protocols[proto_clean] = {'user': val, 'pass': ''}
            for proto, val in pass_pairs:
                proto_clean = proto.replace('登录', '').strip()
                if val != '-':
                    if proto_clean in protocols:
                        protocols[proto_clean]['pass'] = val
                    else:
                        protocols[proto_clean] = {'user': '', 'pass': val}

            # Parse vendor from vendor_type field
            vendor = vendor_type
            model = ''
            if '华为-' in vendor_type:
                vendor = '华为'
                model = vendor_type.replace('华为-', '')
            elif vendor_type.startswith('华为'):
                vendor = '华为'
                model = vendor_type[2:]

            for proto, cred in protocols.items():
                if cred['user'] or cred['pass']:
                    rows.append(make_row(
                        vendor=vendor, model=model,
                        protocol=proto,
                        username=cred['user'], password=cred['pass'],
                        source_file=src_name,
                    ))
        else:
            # Simple format: vendor_type is vendor/description, name_field is username, pass_field is password
            vendor = vendor_type
            model = ''
            if '-' in vendor_type and not vendor_type.startswith(('华为-', '深信服', '天融信', '绿盟', '启明', '山石', '网神', '网御', '迪普', '迈普')):
                parts = vendor_type.split('-', 1)
                vendor = parts[0]
                model = parts[1] if len(parts) > 1 else ''

            rows.append(make_row(
                vendor=vendor, model=model,
                username=name_field, password=pass_field,
                source_file=src_name,
            ))
    return rows

def norm_des_accounts(header, data, src_name):
    """des账号和弱口令汇总v6.16.xlsx: 应用名称, [port/context], 密码, 备注
    Column 2 may contain port numbers or context. Password may contain 'user/pass' pairs.
    """
    col = {h.strip(): i for i, h in enumerate(header)}
    rows = []
    for d in data:
        if len(d) < 3: continue
        vendor = d[0].strip() if len(d)>0 else ''
        col2 = d[1].strip() if len(d)>1 else ''
        pass_raw = d[2].strip() if len(d)>2 else ''
        notes_raw = d[3].strip() if len(d)>3 else ''

        # Detect port number in col2
        if col2.isdigit() and 2 <= len(col2) <= 5:
            notes_raw = ensure_note(notes_raw, fmt_note('port', col2))
            col2 = ''

        # Handle multi-cred in password field
        # Pattern: "user/pass | user2/pass2" or "user/pass"
        if '|' in pass_raw:
            parts = [p.strip() for p in pass_raw.split('|')]
            for i, part in enumerate(parts):
                if '/' in part:
                    up = part.split('/', 1)
                    if len(up) == 2:
                        note = notes_raw
                        if i > 0:
                            note = ensure_note(note, f"[additional_cred: {'|'.join(parts[1:])}]")
                        rows.append(make_row(
                            vendor=vendor, username=up[0].strip(), password=up[1].strip(),
                            notes=note, source_file=src_name,
                        ))
                        break  # Take first, rest in notes
                else:
                    rows.append(make_row(
                        vendor=vendor, username=col2, password=part,
                        notes=notes_raw, source_file=src_name,
                    ))
        elif '/' in pass_raw and len(pass_raw) < 60 and not pass_raw.startswith('http'):
            parts = pass_raw.split('/', 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                rows.append(make_row(
                    vendor=vendor, username=parts[0].strip(), password=parts[1].strip(),
                    notes=notes_raw, source_file=src_name,
                ))
        elif ' ' in pass_raw and (':' in pass_raw or '/' in pass_raw) and len(pass_raw) < 80:
            # Multi-cred separated by space
            space_parts = pass_raw.split()
            sep = ':' if ':' in space_parts[0] else '/'
            up = space_parts[0].split(sep, 1)
            if len(up) == 2:
                rows.append(make_row(
                    vendor=vendor, username=up[0].strip(), password=up[1].strip(),
                    notes=ensure_note(notes_raw, f"[additional: {' '.join(space_parts[1:])}]"),
                    source_file=src_name,
                ))
            else:
                rows.append(make_row(
                    vendor=vendor, username=col2, password=pass_raw,
                    notes=notes_raw, source_file=src_name,
                ))
        else:
            rows.append(make_row(
                vendor=vendor, username=col2, password=pass_raw,
                notes=notes_raw, source_file=src_name,
            ))
    return rows

# ============================================================
# MAIN
# ============================================================
print("=" * 60)
print("PHASE 2: Normalize to unified schema")
print("=" * 60)

# Mapping: Phase 1 filename pattern → normalizer function
source_handlers = {
    'passwords': norm_passwords,
    'ics_default': norm_ics_default,
    'scada': norm_scada,
    'defaultcreds': norm_defaultcreds,
    'default_pw_list': norm_default_pw_list,
    'guoneiwai_1': norm_guoneiwai,
    'guoneiwai_2': norm_guoneiwai,
    'default_cred': norm_default_cred,
    'yixie_shebei': norm_yixie_shebei,
    'weblogic': norm_weblogic,
    'fuwu': norm_fuwu,
    'shebei': norm_shebei,
    'yaoyao': norm_yaoyao,
    'web_systems': norm_narrative,
    'net_sec_devices': norm_narrative,
    'ruokou_md': norm_narrative,
    'fanghuoqiang': norm_gbk_txt,
    'luyouqi': norm_gbk_txt,
    'des账号和弱口令汇总v6.16': norm_des_accounts,
    '华为产品弱口令': norm_xlsx_simple,
    '华为产品弱口令2': norm_xlsx_simple,
    '华为安全产品默认用户名密码速查表': norm_huawei_speedref,
    '华为安全产品默认用户名密码速查表2': norm_huawei_speedref,
    '常见安全产品系统默认口令': norm_xlsx_simple,
    '常见安全产品系统默认口令清单': norm_xlsx_simple,
    '常见安全产品系统默认口令清单2': norm_xlsx_simple,
    '常见网络安全产品口令': norm_xlsx_simple,
    '常见网络安全产品口令2': norm_netsec_product2,
    # External sources (new)
    'totalpass': norm_xlsx_simple,
    'defaultpassword': norm_xlsx_simple,
    'framedefaultpass': norm_xlsx_simple,
    'userpass_dict': norm_xlsx_simple,
    'fwpass': norm_xlsx_simple,
}

total_normalized = 0
for fname in sorted(os.listdir(PHASE1)):
    if fname == 'phase1_manifest.json': continue
    if not fname.endswith('.csv'): continue

    # Extract label from filename (remove number prefix and extension)
    label = re.sub(r'^\d+_', '', fname).replace('.csv', '')

    header, data = read_phase1_csv(fname)
    if not data:
        print(f"  SKIP {fname}: no data")
        continue

    # Fix metadata headers
    header, data = skip_metadata_header(header, data)

    # Find matching handler
    handler = None
    for key, func in source_handlers.items():
        if key in label:
            handler = func
            break

    if handler is None:
        print(f"  WARN {fname} ({label}): no handler found, using generic")
        handler = norm_xlsx_simple

    print(f"\n{fname} ({label}) — {len(data)} rows input")
    # Show input header
    print(f"  Input header: {header[:6]}")

    rows = handler(header, data, label)
    n = write_normalized(f"{fname.replace('.csv','')}_normalized.csv", rows)
    manifest[label] = {'phase1_rows': len(data), 'phase2_rows': n, 'handler': handler.__name__}
    total_normalized += n

print(f"\n{'='*60}")
print(f"Total normalized rows (all sources): {total_normalized}")

# Verification
print(f"\n{'='*60}")
print("PHASE 2 VERIFICATION")
for label, info in sorted(manifest.items()):
    p1 = info['phase1_rows']
    p2 = info['phase2_rows']
    ratio = p2 / p1 if p1 > 0 else 0
    flag = "✅" if p2 >= p1 else "❌ ROW LOSS!"
    print(f"  {flag} {label}: {p1}→{p2} rows ({ratio:.1f}x) [{info['handler']}]")

# Save manifest
import json as j
manifest_path = os.path.join(PHASE2, 'phase2_manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    j.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"\nManifest: {manifest_path}")
print("Phase 2 complete!")
