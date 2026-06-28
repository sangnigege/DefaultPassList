#!/usr/bin/env python3
"""Fix remaining issues found in final audit."""
import csv, os, re
from collections import Counter

SRC = "/home/matrix/work/Common-device-default-password-main"
MASTER = os.path.join(SRC, "output", "phase3_merged", "default_passwords_master.csv")

with open(MASTER, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
fn = rows[0].keys()

print(f"Before: {len(rows)} rows")
stats = {}

def fix(field, old, new, desc):
    stats[desc] = stats.get(desc, 0) + 1

for r in rows:
    u = r["username"].strip()
    p = r["password"].strip()
    v = r["vendor"].strip()

    # ---- 1. Remove fully empty row ----
    if not any(r[f].strip() for f in ['vendor', 'model', 'username', 'password']):
        r["_remove"] = True
        fix("row", "", "", "empty_row_removed")
        continue

    # ---- 2. "blank" password -> empty ----
    if p.lower() in ("blank", "<blank>"):
        r["password"] = ""
        fix("password", p, "", "blank_normalized")

    # ---- 3. URL usernames (http/https split) ----
    if u in ("http", "https") and p.startswith("//"):
        r["notes"] = (r.get("notes", "") + f"; url={u}{p}").strip("; ")
        r["username"] = ""
        r["password"] = ""
        fix("username", u, "", "url_username_fixed")

    # ---- 4. STelnet登录/密码: label in password ----
    p = r["password"].strip()
    m = re.match(r"(\S+登录)/(?:用户名|密码)[：:]\s*(\S+)", p)
    if m:
        proto = m.group(1).replace("登录", "").strip()
        actual = m.group(2).strip()
        if actual not in ("-", "—", "无"):
            r["protocol"] = proto if not r["protocol"].strip() else r["protocol"]
            r["password"] = actual
            fix("password", p[:30], actual, "label_in_password_extracted")

    # ---- 5. Chinese parenthetical note in password: Admin@123（系统管理员） ----
    p = r["password"].strip()
    m = re.match(r"([\w@#$%!._-]+)[（(](.+)[）)]$", p)
    if m:
        r["notes"] = (r.get("notes", "") + f"; {m.group(2)}").strip("; ")
        r["password"] = m.group(1)
        fix("password", p[:30], m.group(1), "cn_parenthetical_extracted")

    # ---- 6. Multi-cred slash-separated with Chinese notes: "12345/使用超级终端..." ----
    p = r["password"].strip()
    if "/" in p and any("一" <= c <= "鿿" for c in p) and len(p) < 120:
        parts = p.split("/")
        # First part looks like a password, rest is note
        if parts and re.match(r"^[\w@#$%!._-]+$", parts[0]):
            r["password"] = parts[0]
            r["notes"] = (r.get("notes", "") + f"; extra_info={'/'.join(parts[1:])}").strip("; ")
            fix("password", p[:30], parts[0], "cn_slash_password_split")

    # ---- 7. Multi-cred concatenated without separator: admin/123456root/123456 ----
    p = r["password"].strip()
    if len(p) > 20 and not " " in p and not "," in p and not "|" in p:
        # Try to split: look for repeated user/pass pattern
        creds = re.findall(r"(\w{2,20})/(\S{1,30}?)(?=\w{2,20}/|$)", p)
        if creds and len(creds) >= 2:
            # Take first, note rest
            first_u, first_p = creds[0]
            if first_u in r.get("username", ""):
                r["password"] = first_p
            else:
                r["username"] = first_u
                r["password"] = first_p
            others = ", ".join(f"{cu}/{cp}" for cu, cp in creds[1:])
            r["notes"] = (r.get("notes", "") + f"; additional_creds={others}").strip("; ")
            fix("password", p[:30], first_p, "multi_cred_concat_split")

    # ---- 8. Long SCADA multi-cred notes in password -> move to notes ----
    p = r["password"].strip()
    if len(p) > 65 and ("," in p or ":" in p):
        # Check if it's a multi-cred list
        parts = [x.strip().strip('"') for x in p.split(",")]
        if len(parts) >= 3:
            # Try to extract first workable credential
            first_cred = None
            for part in parts:
                m2 = re.match(r"(\w{2,20})[：:]\s*(\S+)", part)
                if m2:
                    first_cred = (m2.group(1), m2.group(2))
                    break
                elif "/" in part:
                    up = part.split("/", 1)
                    if re.match(r"^[\w@#$%!._-]+$", up[0]) and len(up[1]) < 40:
                        first_cred = (up[0], up[1])
                        break
            if first_cred:
                r["username"] = first_cred[0]
                r["password"] = first_cred[1]
                r["notes"] = (r.get("notes", "") + f"; full_cred_list={p[:200]}").strip("; ")
                fix("password", p[:30], first_cred[1], "scada_multi_fixed")
            else:
                r["notes"] = (r.get("notes", "") + f"; cred_info={p[:200]}").strip("; ")
                r["password"] = ""
                fix("password", p[:30], "", "scada_info_to_notes")

    # ---- 9. Very long string that's clearly descriptive -> move to notes ----
    p = r["password"].strip()
    if len(p) > 100:
        r["notes"] = (r.get("notes", "") + f"; [long_value: {p[:200]}]").strip("; ")
        r["password"] = ""
        fix("password", p[:30], "", "very_long_to_notes")

# Apply removals and dedup
clean = [r for r in rows if not r.get("_remove")]
for r in clean:
    r.pop("_remove", None)

seen = {}
final = []
dupes = 0
for r in clean:
    key = (r["vendor"].strip().lower(), r["model"].strip().lower(),
           r["version"].strip().lower(), r["protocol"].strip().lower(),
           r["username"].strip().lower(), r["password"].strip().lower())
    if key in seen: dupes += 1
    else:
        seen[key] = r
        final.append(r)

print(f"\nFixes: {sum(stats.values())} total")
for k, v in sorted(stats.items()):
    print(f"  {k}: {v}")
print(f"Dupes removed: {dupes}")
print(f"Final: {len(final)}")

with open(MASTER, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fn)
    w.writeheader()
    w.writerows(final)

# Re-split categories
cc = Counter(r["category"] for r in final)
for cat, cnt in cc.most_common():
    cr = [r for r in final if r["category"] == cat]
    sn = cat.replace("/", "_").replace(" ", "_")
    cp = os.path.join(SRC, "output", "phase3_merged", f"default_passwords_{sn}.csv")
    with open(cp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        w.writerows(cr)

print("Done!")
