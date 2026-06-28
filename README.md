# DefaultPassList — 默认口令数据集

常见设备默认口令数据集，覆盖网络设备、安全产品、服务器、工控系统、数据库、Web 应用、IoT 等 **9 大类**。从 **33 个来源** 整理去重，统一为结构化 CSV 格式，供安全研究和授权评估使用。

A curated, deduplicated collection of 19,856 default credentials for network gear, security appliances, servers, ICS/SCADA, databases, web apps, and IoT — sourced from 33 upstream lists, merged and structured as clean CSV.

> ⚠️ **Disclaimer**：此数据集仅供安全研究、渗透测试授权评估及教育用途。使用者须遵守当地法律法规，在已获得授权的情况下使用。不当使用所造成的一切后果由使用者本人承担。
> This dataset is for authorized security research, pentesting, and educational purposes only.

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/<user>/DefaultPassList.git

# 主数据文件在根目录（符号链接）
head default_passwords_master.csv

# 或直接读取分类文件
head output/phase3_merged/default_passwords_Network.csv
```

### 在 Python 中使用

```python
import csv

with open('default_passwords_master.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"{row['vendor']} | {row['username']} | {row['password']} | {row['category']}")
```

### 用 grep 快速查询

```bash
# 查华为所有默认口令
grep -i "华为" default_passwords_master.csv

# 查某个密码被多少设备使用
cut -d, -f6 default_passwords_master.csv | sort | uniq -c | sort -rn | head -10
```

---

## 数据概览

| 指标 | 数值 |
|------|------|
| 去重后条目总数 | **19,856** |
| 原始合并条目 | 28,779 |
| 去除重复 | 8,923 |
| 来源文件数 | 33 |
| 覆盖厂商 | 2,000+ |
| 分类数 | 9 |

### 分类分布

| 分类 | 数量 | 说明 |
|------|------|------|
| Network | 8,814 | 路由器、交换机、网关、无线AP、ONT/ONU、负载均衡等 |
| Other | 6,020 | 其他未细分条目 |
| Web/App | 1,278 | OA系统、中间件（Tomcat/WebLogic/JBoss）、CMS、运维平台 |
| Server/Storage | 996 | 服务器、存储阵列、IPMI/iLO/iDRAC/CIMC/IRMC |
| Security | 854 | 防火墙、IDS/IPS/WAF、VPN、堡垒机、SIEM、上网行为管理 |
| Database | 839 | 关系型数据库（Oracle/MySQL/MSSQL/达梦/人大金仓）、NoSQL、消息队列 |
| ICS/SCADA | 434 | PLC、RTU、HMI、DCS、DDC、BACnet、Modbus 设备 |
| IoT/Other | 408 | 网络摄像头、打印机、UPS、门禁考勤、嵌入式设备 |
| Service | 213 | FTP/SSH/Telnet/SNMP 等通用服务默认凭据 |

### Top 10 用户名 & 密码

| 用户名 | 次数 | | 密码 | 次数 |
|--------|------|---|------|------|
| admin | 5,938 | | ad*** | 3,653 |
| root | 821 | | pa*** | 996 |
| user | 279 | | ad*** | 785 |
| unknown | 236 | | 12*** | 622 |
| Admin | 190 | | Ad*** | 264 |
| Administrator | 166 | | un*** | 262 |
| test | 126 | | ep*** | 187 |
| guest | 113 | | Ad*** | 187 |
| manager | 95 | | ro*** | 177 |
| administrator | 76 | | 12*** | 159 |

---

## 文件结构

```
DefaultPassList/
├── default_passwords_master.csv          # 主数据文件（符号链接 → output/...）
├── README.md
├── .gitignore
│
├── output/
│   └── phase3_merged/                    # Phase 3 最终产物
│       ├── default_passwords_master.csv  # 全量 19,856 条
│       ├── default_passwords_Network.csv # 网络设备 8,814 条
│       ├── default_passwords_Security.csv
│       ├── default_passwords_Server_Storage.csv
│       ├── default_passwords_ICS_SCADA.csv
│       ├── default_passwords_Web_App.csv
│       ├── default_passwords_Database.csv
│       ├── default_passwords_IoT_Other.csv
│       ├── default_passwords_Service.csv
│       ├── default_passwords_Other.csv
│       └── STATS.md                      # 统计报告
│
├── raw_archive/                          # 原始收集文件（33 个来源）
│   ├── *.xlsx, *.txt, *.csv, *.md       # 原始中文/英文来源
│   ├── csv_from_xlsx/                    # XLSX 转 CSV 中间产物
│   ├── extracted/                        # 外部仓库提取的 CSV
│   ├── DefaultCreds-cheat-sheet/         # DefaultCreds-cheat-sheet 仓库
│   ├── TotalPass/                        # 0xHJK/TotalPass 仓库
│   ├── DefaultPassword/                  # r0eXpeR/DefaultPassword 仓库
│   ├── Frame-DefaultPass/                # Awrrays/Frame-DefaultPass
│   ├── Userpass-Dict/                    # MuyeGecko/Userpass-Dict
│   └── fwpass/                           # 1amfine2333/fwpass
│
└── scripts/                              # 三阶段流水线脚本
    ├── pipeline_config.py                # 共享配置（厂商映射、关键词、端口集）
    ├── pipeline_utils.py                 # 共享工具（编码检测、blank归一化）
    ├── pipeline_phase1_convert.py        # Phase 1: 格式转换
    ├── pipeline_phase2_normalize.py      # Phase 2: Schema 归一化
    ├── pipeline_phase3_merge.py          # Phase 3: 合并、清洗、去重、分类
    ├── extract_external_sources.py       # 外部仓库提取脚本
    ├── fix_final_issues.py               # 最终问题修复
    └── archive/                          # 旧版脚本存档（仅供参考）
```

---

## 数据字段 (Schema)

| 字段 | 类型 | 说明 |
|------|------|------|
| `vendor` | string | 厂商/品牌（已规范化，如 `huawei` → `华为`） |
| `model` | string | 设备型号（部分源自源数据，可能为空） |
| `version` | string | 固件/系统版本（较少填充） |
| `protocol` | string | 访问方式：SSH, Telnet, Web, Console, BootROM, SNMP, FTP, HTTP 等 |
| `username` | string | 默认用户名（`blank`/`none`/`N/A` 已归一化为空） |
| `password` | string | 默认密码（同上归一化） |
| `category` | string | 设备分类（9 大类之一） |
| `source_file` | string | 数据来源文件（多个来源以 `; ` 分隔） |
| `source_section` | string | 来源章节上下文（叙事类源文件） |
| `notes` | string | 备注信息：端口号、原始值（修正过的字段）、附加凭据、参考 URL 等 |

---

## 处理流水线

三阶段系统化流水线，每阶段独立运行、独立验证、有 checkpoint 文件：

### Phase 1 — 格式转换

**脚本**: `pipeline_phase1_convert.py`

| 输入格式 | 源文件数 | 方法 |
|----------|---------|------|
| XLSX | 10 | `openpyxl` 逐单元格提取，MD5 去重 |
| CSV (UTF-8) | 4 | 直接复制，去 BOM |
| CSV (GBK) | 3 | 字节特征检测 → GB18030 解码 |
| Tab-separated TXT | 3 | `csv.reader(dialect='excel-tab')` |
| Colon-separated TXT | 2 | `line.split(':', 2)` |
| Narrative TXT/MD | 3 | 保留章节路径 + 行文本，不在此阶段提取 |
| GBK TXT | 2 | 解码后保留行结构 |
| 外部仓库 YAML/CSV | 5 | 专用提取脚本 → CSV |

**输出**: 33 个原始 CSV，保存在 `output/phase1_converted/`，附带 `phase1_manifest.json`。

**验证**: 每文件 row ≥ 1，GBK 文件含有效中文字符，每种格式抽样 3 行对比原文。

---

### Phase 2 — Schema 归一化

**脚本**: `pipeline_phase2_normalize.py`

核心处理：

- **列映射**: 每个源 30+ 种不同列名 → 统一 schema
- **多协议展开**: 华为速查表 1 行含 Console/Telnet/Web/BootROM 四个协议列 → 展开为 4 行
- **凭据拆分**: `user/pass`、`user:pass`、竖线分隔多值 → 拆成独立行
- **端口识别**: `des账号` 的端口列 → 移入 notes，保留凭据
- **叙事提取**: MD/TXT 中的 `用户名:xxx 密码:xxx` 模式 → 正则提取
- **标签解析**: `常见网络安全产品口令2` 中 `STelnet登录/用户名: admin` → 提取协议+凭据

**原则**: 只拆不删，行数只增不减。

**输出**: 33 个归一化 CSV，保存在 `output/phase2_normalized/`，附带 `phase2_manifest.json`。

**验证**: 每文件行数 ≥ Phase 1，多协议文件行数有预期的倍数增长，零完全空行。

---

### Phase 3 — 合并、清洗、去重、分类

**脚本**: `pipeline_phase3_merge.py`

| 步骤 | 处理内容 | 影响行数 |
|------|---------|---------|
| 3.1 合并 | 加载全部 Phase 2 CSV | 28,779 → 28,779 |
| 3.2 清洗 | blank 归一化、中文描述→notes、Hash密码提取、端口→notes、三重引号清理 | 7,200+ 字段修正 |
| 3.3 厂商规范化 | 150+ 条映射（`huawei`→`华为`）+ 从型号提取厂商 | 3,800+ 条统一 |
| 3.4 去重 | `(vendor, model, version, protocol, username, password)` 键值去重，保留信息更全的行，合并 source_file | -8,923 |
| 3.5 分类 | 9 类关键词匹配（带词边界，防 `abb` 误匹配 `zabbix`） | — |
| 3.6 输出 | Master CSV + 9 分类 CSV + STATS.md | 19,856 |

**原则**: 不掉行（只去重），原始值移入 notes 不丢信息。

**输出**: `output/phase3_merged/` 目录下 11 个文件。

**验证**: 零精确重复、零乱码、零标签残留、已知凭据全部命中、分类抽查正确。

---

## 复现

```bash
# 1. 安装依赖
pip install openpyxl pyyaml

# 2. 从外部仓库提取数据（需先 git clone）
cd raw_archive
git clone https://github.com/0xHJK/TotalPass.git
git clone https://github.com/r0eXpeR/DefaultPassword.git
git clone https://github.com/Awrrays/Frame-DefaultPass.git
git clone https://github.com/MuyeGecko/Userpass-Dict.git
git clone https://github.com/1amfine2333/fwpass.git
cd ..
python3 scripts/extract_external_sources.py

# 3. 三阶段流水线
python3 scripts/pipeline_phase1_convert.py
python3 scripts/pipeline_phase2_normalize.py
python3 scripts/pipeline_phase3_merge.py

# 4. 验证
wc -l output/phase3_merged/default_passwords_master.csv
python3 -c "
import csv
with open('output/phase3_merged/default_passwords_master.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
print(f'{len(rows)} rows, {len(set(r[\"category\"] for r in rows))} categories')
"
```

---

## 参考来源

### 原始来源
- [Phenoelit Default Password List](http://www.phenoelit.de/dpl/dpl.html)
- [DefaultCreds-cheat-sheet](https://github.com/ihebski/DefaultCreds-cheat-sheet)
- [SecLists Default Credentials](https://github.com/danielmiessler/SecLists)
- [ICS Default Passwords](https://github.com/arnaudsoullie/ics-default-passwords)
- [SCADA StrangeLove Default Passwords](https://github.com/arnaudsoullie/ics-default-passwords)

### 外部仓库
- [TotalPass](https://github.com/0xHJK/TotalPass) — YAML 默认密码库（1,051 个设备文件）+ cirt.net 爬虫
- [r0eXpeR/DefaultPassword](https://github.com/r0eXpeR/DefaultPassword) — 默认设备密码 XLSX（4 工作表）
- [Frame-DefaultPass](https://github.com/Awrrays/Frame-DefaultPass) — 框架/设备默认口令表
- [Userpass-Dict](https://github.com/MuyeGecko/Userpass-Dict) — 常见服务默认用户名/密码
- [fwpass](https://github.com/1amfine2333/fwpass) — 常见安全设备默认密码

### 其他
- 中文安全社区收集整理的 TXT/XLSX/MD 汇总
- 各厂商官方文档及公开技术资料

---

## License

数据来自公开来源，遵循各原始来源的许可协议。代码部分（`scripts/`）MIT License。

---

## 更新日志

- **2026-06-28**: 三阶段系统化流水线重建，融合 5 个外部仓库，33 个源文件 → 19,856 条去重数据
