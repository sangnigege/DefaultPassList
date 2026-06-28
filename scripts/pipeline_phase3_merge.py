#!/usr/bin/env python3
"""
Phase 3: Merge all Phase 2 CSVs, clean data, deduplicate, classify, output final files.
"""
import os, sys, csv, json, re
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_config import *
from pipeline_utils import *

os.makedirs(PHASE3, exist_ok=True)

# ============================================================
# Step 3.1: Merge all Phase 2 CSVs
# ============================================================
print("=" * 60)
print("PHASE 3: Merge, Clean, Dedup, Classify")
print("=" * 60)
print("\nStep 3.1: Loading all Phase 2 CSVs...")

all_rows = []
source_counts = Counter()
for fname in sorted(os.listdir(PHASE2)):
    if fname == 'phase2_manifest.json': continue
    if not fname.endswith('.csv'): continue
    path = os.path.join(PHASE2, fname)
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # Ensure all unified fields exist
            for field in UNIFIED_FIELDS:
                if field not in row:
                    row[field] = ''
            row['_phase2_file'] = fname
            all_rows.append(row)
            count += 1
        source_counts[fname] = count

print(f"  Total loaded: {len(all_rows)} rows from {len(source_counts)} files")
for src, cnt in source_counts.most_common():
    print(f"    {src}: {cnt}")

# ============================================================
# Step 3.2: Data Cleaning (never delete, move to notes)
# ============================================================
print("\nStep 3.2: Data cleaning...")
clean_stats = Counter()

for row in all_rows:
    u = row['username'].strip()
    p = row['password'].strip()
    v = row['vendor'].strip()

    # 3.2.1: Normalize blank indicators
    for field in ['username', 'password']:
        val = row[field].strip()
        cleaned, was_blank = norm_blank(val)
        if was_blank:
            if val.lower() != cleaned.lower():
                row['notes'] = ensure_note(row['notes'], fmt_note(f'original_{field}', val))
            row[field] = cleaned
            clean_stats['blank_normalized'] += 1

    # Re-read after normalization
    u = row['username'].strip()
    p = row['password'].strip()

    # 3.2.2: Split user/pass in password field
    if '/' in p and not ' ' in p and len(p) < 60 and not p.startswith('http'):
        parts = p.split('/')
        if len(parts) == 2 and parts[0] and parts[1]:
            if re.match(r'^[\w@#$%!._-]+$', parts[0]) and re.match(r'^[\w@#$%!._-]+$', parts[1]):
                if not u or u.isdigit() or is_port_number(u):
                    if u and (u.isdigit() or is_port_number(u)):
                        row['notes'] = ensure_note(row['notes'], fmt_note('port', u))
                    row['username'] = parts[0]
                    row['password'] = parts[1]
                    clean_stats['split_userpass_in_password'] += 1

    u = row['username'].strip()
    p = row['password'].strip()

    # 3.2.3: Split "user:pass" in password field
    if ':' in p and not ' ' in p and len(p) < 60 and not p.startswith('http'):
        parts = p.split(':')
        if len(parts) == 2 and parts[0] and parts[1]:
            if re.match(r'^[\w@#$%!._-]+$', parts[0]) and re.match(r'^[\w@#$%!._-]+$', parts[1]):
                if not u or u.isdigit():
                    if u.isdigit():
                        row['notes'] = ensure_note(row['notes'], fmt_note('port', u))
                    row['username'] = parts[0]
                    row['password'] = parts[1]
                    clean_stats['split_userpass_in_password'] += 1

    u = row['username'].strip()
    p = row['password'].strip()

    # 3.2.4: Move Chinese descriptions from username field
    if has_cjk(u) and len(u) > 10:
        if any(kw in u for kw in CHINESE_DESC_KEYWORDS):
            row['notes'] = ensure_note(row['notes'], fmt_note('account_desc', u))
            row['username'] = ''
            clean_stats['chinese_desc_to_notes'] += 1

    u = row['username'].strip()

    # 3.2.5: Move URLs from username
    if u.startswith('http://') or u.startswith('https://'):
        row['notes'] = ensure_note(row['notes'], fmt_note('reference_url', u))
        row['username'] = ''
        clean_stats['url_to_notes'] += 1

    # 3.2.6: Move well-known port numbers from username
    if is_port_number(u):
        row['notes'] = ensure_note(row['notes'], fmt_note('port', u))
        row['username'] = ''
        clean_stats['port_to_notes'] += 1

    u = row['username'].strip()

    # 3.2.7: Handle "Hardcoded password: xxx" in password
    p = row['password'].strip()
    m = re.match(r'[Hh]ardcoded password[：:]\s*(\S+)', p)
    if m:
        row['notes'] = ensure_note(row['notes'], fmt_note('original_password', p))
        row['password'] = m.group(1)
        clean_stats['hardcoded_password_fix'] += 1

    # 3.2.8: Normalize '空' (Chinese for "empty") as empty password
    p = row['password'].strip()
    if p == '空':
        row['notes'] = ensure_note(row['notes'], '[password: empty]')
        row['password'] = ''
        clean_stats['chinese_empty_password'] += 1

    # 3.2.9: Clean triple-quote wrappers
    for field in ['vendor', 'username', 'password']:
        val = row[field].strip()
        if val.startswith('"""') or val.startswith('"""'):
            row[field] = val.strip('"').strip()
            clean_stats['triple_quote_cleaned'] += 1

    # 3.2.10: Password is purely a CJK description (not a credential)
    p = row['password'].strip()
    if has_cjk(p) and len(p) > 20 and not any(c in p for c in '@#$%!./'):
        row['notes'] = ensure_note(row['notes'], fmt_note('password_desc', p))
        row['password'] = ''
        clean_stats['chinese_password_to_notes'] += 1

    # 3.2.11: Split multi-field labeled passwords: "XXX用户/密码: YYY ZZZ用户/密码: WWW"
    p = row['password'].strip()
    if has_cjk(p) and '/密码:' in p and len(p) > 40:
        # Extract individual credential fields
        cred_fields = re.findall(r'(\S+?)/密码[：:]\s*(\S+)', p)
        if cred_fields and len(cred_fields) >= 2:
            # Take the first one as primary, rest as notes
            first_label, first_pass = cred_fields[0]
            row['password'] = first_pass.strip()
            others = '; '.join(f'{label}={cred}' for label, cred in cred_fields[1:])
            row['notes'] = ensure_note(row['notes'], f'[multi_field_creds: {first_label}={first_pass}; {others}]')
            clean_stats['multi_field_password_split'] += 1
        elif cred_fields and len(cred_fields) == 1:
            row['password'] = cred_fields[0][1].strip()
            clean_stats['multi_field_password_split'] += 1

for k, v in sorted(clean_stats.items()):
    print(f"  {k}: {v}")

# ============================================================
# Step 3.3: Vendor Normalization
# ============================================================
print("\nStep 3.3: Vendor normalization...")
vendor_norm_count = 0
vendor_extract_count = 0

for row in all_rows:
    old_vendor = row['vendor'].strip()
    # Normalize vendor name
    vl = old_vendor.lower().strip()
    if vl in VENDOR_MAP:
        row['vendor'] = VENDOR_MAP[vl]
        if row['vendor'] != old_vendor:
            vendor_norm_count += 1
    elif old_vendor.isupper() and len(old_vendor) > 3 and ' ' not in old_vendor:
        row['vendor'] = old_vendor.title()
        vendor_norm_count += 1

    # Extract vendor from model if vendor is generic
    vendor = row['vendor'].strip()
    model = row['model'].strip()
    if vendor in GENERIC_VENDORS or not vendor:
        new_vendor, new_model = extract_vendor_from_model(vendor, model)
        if new_vendor != vendor:
            row['vendor'] = new_vendor
            if new_model != model:
                row['model'] = new_model
            vendor_extract_count += 1

print(f"  Vendor name normalized: {vendor_norm_count}")
print(f"  Vendor extracted from model: {vendor_extract_count}")

# ============================================================
# Step 3.4: Deduplication
# ============================================================
print("\nStep 3.4: Deduplication...")

seen = {}
dup_count = 0

for row in all_rows:
    key = (norm_key(row['vendor']), norm_key(row['model']),
           norm_key(row['version']), norm_key(row['protocol']),
           norm_key(row['username']), norm_key(row['password']))

    if key in seen:
        dup_count += 1
        existing = seen[key]
        # Merge source_file
        es = existing.get('source_file', '')
        ns = row.get('source_file', '')
        if ns and ns not in es:
            row['source_file'] = es + '; ' + ns if es else ns
        # Merge notes
        en = existing.get('notes', '')
        nn = row.get('notes', '')
        if nn and nn not in en:
            row['notes'] = (en + '; ' + nn).strip('; ') if en else nn
        # Keep row with more filled fields
        def filled(r):
            return sum(1 for k in UNIFIED_FIELDS if r.get(k, '').strip())
        if filled(row) > filled(existing):
            seen[key] = row
    else:
        seen[key] = row

unique_rows = list(seen.values())
print(f"  Duplicates removed: {dup_count}")
print(f"  Unique rows: {len(unique_rows)}")

# ============================================================
# Step 3.5: Classification
# ============================================================
print("\nStep 3.5: Classification...")

def word_match(kw, text):
    """Match keyword as a word boundary in text.
    For short keywords (len <= 3), require word boundaries.
    For longer keywords or CJK keywords, substring match is fine."""
    if not kw or not text:
        return False
    # CJK keyword — safe to substring match (multi-char, won't accidentally match)
    if has_cjk(kw) or len(kw) > 4:
        return kw in text
    # Short ASCII keyword — use word boundary to avoid "abb" matching "zabbix"
    pattern = r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])'
    return bool(re.search(pattern, text))

def classify(row):
    vendor = (row.get('vendor', '') + ' ' + row.get('model', '')).lower()
    notes = (row.get('protocol', '') + ' ' + row.get('notes', '')).lower()
    src = row.get('source_file', '').lower()

    # Check each category's keywords
    for cat, keywords in CAT_KEYWORDS.items():
        if any(word_match(kw, vendor) for kw in keywords):
            return cat
        if any(word_match(kw, notes) for kw in keywords):
            return cat

    # Check protocol field for network indicators
    if any(kw in row.get('protocol', '').lower() for kw in ['telnet', 'ssh', 'snmp']):
        return 'Network'

    # Source-based heuristics
    if 'scada' in src: return 'ICS/SCADA'
    if 'ics' in src: return 'ICS/SCADA'
    if 'des账号' in src: return 'Database'
    if 'weblogic' in src: return 'Web/App'
    if 'web_systems' in src: return 'Web/App'

    return 'Other'

for row in unique_rows:
    row['category'] = classify(row)

cat_counts = Counter(row['category'] for row in unique_rows)
for cat, cnt in cat_counts.most_common():
    print(f"  {cat}: {cnt}")

# ============================================================
# Step 3.6: Write Outputs
# ============================================================
print("\nStep 3.6: Writing outputs...")

OUTPUT_FIELDS = ['vendor', 'model', 'version', 'protocol', 'username', 'password',
                 'category', 'source_file', 'source_section', 'notes']

master_path = os.path.join(PHASE3, 'default_passwords_master.csv')
with open(master_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction='ignore')
    w.writeheader()
    w.writerows(unique_rows)
print(f"  Master: {master_path} ({len(unique_rows)} rows)")

# Category splits
for cat, cnt in cat_counts.most_common():
    cat_rows = [r for r in unique_rows if r['category'] == cat]
    safe = cat.replace('/', '_').replace(' ', '_')
    cp = os.path.join(PHASE3, f'default_passwords_{safe}.csv')
    with open(cp, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(cat_rows)
    print(f"  {safe}: {len(cat_rows)} rows")

# STATS.md
stats_path = os.path.join(PHASE3, 'STATS.md')
with open(stats_path, 'w', encoding='utf-8') as f:
    f.write('# 默认口令数据集 - 统计报告\n\n')
    f.write(f'**生成日期**: 2026-06-28\n**处理方式**: 三阶段系统化流水线\n\n')
    f.write(f'## 总览\n\n')
    f.write(f'- **去重后条目总数**: {len(unique_rows)}\n')
    f.write(f'- **原始合并条目数**: {len(all_rows)}\n')
    f.write(f'- **去除重复**: {dup_count}\n')
    f.write(f'- **来源文件数**: {len(source_counts)}\n\n')
    f.write(f'## 分类分布\n\n| 分类 | 数量 |\n|------|------|\n')
    for cat, cnt in cat_counts.most_common():
        f.write(f'| {cat} | {cnt} |\n')
    f.write(f'\n## Top 20 厂商\n\n')
    vc = Counter(r['vendor'].strip() for r in unique_rows if r['vendor'].strip())
    for v, cnt in vc.most_common(20):
        f.write(f'- {v}: {cnt}\n')
    f.write(f'\n## Top 20 默认密码\n\n')
    pc = Counter(r['password'].strip() for r in unique_rows if r['password'].strip())
    for p, cnt in pc.most_common(20):
        masked = p[:2] + '***' if len(p) > 2 else '***'
        f.write(f'- {masked}: {cnt}\n')
    f.write(f'\n## Top 10 默认用户名\n\n')
    uc = Counter(r['username'].strip() for r in unique_rows if r['username'].strip())
    for u, cnt in uc.most_common(10):
        f.write(f'- {u}: {cnt}\n')
print(f"  STATS.md: {stats_path}")

# ============================================================
# VERIFICATION
# ============================================================
print("\n" + "=" * 60)
print("PHASE 3 VERIFICATION")
print("=" * 60)

errors = 0

# 1. Row count sanity
merged_count = sum(source_counts.values())
print(f"\n1. Row count: {len(unique_rows)} (from {merged_count} merged, {dup_count} dupes removed)")
if len(unique_rows) > merged_count:
    print("   ❌ Unique rows > merged rows!")
    errors += 1
else:
    print("   ✅")

# 2. No exact duplicates
seen2 = {}
dupes2 = 0
for r in unique_rows:
    key = (norm_key(r['vendor']), norm_key(r['model']), norm_key(r['version']),
           norm_key(r['protocol']), norm_key(r['username']), norm_key(r['password']))
    if key in seen2:
        dupes2 += 1
    else:
        seen2[key] = True
print(f"2. Exact duplicates in output: {dupes2}")
if dupes2 > 0:
    print("   ❌ Duplicates found!")
    errors += 1
else:
    print("   ✅")

# 3. No garbled characters
garbled = 0
for r in unique_rows:
    for f in ['vendor', 'username', 'password']:
        if '�' in r[f]:
            garbled += 1
print(f"3. Garbled characters: {garbled}")
if garbled > 0:
    print("   ❌")
    errors += 1
else:
    print("   ✅")

# 4. Known credentials test
known_creds = [
    ('cisco', 'cisco', 'cisco'), ('admin', 'admin', ''),
    ('root', 'calvin', 'Dell'), ('super', 'juniper123', 'Juniper'),
    ('Admin', 'zabbix', 'Zabbix'), ('weblogic', 'weblogic1', 'WebLogic'),
    ('admin', 'Admin@123', '华为'), ('tomcat', 'tomcat', ''),
]
print("4. Known credentials check:")
for cred in known_creds:
    u = cred[0].lower()
    pw = cred[1].lower()
    vhint = cred[2].lower() if len(cred) > 2 else ''
    found = False
    for r in unique_rows:
        if (norm_key(r['username']) == u and norm_key(r['password']) == pw):
            if not vhint or vhint in norm_key(r['vendor']):
                found = True
                break
    status = "✅" if found else "❌ MISSING!"
    print(f"   {status} {cred}")
    if not found: errors += 1

# 5. Source coverage
print("5. Source coverage:")
phase2_files = [f for f in os.listdir(PHASE2) if f.endswith('.csv') and f != 'phase2_manifest.json']
all_sources_in_output = set()
for r in unique_rows:
    sf = r.get('source_file', '')
    for s in sf.split(';'):
        if s.strip():
            all_sources_in_output.add(s.strip())

for pf in phase2_files:
    label = pf.replace('_normalized.csv', '')
    found = any(label in s for s in all_sources_in_output)
    if not found:
        print(f"   ⚠ {label}: not found in output source_file")
    # else: OK — sources get merged

# 6. Category sanity
print("6. Category spot-check:")
category_checks = [
    ('Cisco', 'Network'), ('Oracle', 'Database'), ('Siemens', 'ICS/SCADA'),
    ('Dell', 'Server/Storage'), ('华为', 'Network'), ('Zabbix', 'Web/App'),
    ('深信服', 'Security'), ('H3C', 'Network'),
]
for vendor, expected_cat in category_checks:
    found_cats = set()
    for r in unique_rows:
        if vendor.lower() in r['vendor'].lower():
            found_cats.add(r['category'])
    if expected_cat in found_cats:
        print(f"   ✅ {vendor}: {expected_cat} in {found_cats}")
    else:
        print(f"   ❌ {vendor}: expected {expected_cat}, got {found_cats}")
        errors += 1

# 7. Spot-check rows
print("\n7. Spot-check (every ~1500 rows):")
step = max(len(unique_rows) // 10, 1)
for i in range(0, len(unique_rows), step):
    r = unique_rows[i]
    v = r['vendor'][:22]
    u = r['username'][:18] if r['username'].strip() else '-'
    p = r['password'][:22] if r['password'].strip() else '-'
    c = r['category'][:12]
    print(f"  [{i:5d}] {v:<22s} {u:<18s} {p:<22s} {c}")

print(f"\n{'='*60}")
print(f"VERIFICATION COMPLETE: {errors} errors")
print(f"Output: {PHASE3}/")
