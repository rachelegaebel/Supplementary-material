#!/usr/bin/env python3
"""
Test 2 — reproducible analysis (RacqI vs naked, blind rater study)
==================================================================
ONE canonical pipeline. Reproduces every number in Chapter 5 from the raw
Qualtrics exports + the pre-registered blinding key.

Steps:
  0. load the two raw Qualtrics CSVs (experts, non-experts)
  1. self-verify the blinding key against the actual answer text (both surveys)
  2. de-blind (neutral A/B -> arm=RacqI/naked, market=dense/thin/control, id)
  3. per-condition aggregates: mean, median, IQR, n, full 1-5 distribution
  4. per-question contrasts (RacqI - naked) + gradient + retention (dissociation)
  5. Krippendorff's alpha (ordinal), per dimension, per panel
  6. controls attribution (3-case rule) from the RacqI answers' citations

Inputs (all in Test2_dataset/):
  Test 2 - Experts_*.csv, Test 2 - Non-experts_*.csv,
  blinding_key.json, DATASET_32_normalized.md,
  survey_definitions/qualtrics_EXPERTS_full.txt, qualtrics_BUSINESSMEN_full.txt
"""
import os, re, json, glob
import numpy as np, pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../Test2_dataset
KEY  = json.load(open(os.path.join(BASE, "blinding_key.json")))

# ---- QID layouts (fixed by the Qualtrics survey structure) ------------------
# key blocks are letters A..D, in survey order. Each block = 4 question pairs.
# EXPERTS: per pair (answerA_qid, answerB_qid); dims _1=reasoning, _2=evidence
EXP_LAYOUT = {
    "A": [(4,6),(8,10),(12,14),(16,18)],
    "B": [(21,23),(25,27),(29,31),(33,35)],
    "C": [(38,40),(42,44),(46,48),(50,52)],
    "D": [(55,57),(59,61),(63,65),(67,69)],
}
EXP_DIMS = {1: "reasoning", 2: "evidence"}
# NON-EXPERTS: per q (answerA_qid, answerB_qid, forcedchoice_qid); dims _1=trust,_2=action,_3=compet
NE_LAYOUT = {
    "A": [(4,6,7),(9,11,12),(14,16,17),(19,21,22)],
    "B": [(25,27,28),(30,32,33),(35,37,38),(40,42,43)],
    "C": [(46,48,49),(51,53,54),(56,58,59),(61,63,64)],
    "D": [(67,69,70),(72,74,75),(77,79,80),(82,84,85)],
}
NE_DIMS = {1: "trust", 2: "action", 3: "compet"}

def find_csv(pat):
    m = glob.glob(os.path.join(BASE, pat))
    if not m: raise FileNotFoundError(pat)
    return sorted(m)[-1]

def load_qualtrics(path):
    """Robust loader: Qualtrics CSVs have a codes header + 2 metadata rows
    (IT labels, ImportId JSON), sometimes preceded by a title line."""
    raw = open(path, encoding="utf-8").read().splitlines()
    hdr = next(i for i,l in enumerate(raw) if l.startswith("StartDate"))
    df = pd.read_csv(path, sep=";", header=hdr, dtype=str, keep_default_na=False)
    return df.drop(index=[0,1]).reset_index(drop=True)   # drop IT-labels + ImportId rows

# ---- 1. self-verify the key against the actual answer text -------------------
def _norm(x): return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", " ", x).lower())
def verify_key():
    d = open(os.path.join(BASE, "DATASET_32_normalized.md")).read()
    ans = {}
    for m in re.finditer(r"### \[(\d\d)\] · (RacqI-Claude|Naked[^\n]*)\n\n(.*?)(?=\n### \[|\n## \[|\n---\n|\Z)", d, re.S):
        ans[(m.group(1), 'R' if 'RacqI' in m.group(2) else 'N')] = _norm(m.group(3))
    def fp(t, other):
        for s in range(50, max(60, len(t)-60), 40):
            frag = t[s:s+50]
            if len(frag) == 50 and frag not in other: return frag
        return None
    ok_all = True
    for tag, fn in [("EXP","qualtrics_EXPERTS_full.txt"), ("NE","qualtrics_BUSINESSMEN_full.txt")]:
        qtx = open(os.path.join(BASE, "survey_definitions", fn)).read()
        btxt = {mm.group(1): mm.group(2) for mm in
                re.finditer(r"\[\[Block:Block ([A-D])[^\]]*\]\](.*?)(?=\[\[Block:|\Z)", qtx, re.S)}
        for B in "ABCD":
            qs = re.split(r"<h3>Question \d+</h3>", btxt.get(B, ""))[1:]
            for pos, seg in enumerate(qs, 1):
                it = KEY["blocks"][B][pos-1]; idn = it["id"]
                a, b = seg.find("<b>Answer A</b>"), seg.find("<b>Answer B</b>")
                regA, regB = _norm(seg[a:b]), _norm(seg[b:])
                R, N = ans[(idn,'R')], ans[(idn,'N')]
                fR = fp(R, N)
                Rin = "A" if fR and fR in regA else ("B" if fR and fR in regB else "?")
                ok = (Rin == it["RacqI_label"]); ok_all = ok_all and ok
    return ok_all

# ---- 2. de-blind -> tidy long tables ---------------------------------------
def deblind_experts(df):
    rows = []
    for _, r in df.iterrows():
        for B, pairs in EXP_LAYOUT.items():
            for pos, (qa, qb) in enumerate(pairs, 1):
                it = KEY["blocks"][B][pos-1]
                for lab, q in (("A", qa), ("B", qb)):
                    vals = {EXP_DIMS[k]: r.get(f"QID{q}_{k}", "").strip() for k in (1,2)}
                    if not any(vals.values()): continue
                    arm = "RacqI" if lab == it["RacqI_label"] else "naked"
                    rows.append(dict(rater=r["ResponseId"], id=it["id"], density=it["density"], arm=arm,
                                     reasoning=_int(vals["reasoning"]), evidence=_int(vals["evidence"])))
    return pd.DataFrame(rows)

def deblind_nonexperts(df):
    rows, fc = [], []
    for _, r in df.iterrows():
        for B, trips in NE_LAYOUT.items():
            for pos, (qa, qb, qf) in enumerate(trips, 1):
                it = KEY["blocks"][B][pos-1]
                for lab, q in (("A", qa), ("B", qb)):
                    vals = {NE_DIMS[k]: r.get(f"QID{q}_{k}", "").strip() for k in (1,2,3)}
                    if not any(vals.values()): continue
                    arm = "RacqI" if lab == it["RacqI_label"] else "naked"
                    rows.append(dict(rater=r["ResponseId"], id=it["id"], density=it["density"], arm=arm,
                                     trust=_int(vals["trust"]), action=_int(vals["action"]), compet=_int(vals["compet"])))
                fv = r.get(f"QID{qf}", "").strip()
                if fv in ("1","2"):
                    chosen = "A" if fv == "1" else "B"
                    fc.append(dict(id=it["id"], density=it["density"],
                                   chose_racqi=1 if chosen == it["RacqI_label"] else 0))
    return pd.DataFrame(rows), pd.DataFrame(fc)

def _int(s):
    return int(s) if s not in ("", None) else np.nan

# ---- 3. per-condition aggregates -------------------------------------------
def aggregates(df, dims):
    out = []
    for dim in dims:
        for dens in ["dense","thin","control"]:
            for arm in ["RacqI","naked"]:
                s = df[(df.density==dens)&(df.arm==arm)][dim].dropna()
                d = {k: round((s==k).mean()*100) for k in range(1,6)}
                out.append(dict(dim=dim, density=dens, arm=arm, n=len(s),
                                mean=round(s.mean(),2), median=s.median(),
                                iqr=f"{np.percentile(s,25):.0f}-{np.percentile(s,75):.0f}",
                                **{f"pct{k}":d[k] for k in range(1,6)}))
    return pd.DataFrame(out)

# ---- 4. contrasts + retention ----------------------------------------------
def contrasts(E, N, FC):
    rows = []
    for idn in sorted(E.id.unique()):
        dens = E[E.id==idn].density.iloc[0]
        def dm(df, arm, dim): return df[(df.id==idn)&(df.arm==arm)][dim].mean()
        rows.append(dict(id=idn, density=dens,
            d_evidence = dm(E,"RacqI","evidence") - dm(E,"naked","evidence"),
            d_reasoning= dm(E,"RacqI","reasoning")- dm(E,"naked","reasoning"),
            d_trust    = dm(N,"RacqI","trust")    - dm(N,"naked","trust"),
            d_action   = dm(N,"RacqI","action")   - dm(N,"naked","action"),
            d_compet   = dm(N,"RacqI","compet")   - dm(N,"naked","compet"),
            racqi_choice_pct = FC[FC.id==idn].chose_racqi.mean()*100))
    R = pd.DataFrame(rows)
    grad = R.groupby("density")[["d_evidence","d_reasoning","d_trust","d_action","d_compet","racqi_choice_pct"]].mean()
    ret = (grad.loc["thin"] / grad.loc["dense"] * 100).round(0)
    return R, grad.round(2), ret

# ---- 5. Krippendorff's alpha (ordinal) -------------------------------------
def kripp_ordinal(units):
    units = [[int(x) for x in u] for u in units if len(u) >= 2]
    vals = sorted({v for u in units for v in u}); idx = {v:i for i,v in enumerate(vals)}; K = len(vals)
    o = np.zeros((K,K))
    for u in units:
        m = len(u)
        for i in range(m):
            for j in range(m):
                if i != j: o[idx[u[i]], idx[u[j]]] += 1.0/(m-1)
    nc = o.sum(1); n = nc.sum()
    def d2(a,b):
        lo,hi = min(a,b),max(a,b); s = nc[lo:hi+1].sum() - (nc[a]+nc[b])/2.0; return s*s
    Do = sum(o[a,b]*d2(a,b) for a in range(K) for b in range(K))
    De = sum(nc[a]*nc[b]*d2(a,b) for a in range(K) for b in range(K)) / (n-1)
    return 1 - Do/De

def alpha_table(df, dims):
    out = {}
    for dim in dims:
        units = [g[dim].dropna().astype(int).tolist()
                 for _, g in df.groupby(["id","arm"]) if g[dim].notna().sum() >= 2]
        out[dim] = round(kripp_ordinal(units), 3)
    return out

# ---- 6. controls attribution (3-case rule) ---------------------------------
def controls_attribution(E):
    d = open(os.path.join(BASE, "DATASET_32_normalized.md")).read()
    ans = {}
    for m in re.finditer(r"### \[(\d\d)\] · (RacqI-Claude|Naked[^\n]*)\n\n(.*?)(?=\n### \[|\n## \[|\n---\n|\Z)", d, re.S):
        ans[(m.group(1),'R' if 'RacqI' in m.group(2) else 'N')] = m.group(3)
    cite = re.compile(r"\(([A-Z][^()]{2,60}?)\)")
    names = {"13":"Branding","14":"Design/build","15":"Acoustics","16":"Sales"}
    out = []
    for idn, nm in names.items():
        srcs = sorted({c.strip() for c in cite.findall(ans[(idn,'R')])
                       if re.search(r"[A-Za-z]{4,}", c) and not re.match(r"^(RSI|see|Catchment|Lookup)$", c)})
        de = E[(E.id==idn)&(E.arm=='RacqI')].evidence.mean() - E[(E.id==idn)&(E.arm=='naked')].evidence.mean()
        case = "b: curated grounding" if len(srcs) >= 2 else ("a: house-style RED FLAG" if not srcs else "few sources")
        out.append(dict(id=idn, control=nm, distinct_sources=len(srcs), d_evidence=round(de,2), case=case))
    return pd.DataFrame(out)

# ============================ run ============================================
if __name__ == "__main__":
    print("KEY self-verification vs answer text (both surveys):",
          "PASS" if verify_key() else "FAIL — do not trust de-blinding")
    E = deblind_experts(load_qualtrics(find_csv("Test 2 - Experts_*.csv")))
    N, FC = deblind_nonexperts(load_qualtrics(find_csv("Test 2 - Non-experts_*.csv")))
    E.to_csv(os.path.join(BASE,"analysis","experts_tidy.csv"), index=False)
    N.to_csv(os.path.join(BASE,"analysis","nonexperts_tidy.csv"), index=False)
    print(f"\nexperts: {E.rater.nunique()} raters, {len(E)} ratings | "
          f"non-experts: {N.rater.nunique()} raters, {len(N)} ratings, {len(FC)} forced choices")

    print("\n--- per-condition aggregates (experts) ---");     print(aggregates(E, ["evidence","reasoning"]).to_string(index=False))
    print("\n--- per-condition aggregates (non-experts) ---"); print(aggregates(N, ["trust","action","compet"]).to_string(index=False))

    R, grad, ret = contrasts(E, N, FC)
    R.round(2).to_csv(os.path.join(BASE,"analysis","dissociation_pairing.csv"), index=False)
    print("\n--- gradient (mean RacqI-naked contrast by density) ---"); print(grad.to_string())
    print("\n--- retention thin/dense (%) = the dissociation ---");     print(ret.to_string())

    print("\n--- Krippendorff alpha (ordinal) ---")
    print("experts    :", alpha_table(E, ["evidence","reasoning"]))
    print("non-experts:", alpha_table(N, ["trust","action","compet"]))

    print("\n--- controls attribution (3-case rule) ---")
    print(controls_attribution(E).to_string(index=False))
