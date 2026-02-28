#!/usr/bin/env python3
"""
vibe_engine_patcher.py  —  Run from the same folder as vibe_engine.py
    python vibe_engine_patcher.py
Produces vibe_engine_fixed.py  with all 3 Indian Hip Hop fixes applied.
"""
import re, sys

SRC  = "vibe_engine.py"
DEST = "vibe_engine_fixed.py"

try:
    with open(SRC, "r", encoding="utf-8") as f:
        c = f.read()
except FileNotFoundError:
    sys.exit(f"ERROR: {SRC} not found. Run this from the same folder.")

orig_len = len(c)
print(f"Loaded {SRC}  ({orig_len:,} chars)")

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 1 — LANGUAGE_TAG_MAP Hindi: route "hype" → "indian hip hop"
#   Strategy: find "Hindi": { then replace "hype": "bollywood" within the
#   next 800 chars only (avoids needing to find the exact block end).
# ═══════════════════════════════════════════════════════════════════════════════
HINDI_ANCHOR = '"Hindi": {'
hi_s = c.find(HINDI_ANCHOR)
if hi_s < 0:
    HINDI_ANCHOR = '"Hindi" : {'
    hi_s = c.find(HINDI_ANCHOR)

if hi_s >= 0:
    WINDOW = 900
    chunk    = c[hi_s : hi_s + WINDOW]
    new_chunk = re.sub(
        r'("hype"\s*:\s*)"bollywood"',
        r'\1"indian hip hop"',
        chunk,
        count=1
    )
    c    = c[:hi_s] + new_chunk + c[hi_s + WINDOW:]
    fix1 = '"indian hip hop"' in c[hi_s : hi_s + WINDOW]
else:
    fix1 = False

print(f"FIX 1  Hindi hype -> indian hip hop: {'OK' if fix1 else 'FAILED (Hindi block not found)'}")

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2 — SYNONYMS: inject Indian Hip Hop aliases after dholak entry
# ═══════════════════════════════════════════════════════════════════════════════
INDIAN_HH = """
# -- Indian / Desi Hip Hop --------------------------------------------------
"indian hip hop":   ["hype", "desi"],
"gully rap":        ["hype", "desi"],
"desi rap":         ["hype", "desi"],
"mumbai rap":       ["hype", "desi"],
"hindi rap":        ["hype", "desi"],
"desi drill":       ["hype", "desi"],
"desi trap":        ["hype", "desi"],
"gully boy":        ["hype", "desi"],
"underground desi": ["hype", "desi"],
"kr$na":            ["hype", "desi"],
"seedhe maut":      ["hype", "desi"],
"mc stan":          ["hype", "desi"],
"divine rap":       ["hype", "desi"],
"emiway":           ["hype", "desi"],
"raftaar vibes":    ["hype", "desi"],
"prabh deep":       ["hype", "desi"],
"bohemia vibes":    ["hype", "punjabi"],
"dino james":       ["hype", "desi"],
"brodha v":         ["hype", "desi"],
"""

fix2 = False
for anchor in [
    '"dholak": ["desi", "party"],',
    '"dholak":["desi","party"],',
    '"desi romance": ["romantic", "desi"],',
]:
    if anchor in c:
        c    = c.replace(anchor, anchor + INDIAN_HH, 1)
        fix2 = '"gully rap"' in c
        break

print(f"FIX 2  Indian HH synonyms injected:  {'OK' if fix2 else 'FAILED (anchor not found)'}")

# ═══════════════════════════════════════════════════════════════════════════════
# FIX 3 — VIBE_MAP hype genres: append Desi Hip Hop genre tags
#   Strategy: find "hype": { then find its "genres": [...] list and append.
# ═══════════════════════════════════════════════════════════════════════════════
DESI_GENRES = ', "Desi Hip Hop", "Indian Hip Hop", "Gully Rap", "Hindi Rap", "Desi Drill", "Mumbai Rap"'

hype_i   = c.find('"hype": {')
genres_i = c.find('"genres":', hype_i)
genres_e = c.find('],', genres_i)          # closing ], of the genres list

fix3 = False
if genres_i > 0 and genres_e > genres_i:
    if 'Desi Hip Hop' not in c[genres_i:genres_e]:
        c    = c[:genres_e] + DESI_GENRES + c[genres_e:]
        fix3 = 'Desi Hip Hop' in c
    else:
        fix3 = True   # already applied
        print("       (Desi Hip Hop genres already present, skipping)")

print(f"FIX 3  Desi Hip Hop in hype genres:  {'OK' if fix3 else 'FAILED (hype genres not found)'}")

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════
with open(DEST, "w", encoding="utf-8") as f:
    f.write(c)

all_ok = fix1 and fix2 and fix3
print()
print(f"{'ALL FIXES APPLIED' if all_ok else 'PARTIAL — see failures above'}")
print(f"Written: {DEST}  ({len(c):,} chars,  delta {len(c) - orig_len:+d})")
if all_ok:
    print("Rename to vibe_engine.py when ready.")
