from __future__ import annotations

import hashlib, math, random
from typing import Any

from src.randomness import sample_ranges, numpy_seed


def _rng(seed: int | None, salt: str) -> random.Random:
    base = numpy_seed() if seed is None else seed
    digest = hashlib.sha256(f"{base}:{salt}".encode()).hexdigest()[:16]
    return random.Random(int(digest, 16))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _style_by_name(styles: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((s for s in styles if s.get("name") == name), styles[0])


def _candidate(algorithm: str, description: str, style: str, params: dict[str, Any], seed: int, reason: str, tags=None) -> dict[str, Any]:
    return {
        "algorithm": algorithm,
        "algorithm_description": description,
        "style": style,
        "style_name": style,
        "params": params,
        "seed": seed,
        "grain_seed": seed,
        "grain_seed_hex": hex(seed),
        "explanation": reason,
        "reasoning": reason,
        "tags": tags or [],
    }


def generate_style_range_candidates(styles, count: int, profile: dict[str, Any], seed: int | None = None):
    out=[]; r=_rng(seed,"style-range")
    for i in range(count):
        style=styles[i % len(styles)]
        out.append(_candidate("style_range", "Backward-compatible fixed style range sampler.", style["name"], sample_ranges(style["ranges"]), r.randrange(2**32), "Sampled from configured style ranges.", ["Classic"]))
    return out


def generate_adaptive_auto_enhance(styles, count:int, profile, seed=None):
    out=[]; r=_rng(seed,"adaptive")
    base=_style_by_name(styles,"clean_bright")
    mean=profile.get("mean_luminance", .5); std=profile.get("luminance_std", .18); sat=profile.get("mean_saturation", .2)
    for i in range(count):
        p=sample_ranges(base["ranges"])
        p.update({
            "exposure": _clamp((0.52-mean)*0.9 + r.uniform(-.04,.04), -.35, .35),
            "contrast": _clamp(1.0 + (0.22-std)*1.2 + r.uniform(-.06,.08), .82, 1.42),
            "saturation": _clamp(1.0 + (0.20-sat)*0.8 + r.uniform(-.08,.1), .75, 1.35),
            "highlights": -_clamp(profile.get("clipping_ratio",0)*2.5,0,.18),
            "shadows": _clamp((0.45-mean)*0.25, -.08, .14),
        })
        out.append(_candidate("adaptive_auto_enhance","Source-aware exposure, contrast, and saturation correction.","adaptive_auto_enhance",p,r.randrange(2**32),"Adjusted from source luminance, contrast, clipping, and saturation.",["Adaptive"]))
    return out


def generate_palette_cinematic(styles, count:int, profile, seed=None):
    out=[]; r=_rng(seed,"palette")
    base=_style_by_name(styles,"teal_orange_split")
    bias=profile.get("temperature_bias",0.0); spread=profile.get("hue_spread",0.0)
    for i in range(count):
        p=sample_ranges(base["ranges"])
        p["temperature"]=_clamp(-bias*.35 + r.uniform(-.08,.1),-.22,.22)
        p["tint"]=r.uniform(-.04,.06)
        p["split_strength"]=_clamp(.16 + (1-spread)*.18 + r.uniform(-.04,.08),.08,.45)
        p["shadow_tone"]="#0A7C86" if bias >= 0 else "#243B8F"
        p["highlight_tone"]="#FFAA4D" if bias <= .08 else "#FFE1A8"
        out.append(_candidate("palette_cinematic","Palette-aware cinematic split tone based on dominant hues.","palette_cinematic",p,r.randrange(2**32),"Chose temperature and split tones from palette spread and warm/cool bias.",["Palette-aware"]))
    return out


def generate_diversity_explorer(styles,count:int,profile,seed=None):
    out=[]; r=_rng(seed,"diverse")
    for i in range(count):
        style=styles[(i*2) % len(styles)]
        p=sample_ranges(style["ranges"])
        p.update({"exposure": r.uniform(-.32,.32), "contrast": r.uniform(.78,1.55), "saturation": r.uniform(.55,1.55), "temperature": r.uniform(-.22,.22), "vignette": r.uniform(0,.34)})
        out.append(_candidate("diversity_explorer","Experimental wide sampler that explores varied looks.",style["name"],p,r.randrange(2**32),"Intentionally varied exposure, color, and contrast while retaining configured grade controls.",["Experimental"]))
    return out


def generate_monochrome_editorial(styles,count:int,profile,seed=None):
    out=[]; r=_rng(seed,"mono")
    for _ in range(count):
        p={"exposure":r.uniform(-.1,.16),"brightness":0,"contrast":r.uniform(1.05,1.38),"saturation":0.0,"vibrance":0,"temperature":0,"tint":0,"shadows":r.uniform(-.1,.04),"highlights":r.uniform(-.12,.02),"gamma":r.uniform(.9,1.08),"fade":r.uniform(0,.08),"vignette":r.uniform(.05,.28),"grain":r.uniform(.008,.035)}
        out.append(_candidate("monochrome_editorial","Black-and-white editorial grade for shape and contrast.","monochrome_editorial",p,r.randrange(2**32),"Removed chroma to emphasize luminance structure and texture.",["Experimental"]))
    return out


def generate_candidates(styles, profile, algorithm_config: dict[str, Any] | None = None, seed: int | None = None):
    cfg=algorithm_config or {}
    counts=cfg.get("candidate_counts",{})
    enabled=cfg.get("enabled", ["style_range","adaptive_auto_enhance","palette_cinematic","diversity_explorer","monochrome_editorial"])
    funcs={"style_range":generate_style_range_candidates,"adaptive_auto_enhance":generate_adaptive_auto_enhance,"palette_cinematic":generate_palette_cinematic,"diversity_explorer":generate_diversity_explorer,"monochrome_editorial":generate_monochrome_editorial}
    out=[]
    for name in enabled:
        if name in funcs:
            out.extend(funcs[name](styles, int(counts.get(name, cfg.get("default_candidates", 3))), profile, seed))
    return out


def param_distance(a,b):
    keys=["exposure","contrast","saturation","temperature","tint","gamma","fade","vignette"]
    return math.sqrt(sum((float(a.get(k,0))-float(b.get(k,0)))**2 for k in keys)/len(keys))


def select_diverse_candidates(candidates, final_count:int):
    pool=sorted(candidates, key=lambda c: float(c.get("score",{}).get("score",0)), reverse=True)
    selected=[]
    for cand in pool:
        if len(selected)>=final_count: break
        alg_bonus=.08 if all(s.get("algorithm")!=cand.get("algorithm") for s in selected) else 0
        distances=[param_distance(cand.get("params",{}), s.get("params",{})) for s in selected]
        diversity=1.0 if not distances else _clamp(min(distances)/.45,0,1)
        cand["diversity_score"]=round(diversity*100,2)
        cand["overall_selection_score"]=round(float(cand.get("score",{}).get("score",0))*.78 + diversity*22 + alg_bonus*100,2)
        if not selected or diversity>.18 or len(pool)-pool.index(cand) <= final_count-len(selected):
            cand["selection_reason"]=("Best quality candidate" if not selected else "Balanced quality with visual and algorithm diversity")
            selected.append(cand)
    return sorted(selected, key=lambda c: c["overall_selection_score"], reverse=True)[:final_count]
