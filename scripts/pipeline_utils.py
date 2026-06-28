#!/usr/bin/env python3
"""Shared utilities for the 3-phase pipeline."""

import re

def has_cjk(s):
    """Check if string contains CJK characters."""
    if not s:
        return False
    for c in s:
        cp = ord(c)
        if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0x20000 <= cp <= 0x2A6DF or 0xF900 <= cp <= 0xFAFF or
            0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF):
            return True
    return False

def detect_encoding(raw_bytes):
    """Detect if bytes are GBK/GB2312/GB18030 encoded. Returns encoding name or None."""
    if not raw_bytes:
        return 'utf-8'
    # Try UTF-8 first
    try:
        raw_bytes.decode('utf-8')
        # Check for GBK high-byte patterns that would indicate GBK in a UTF-8 successful decode
        # If the text has replacement chars or looks garbled, it's not really UTF-8
        decoded = raw_bytes.decode('utf-8')
        if '�' in decoded:
            pass  # fall through to GBK detection
        else:
            return 'utf-8'
    except UnicodeDecodeError:
        pass

    # Check for GBK byte patterns: 0x81-0xFE followed by 0x40-0xFE
    gbk_high_bytes = 0
    for i in range(len(raw_bytes) - 1):
        if 0x81 <= raw_bytes[i] <= 0xFE and 0x40 <= raw_bytes[i+1] <= 0xFE:
            gbk_high_bytes += 1

    # If significant number of GBK-like byte pairs, it's probably GBK
    if gbk_high_bytes > len(raw_bytes) * 0.01:  # >1% GBK pairs
        try:
            raw_bytes.decode('gb18030')
            return 'gb18030'
        except:
            pass
        try:
            raw_bytes.decode('gbk')
            return 'gbk'
        except:
            pass
        try:
            raw_bytes.decode('gb2312')
            return 'gb2312'
        except:
            pass

    # Fallback: try all common Chinese encodings
    for enc in ['gb18030', 'gbk', 'gb2312', 'big5']:
        try:
            decoded = raw_bytes.decode(enc)
            if has_cjk(decoded):
                return enc
        except:
            pass

    return 'utf-8'

def read_file_smart(path):
    """Read a file with automatic encoding detection. Returns (text, encoding_used)."""
    with open(path, 'rb') as f:
        raw = f.read()

    if not raw:
        return '', 'utf-8'

    encoding = detect_encoding(raw)
    try:
        return raw.decode(encoding), encoding
    except:
        return raw.decode('utf-8', errors='replace'), 'utf-8'

def norm_key(s):
    """Normalize string for dedup key comparison."""
    if not s:
        return ''
    s = s.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('（', '(').replace('）', ')').replace('：', ':')
    return s

def norm_blank(s):
    """Normalize blank indicators to empty string. Returns (normalized_value, original_was_blank)."""
    if not s or not s.strip():
        return '', False
    s_stripped = s.strip()
    if s_stripped.lower() in {'(none)', 'none', 'n/a', 'no default', 'blank',
                                '<blank>', '-', '--', 'null', 'nologin',
                                '<n/a>', '(blank)', 'n/a (blank)'}:
        return '', True
    return s_stripped, False

def fmt_note(prefix, value):
    """Format a note label:value pair."""
    return f"[{prefix}: {value}]"

def ensure_note(existing_notes, new_note_text):
    """Append to notes field, avoiding duplicates."""
    if not existing_notes:
        return new_note_text
    if new_note_text in existing_notes:
        return existing_notes
    return existing_notes + '; ' + new_note_text

def extract_vendor_from_model(vendor, model):
    """If vendor is generic, try to extract real vendor from model prefix."""
    from pipeline_config import GENERIC_VENDORS, MODEL_VENDOR_PREFIXES

    if vendor.strip() not in GENERIC_VENDORS:
        return vendor, model

    if not model:
        return vendor, model

    ml = model.strip().lower()
    for prefix, vendor_name in MODEL_VENDOR_PREFIXES.items():
        if ml.startswith(prefix.lower()):
            remaining = model[len(prefix):].strip('-').strip()
            return vendor_name, remaining

    # General fallback: "VendorName-ModelNumber"
    if '-' in model and not model.startswith('-'):
        parts = model.split('-', 1)
        pv = parts[0].strip()
        if pv and len(pv) >= 2 and not pv.isdigit():
            if not re.match(r'^[0-9]+[a-z]*$', pv.lower()):
                return pv, parts[1].strip() if len(parts) > 1 else ''

    return vendor, model

def is_port_number(s):
    """Check if a string is a well-known port number."""
    from pipeline_config import WELL_KNOWN_PORTS
    return s.strip().isdigit() and s.strip() in WELL_KNOWN_PORTS
