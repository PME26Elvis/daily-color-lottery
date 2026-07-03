from src.algorithms import generate_candidates, select_diverse_candidates


def styles():
    return [{"name":"clean_bright","ranges":{"exposure":[0,0],"brightness":[0,0],"contrast":[1,1],"saturation":[1,1],"vibrance":[0,0],"temperature":[0,0],"tint":[0,0],"shadows":[0,0],"highlights":[0,0],"gamma":[1,1],"fade":[0,0],"vignette":[0,0],"grain":[0,0]}}]


def profile():
    return {"mean_luminance":0.35,"luminance_std":0.12,"clipping_ratio":0.01,"mean_saturation":0.1,"dominant_palette":["#112233"],"hue_spread":0.2,"temperature_bias":0.1,"profile_bucket":"low-light"}


def test_generate_candidates_returns_consistent_metadata():
    cands = generate_candidates(styles(), profile(), {"enabled":["style_range","adaptive_auto_enhance","palette_cinematic","diversity_explorer"], "default_candidates":1}, seed=1)
    assert {"style_range","adaptive_auto_enhance","palette_cinematic","diversity_explorer"} <= {c["algorithm"] for c in cands}
    for cand in cands:
        assert cand["style"]
        assert isinstance(cand["params"], dict)
        assert cand["grain_seed_hex"].startswith("0x")
        assert cand["algorithm_description"]
        assert cand["explanation"]


def test_select_diverse_candidates_adds_selection_metadata():
    cands=[]
    for i in range(4):
        cands.append({"algorithm":"a" if i<2 else "b", "params":{"exposure":i*.2,"contrast":1+i*.1,"saturation":1}, "score":{"score":90-i}, "style":f"s{i}"})
    selected = select_diverse_candidates(cands, 3)
    assert len(selected) == 3
    assert all("selection_reason" in c for c in selected)
    assert all("diversity_score" in c for c in selected)
    assert all("overall_selection_score" in c for c in selected)
