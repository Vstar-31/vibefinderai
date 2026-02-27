#!/usr/bin/env python3
"""
vibe_engine_patcher.py - v6.0 Fix 2 Patcher
Run once from same directory as vibe_engine.py.
Creates vibe_engine.py.bak before patching.
"""
import re, shutil

SRC = "vibe_engine.py"
BAK = "vibe_engine.py.bak"

with open(SRC, "r", encoding="utf-8") as f:
    src = f.read()

shutil.copy(SRC, BAK)
print(f"Backup saved to {BAK}")

# PATCH 1: Inject constants after BLEED dict
CONST_BLOCK = """

# =============================================================
# FIX 2 v6.0: CULTURAL VIBE TRUMP CARD
# Cultural vibes get a post-scoring multiplier so broad generic
# vibes (party, chill, hype) cannot drown them out.
# Any cultural vibe with at least 1 keyword hit gets x1.6.
# =============================================================
CULTURAL_VIBE_NAMES = {"desi", "punjabi", "haryanvi", "bollywoodsad", "punjabisoft", "romantic"}
CULTURAL_BOOST_MULTIPLIER = 1.6
"""

# Anchor: last entry in BLEED dict
bleed_end_pattern = r'("chill":\s*0\.05\s*\})'
if re.search(bleed_end_pattern, src):
    src = re.sub(bleed_end_pattern, r"\1" + CONST_BLOCK, src, count=1)
    print("PATCH 1: constants injected after BLEED dict.")
else:
    # fallback: inject before analyze_vibe_algorithm definition
    marker = "def analyze_vibe_algorithm"
    idx = src.find(marker)
    if idx != -1:
        src = src[:idx] + CONST_BLOCK + "\n" + src[idx:]
        print("PATCH 1 (fallback): constants injected before analyze_vibe_algorithm.")
    else:
        print("PATCH 1 FAILED: add CULTURAL_VIBE_NAMES manually.")

# PATCH 2: Inject boost loop after BLEED application inside analyze_vibe_algorithm
BOOST_LINES = [
    "",
    "    # FIX 2 v6.0: CULTURAL VIBE TRUMP CARD BOOST",
    "    # Applied right after BLEED so cultural vibes survive the sort against party/hype.",
    "    for _cv in CULTURAL_VIBE_NAMES:",
    "        if scores.get(_cv, 0) > 0:",
    "            scores[_cv] *= CULTURAL_BOOST_MULTIPLIER",
    "",
]
BOOST_BLOCK = "\n".join(BOOST_LINES)

anchor = "pre_bleed[vibe] * factor"
anchor_idx = src.find(anchor)
if anchor_idx == -1:
    anchor = "pre_bleed.get(vibe"
    anchor_idx = src.find(anchor)

if anchor_idx != -1:
    line_end = src.find("\n", anchor_idx) + 1
    src = src[:line_end] + BOOST_BLOCK + src[line_end:]
    print("PATCH 2: Cultural boost loop injected after BLEED application.")
else:
    # fallback: inject before STEP 8 / result assembly
    for step8_marker in ["# STEP 8", "positive_scores", "total_raw_score"]:
        idx = src.find(step8_marker)
        if idx != -1:
            src = src[:idx] + BOOST_BLOCK + "\n" + src[idx:]
            print(f"PATCH 2 (fallback): boost loop injected before {step8_marker!r}.")
            break
    else:
        print("PATCH 2 FAILED: add boost loop manually before result assembly.")

with open(SRC, "w", encoding="utf-8") as f:
    f.write(src)

print("Done. vibe_engine.py patched in place.")
print(f"Original backed up to {BAK}")
print("Run your test suite to verify, then delete the .bak file.")