"""Clean-vs-dirty cut across the FULL archive (not just the 99-case cohort).

Uses the OOB counts already computed in manifest_ec_features.csv for every EC
panel. "real OOB" = oob_total - oob_std_global (drops the STD Raw + Global STD
block; Global STD is the x1000 artifact, OOB in ~95% of v2025 panels and the one
version-dependent metric, so removing it makes v2023 and v2025 comparable).

Restricts to the EC_191/192-database versions (v2023_autoscan_192, v2025_brainml).
Characterizes clean vs dirty on the 6 outcomes for the report-paired subset.
"""
import csv, os
import numpy as np
import config, report_parser as rp, labels as L
from harvest_abnormal_archive import robust_paroxysmal, robust_clinical

def robust_labels(rep, age):
    """labels.py for the 4 clean outcomes; space-robust for the 2 corruption-prone
    ones (older reports say 'N one.' / 'no epileptiform abnormalities')."""
    d = {o: L.all_labels(rep, age)[o][0] for o in L.OUTCOMES}
    d["paroxysmal"] = robust_paroxysmal(rep)
    d["clinical_abnorm"] = robust_clinical(rep)
    return d

EC191_VERSIONS = {"v2023_autoscan_192", "v2025_brainml"}

def main():
    rows = list(csv.DictReader(open(os.path.join(config.OUT_DIR,
                "manifest_ec_features.csv"), encoding="utf-8")))
    def num(x):
        try: return int(float(x))
        except Exception: return None
    keep = []
    for r in rows:
        if r["version"] not in EC191_VERSIONS: continue
        if r.get("valid") not in ("True", "1", True): continue
        ot, og = num(r["oob_total"]), num(r["oob_std_global"])
        if ot is None or og is None: continue
        r["real_oob"] = ot - og
        keep.append(r)
    print(f"EC_191-version panels analyzed: {len(keep)} "
          f"(v2023 + v2025); paired w/ report: {sum(1 for r in keep if r['paired']=='True')}")

    ro = np.array([r["real_oob"] for r in keep])
    print(f"\n=== real-OOB distribution (full archive, both versions) ===")
    for k in range(0, 10):
        c = int((ro == k).sum())
        if c: print(f"  {k:2d} OOB: {c:3d}  {'#'*min(c,60)}")
    print(f"  >=10 : {int((ro>=10).sum())};  median {np.median(ro):.0f}, mean {ro.mean():.1f}")

    # by version (robustness check)
    print("\n=== clean/dirty share by version ===")
    for v in sorted(EC191_VERSIONS):
        sub = [r for r in keep if r["version"] == v]
        s = np.array([r["real_oob"] for r in sub])
        cl = int((s <= 1).sum()); dr = int((s >= 5).sum())
        print(f"  {v:22} n={len(sub):3}  clean(<=1) {cl:3} ({100*cl/len(sub):3.0f}%)  "
              f"dirty(>=5) {dr:3} ({100*dr/len(sub):3.0f}%)  median {np.median(s):.0f}")

    clean = [r for r in keep if r["real_oob"] <= 1]
    dirty = [r for r in keep if r["real_oob"] >= 5]
    print(f"\nCLEAN (<=1 real OOB): n={len(clean)}   DIRTY (>=5): n={len(dirty)}")

    # ---- characterize on the 6 outcomes (paired-with-report subset only)
    def labelrate(group, outcome):
        vals = []
        for r in group:
            if r["paired"] != "True" or not r.get("report_path"): continue
            try: rep = rp.parse_report(r["report_path"])
            except Exception: continue
            age = None
            try: age = int(float(r["age"]))
            except Exception: pass
            vals.append(robust_labels(rep, age)[outcome])
        return sum(vals), len(vals)

    print(f"\n{'outcome':16} {'CLEAN %pos':>16} {'DIRTY %pos':>16}")
    for o in L.OUTCOMES:
        cp, cn = labelrate(clean, o); dp, dn = labelrate(dirty, o)
        cs = f"{cp}/{cn}={100*cp/cn:3.0f}%" if cn else "  n/a"
        ds = f"{dp}/{dn}={100*dp/dn:3.0f}%" if dn else "  n/a"
        print(f"{o:16} {cs:>16} {ds:>16}")

    # clean panels the report calls abnormal (panel missed sustained/transient)
    print("\n=== CLEAN panels the Doctor's Report flags abnormal ===")
    n_missed = 0
    for r in clean:
        if r["paired"] != "True" or not r.get("report_path"): continue
        try: rep = rp.parse_report(r["report_path"])
        except Exception: continue
        age = None
        try: age = int(float(r["age"]))
        except Exception: pass
        labs = robust_labels(rep, age)
        flags = [o for o in ("clinical_abnorm","paroxysmal","pdr_freq_abnorm") if labs[o]]
        if flags:
            n_missed += 1
            q = [t for t in r["ec_panel_file"].split() if t.isdigit() and len(t)==4]
            print(f"  {(q[0] if q else r['ec_panel_file'][:14]):8} realOOB={r['real_oob']} {flags} "
                  f":: parox='{(rep.get('paroxysmal') or '')[:34]}'")
    print(f"  ({n_missed} clean panels with a report-flagged abnormality)")

if __name__ == "__main__":
    main()
