#!/usr/bin/env python3
"""
Extract default password data from 5 external repos into CSV files.
Output goes to raw_archive/external/ for Phase 1 ingestion.
"""
import os, sys, csv, re, yaml, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_utils import read_file_smart, has_cjk

SRC = "/home/matrix/work/Common-device-default-password-main"
EXT = os.path.join(SRC, "external_repos")
OUT = os.path.join(SRC, "raw_archive", "external")
os.makedirs(OUT, exist_ok=True)

counter = 0
def write_csv(fname, rows, cols):
    path = os.path.join(OUT, fname)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"  -> {fname}: {len(rows)} rows")
    return len(rows)

# ============================================================
# 1. TotalPass — YAML payloads (1051 files)
# ============================================================
print("=" * 60)
print("1. TotalPass — YAML payloads + tiny.csv")
print("=" * 60)

def extract_totalpass():
    rows = []
    payload_dir = os.path.join(EXT, "TotalPass", "totalpass", "payloads")

    # 1a. Parse all YAML files
    for root, dirs, files in os.walk(payload_dir):
        for fname in files:
            if not fname.endswith('.yml'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue
                vendor = data.get('vendor', '')
                name = data.get('name', '')
                category = data.get('category', '')
                port = data.get('port', '')
                comment = data.get('comment', '')
                credentials = data.get('auth', {}).get('credentials', [])
                if not credentials:
                    continue
                for cred in credentials:
                    if isinstance(cred, dict):
                        rows.append([
                            vendor, name, '', category or str(port),
                            cred.get('username', ''),
                            cred.get('password', ''),
                            f'totalpass_yaml::{os.path.relpath(fpath, payload_dir)}',
                            comment
                        ])
            except Exception as e:
                pass  # skip unparseable YAML

    # 1b. Parse tiny.csv
    tiny_path = os.path.join(payload_dir, "tiny.csv")
    if os.path.exists(tiny_path):
        with open(tiny_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ',' in line:
                    u, p = line.split(',', 1)
                    rows.append(['', '', '', '', u.strip(), p.strip(), 'totalpass_tiny.csv', ''])

    n = write_csv('ext_01_totalpass.csv', rows,
                  ['vendor', 'model', 'version', 'protocol', 'username', 'password', 'source', 'notes'])
    return n

# ============================================================
# 2. DefaultPassword — XLSX (r0eXpeR)
# ============================================================
print("\n" + "=" * 60)
print("2. DefaultPassword (r0eXpeR) — XLSX")
print("=" * 60)

def extract_defaultpassword():
    xlsx_path = os.path.join(EXT, "DefaultPassword", "默认设备密码-20200822-DefaultPassword.xlsx")
    try:
        import openpyxl
    except ImportError:
        os.system(f"{sys.executable} -m pip install openpyxl -q")
        import openpyxl

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    all_rows = []

    # Sheet 1: 默认密码(china) — Name, Method, User ID, PassWord, Level
    ws = wb['默认密码(china)']
    for i, row in enumerate(ws.iter_rows(min_row=3, max_row=ws.max_row, values_only=True)):
        if not row or not any(row): continue
        name = str(row[0]).strip() if len(row) > 0 and row[0] else ''
        method = str(row[1]).strip() if len(row) > 1 and row[1] else ''
        user = str(row[2]).strip() if len(row) > 2 and row[2] else ''
        passwd = str(row[3]).strip() if len(row) > 3 and row[3] else ''
        if not name: continue
        # Handle "(none)/root" format in password
        passwords = [p.strip() for p in passwd.replace('(none)', '').split('/') if p.strip()]
        for pw in passwords or ['']:
            all_rows.append([name, '', '', method, user, pw, 'defaultpassword_china', ''])

    # Sheet 2: datarecovery-password — Manufacturer, Model/Name, Revision, Protocol, User, Password, Access Level, Notes
    ws = wb['datarecovery-password']
    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True)):
        if not row or not any(row): continue
        mfr = str(row[0]).strip() if len(row) > 0 and row[0] else ''
        model = str(row[1]).strip() if len(row) > 1 and row[1] else ''
        rev = str(row[2]).strip() if len(row) > 2 and row[2] else ''
        proto = str(row[3]).strip() if len(row) > 3 and row[3] else ''
        user = str(row[4]).strip() if len(row) > 4 and row[4] else ''
        passwd = str(row[5]).strip() if len(row) > 5 and row[5] else ''
        notes = str(row[7]).strip() if len(row) > 7 and row[7] else ''
        if not mfr and not model: continue
        all_rows.append([mfr, model, rev, proto, user, passwd, 'defaultpassword_datarecovery', notes])

    # Sheet 3: 安全设备默认密码含产品地址 — 设备, 默认账号, 默认密码, 地址
    ws = wb['安全设备默认密码含产品地址']
    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True)):
        if not row or not any(row): continue
        device = str(row[0]).strip() if len(row) > 0 and row[0] else ''
        user = str(row[1]).strip() if len(row) > 1 and row[1] else ''
        passwd = str(row[2]).strip() if len(row) > 2 and row[2] else ''
        addr = str(row[3]).strip() if len(row) > 3 and row[3] else ''
        if not device: continue
        # Handle multi-line passwords
        passwords = [p.strip() for p in passwd.split('\n') if p.strip()]
        for pw in passwords or ['']:
            all_rows.append([device, '', '', '', user, pw, 'defaultpassword_sec_devices', addr])

    # Sheet 4: 路由器默认密码含说明 — 1-column descriptive text
    ws = wb['路由器默认密码含说明']
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)):
        if not row or not row[0]: continue
        text = str(row[0]).strip()
        # Extract user/pass from descriptive text
        # Pattern: 用户名xxx密码xxx
        user_m = re.search(r'用户名[:：]?\s*(\S+?)(?:密码|，|。|\s)', text)
        pass_m = re.search(r'密码[:：]?(?:是|为)?\s*(\S+)', text)
        if user_m and pass_m:
            vendor = text[:15].strip()
            all_rows.append([vendor, '', '', '', user_m.group(1), pass_m.group(1), 'defaultpassword_router', text[:100]])

    n = write_csv('ext_02_defaultpassword.csv', all_rows,
                  ['vendor', 'model', 'version', 'protocol', 'username', 'password', 'source', 'notes'])
    return n

# ============================================================
# 3. Frame-DefaultPass — README.md table
# ============================================================
print("\n" + "=" * 60)
print("3. Frame-DefaultPass — README.md table")
print("=" * 60)

def extract_frame_defaultpass():
    readme_path = os.path.join(EXT, "Frame-DefaultPass", "Readme.md")
    text, _ = read_file_smart(readme_path)
    rows = []

    # Parse markdown table rows: | vendor/desc | cred info |
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('|') or '---' in line or 'Frame' in line:
            continue
        cols = [c.strip() for c in line.split('|') if c.strip()]
        if len(cols) < 2:
            continue

        vendor_desc = cols[0].strip()
        cred_text = cols[1].strip()

        # Extract vendor from first column (may contain HTML links)
        vendor = re.sub(r'<[^>]+>', '', vendor_desc).strip()
        if len(vendor) > 60:
            vendor = vendor[:60]

        # Extract credentials from second column
        # Patterns: "admin/admin", "admin/123456", "username/password<br />username/password"
        cred_parts = re.split(r'<br\s*/?>', cred_text)
        for part in cred_parts:
            part = part.strip()
            if not part: continue

            # Skip descriptive text without credentials
            if '没有原始密码' in part or '要求创建密码' in part or '任意密码' in part or '无密码' in part:
                rows.append([vendor, '', '', '', '', '', 'frame_defaultpass', part])
                continue

            # Look for user/pass or user\pass patterns
            slash_match = re.findall(r'(\S+?)\s*/\s*(\S+)', part)
            if slash_match:
                for u, p in slash_match:
                    # Filter email-looking usernames
                    if '@' in u and '.' in u.split('@')[-1]:
                        rows.append([vendor, '', '', '', u, p, 'frame_defaultpass', f'email_user: {part}'])
                    else:
                        rows.append([vendor, '', '', '', u, p, 'frame_defaultpass', part])
            elif '\\' in part:
                # Pattern: "super@walle-web.io\ Walle123"
                bs_match = re.findall(r'(\S+?)\s*\\\s*(\S+)', part)
                for u, p in bs_match:
                    rows.append([vendor, '', '', '', u, p, 'frame_defaultpass', part])
            elif '：' in part or ':' in part:
                # Pattern: "超管：super@walle-web.io\ Walle123"
                colon_m = re.findall(r'[：:]\s*(\S+)\s*[\\/]\s*(\S+)', part)
                for u, p in colon_m:
                    rows.append([vendor, '', '', '', u, p, 'frame_defaultpass', part])
            elif part and not any(kw in part for kw in ['<空>', '无', '任意', '创建密码']):
                # Single value — might be just a password
                if '/' in part:
                    u, p = part.split('/', 1)
                    rows.append([vendor, '', '', '', u.strip(), p.strip(), 'frame_defaultpass', ''])
                else:
                    rows.append([vendor, '', '', '', '', part, 'frame_defaultpass', ''])

    n = write_csv('ext_03_framedefaultpass.csv', rows,
                  ['vendor', 'model', 'version', 'protocol', 'username', 'password', 'source', 'notes'])
    return n

# ============================================================
# 4. Userpass-Dict — organized username/password lists
# ============================================================
print("\n" + "=" * 60)
print("4. Userpass-Dict — default credential lists")
print("=" * 60)

def extract_userpass_dict():
    base = os.path.join(EXT, "Userpass-Dict")
    rows = []

    # Service mapping: filename prefix -> service info
    service_map = {
        'ssh': ('SSH', '22'),
        'ftp': ('FTP', '21'),
        'mysql': ('MySQL', '3306'),
        'postgresql': ('PostgreSQL', '5432'),
        'sqlserver': ('MSSQL', '1433'),
        'tomcat': ('Apache Tomcat', '8080'),
        'weblogic': ('Oracle WebLogic', '7001'),
        'jboss': ('JBoss', '8080'),
    }

    # Process each service's user+pass
    for svc_key, (svc_name, svc_port) in service_map.items():
        user_file = os.path.join(base, 'username', f'{svc_key}_def_user')
        pass_file = os.path.join(base, 'password', f'{svc_key}_def_pass')

        users = []
        passwords = []
        if os.path.exists(user_file):
            with open(user_file, 'r', encoding='utf-8', errors='replace') as f:
                users = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        if os.path.exists(pass_file):
            with open(pass_file, 'r', encoding='utf-8', errors='replace') as f:
                passwords = [l.strip() for l in f if l.strip() and not l.startswith('#')]

        # Cross-product: each user with each password
        for u in users:
            for p in passwords:
                rows.append([svc_name, '', '', svc_port, u, p, 'userpass_dict', ''])

        # If one list is empty, still record the other
        if not users and passwords:
            for p in passwords:
                rows.append([svc_name, '', '', svc_port, '', p, 'userpass_dict', ''])
        if users and not passwords:
            for u in users:
                rows.append([svc_name, '', '', svc_port, u, '', 'userpass_dict', ''])

    n = write_csv('ext_04_userpass_dict.csv', rows,
                  ['vendor', 'model', 'version', 'protocol', 'username', 'password', 'source', 'notes'])
    return n

# ============================================================
# 5. fwpass — pass.txt (security appliances)
# ============================================================
print("\n" + "=" * 60)
print("5. fwpass — pass.txt (security appliances)")
print("=" * 60)

def extract_fwpass():
    pass_path = os.path.join(EXT, "fwpass", "pass.txt")
    text, enc = read_file_smart(pass_path)
    rows = []

    current_vendor = ''
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue

        cols = line.split('\t')
        if len(cols) >= 3:
            # Format: vendor \t username \t password
            vendor = cols[0].strip()
            username = cols[1].strip()
            password = cols[2].strip()
            if vendor and username:
                rows.append([vendor, '', '', '', username, password, 'fwpass', ''])
                current_vendor = vendor
        elif len(cols) == 2:
            # Continuation: username \t password (vendor from previous line)
            rows.append([current_vendor, '', '', '', cols[0].strip(), cols[1].strip(), 'fwpass', ''])
        elif len(cols) == 1 and current_vendor:
            # Just a password value
            rows.append([current_vendor, '', '', '', '', cols[0].strip(), 'fwpass', ''])

    n = write_csv('ext_05_fwpass.csv', rows,
                  ['vendor', 'model', 'version', 'protocol', 'username', 'password', 'source', 'notes'])
    return n

# ============================================================
# MAIN
# ============================================================
total = 0
total += extract_totalpass()
total += extract_defaultpassword()
total += extract_frame_defaultpass()
total += extract_userpass_dict()
total += extract_fwpass()

print(f"\n{'='*60}")
print(f"TOTAL extracted: {total} rows from 5 external repos")
print(f"Output directory: {OUT}")
