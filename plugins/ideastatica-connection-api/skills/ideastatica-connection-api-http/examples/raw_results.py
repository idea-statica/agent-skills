"""
Read and INTERPRET raw CBFEM results from the IDEA StatiCa Connection REST API.

POST /api/5/projects/{projectId}/connections/rawresults-text returns an array of JSON
*strings*; each string is a serialized CheckResultsData. Unlike /results and /calculate,
raw results are UNSCALED — SI base units (Pa, metres) and dimensionless ratios (0..1).
This script parses them and converts to the human units the app shows
(stress -> MPa, length -> mm, ratio -> %). See reference/raw-results.md for the full
field reference and the unit table.

Prereqs: service on http://localhost:5000, valid license, pip install requests.
Run:  python raw_results.py path/to/model.ideaCon
"""

import sys
import json
import requests

BASE = "http://localhost:5000/api/5"


def NaN_safe(x):
    """Raw results emit 'NaN'/'Infinity' as strings for fields not applicable to the code or element (e.g. a cjp weld)."""
    return None if isinstance(x, str) else x


class ConnectionApi:
    def __init__(self, base_url: str = BASE):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()

    def connect(self) -> str:
        r = self.session.get(f"{self.base}/clients/connect-client")
        r.raise_for_status()
        cid = r.text.strip().strip('"')
        self.session.headers.update({"ClientId": cid})
        return cid

    def open_project(self, path: str) -> dict:
        with open(path, "rb") as f:
            files = {"ideaConFile": (path, f, "application/octet-stream")}
            r = self.session.post(f"{self.base}/projects/open", files=files)
        r.raise_for_status()
        return r.json()

    def connections(self, project_id: str) -> list:
        r = self.session.get(f"{self.base}/projects/{project_id}/connections")
        r.raise_for_status()
        return r.json()

    def calculate(self, project_id: str, ids: list[int]) -> list:
        r = self.session.post(
            f"{self.base}/projects/{project_id}/connections/calculate", json=ids
        )
        r.raise_for_status()
        return r.json()

    def raw_results(self, project_id: str, ids: list[int]) -> list[dict]:
        # Returns array<string>; each element is itself a JSON document (CheckResultsData)
        # — or the literal "Results for connection {id} failed".
        r = self.session.post(
            f"{self.base}/projects/{project_id}/connections/rawresults-text", json=ids
        )
        r.raise_for_status()
        out = []
        for elem in r.json():
            if elem.startswith("Results for connection"):
                out.append({"_failed": elem})
            else:
                out.append(json.loads(elem))  # the second parse
        return out

    def close(self, project_id: str) -> None:
        self.session.get(f"{self.base}/projects/{project_id}/close").raise_for_status()


def report_raw(data: dict) -> None:
    if data.get("_failed"):
        print("  ", data["_failed"])
        return

    # --- summary: ratio checkValue per checkContext (-1.0 = not calculated) ---
    print("  Summary:")
    for row in (data.get("summary") or {}).values():
        cv = row.get("checkValue")
        if cv is None or cv == -1.0:
            print(f"    {row.get('checkContext'):<16} (not calculated)")
            continue
        # 'analysis' checkValue is applied-load fraction; others are utilization/strain ratios.
        print(
            f"    {row.get('checkContext'):<16} {cv * 100:6.2f}%  "
            f"limit {row.get('limit', 0) * 100:.1f}%  "
            f"[{'ok' if row.get('checkStatus') else 'NOT OK'}]"
        )

    # --- plates: stress in Pa -> MPa, strain ratio -> % ---
    plates = data.get("plates") or {}
    if plates:
        print("  Plates (stress -> MPa, plastic strain -> %):")
        for p in plates.values():
            stress_mpa = NaN_safe(p.get("maxStress"))
            strain = NaN_safe(p.get("maxStrain"))
            limit = NaN_safe(p.get("limitPlasticStrain"))
            stress_txt = f"{stress_mpa / 1e6:.1f} MPa" if stress_mpa is not None else "n/a"
            strain_txt = f"{strain * 100:.2f}%" if strain is not None else "n/a"
            limit_txt = f"{limit * 100:.0f}%" if limit is not None else "n/a"
            ok = "ok" if p.get("checkStatus") else "NOT OK"
            print(
                f"    {p.get('name'):<6} sigma={stress_txt:<11} eps_pl={strain_txt:<7} "
                f"(limit {limit_txt}) t={p.get('thickness', 0) * 1000:.0f}mm "
                f"{p.get('materialName')} [{ok}]"
            )

    # --- welds: unity check ratio -> %, stresses Pa -> MPa, plastic strain ratio -> % ---
    welds = data.get("welds") or {}
    if welds:
        print("  Welds (utilization -> %, stresses -> MPa, plastic strain -> %):")
        # one line per weld, sorted worst-first
        # NOTE: `x or 0` does NOT neutralize 'NaN' — a non-empty string is truthy,
        # so it survives and the next f-string raises "Unknown format code 'f'".
        # Every numeric field must go through NaN_safe(), not just the ones a
        # failing check blanks out: 'NaN' shows up on healthy models too, and a
        # weld (e.g. a `cjp` or `edgeToEdge` one) can read 'NaN' in every field.
        for w in sorted(welds.values(),
                        key=lambda x: NaN_safe(x.get("unityCheckWeld")) or 0, reverse=True):
            uc = NaN_safe(w.get("unityCheckWeld"))
            uc_txt = f"{uc * 100:6.1f}%" if uc is not None else "   n/a "
            ok = "ok" if w.get("checkStatus") else "NOT OK"
            # Stresses are in Pa; equivalent stress is checked against equivalentStressResistance.
            sig_eqv = NaN_safe(w.get("maxEquivalentStress"))
            sig_res = NaN_safe(w.get("equivalentStressResistance"))
            sig_perp = NaN_safe(w.get("sigmaPerpendicular"))
            tau_x = NaN_safe(w.get("taux"))
            tau_y = NaN_safe(w.get("tauy"))
            pl_strain = NaN_safe(w.get("plasticStrain"))
            mpa = lambda x: f"{x / 1e6:.1f}" if x is not None else "n/a"
            eps_txt = f"{pl_strain * 100:.2f}%" if pl_strain is not None else "n/a"
            mm = lambda x: f"{x * 1000:.1f}mm" if x is not None else "n/a"
            print(
                f"    {(w.get('name') or '(unnamed)'):<8} {uc_txt}  "
                f"sigma_eqv={mpa(sig_eqv)}/{mpa(sig_res)} MPa  "
                f"sigma_perp={mpa(sig_perp)}  tau=({mpa(tau_x)},{mpa(tau_y)})  "
                f"eps_pl={eps_txt}"
            )
            print(
                f"             throat={mm(NaN_safe(w.get('thickness')))} "
                f"leg={mm(NaN_safe(w.get('legSize')))} {w.get('weldType2')} [{ok}]"
            )

    # --- bolts: forces in N, unity checks ratio -> %.  forcesAllLoadCases keyed by LE id. ---
    bolts = data.get("bolts") or {}
    if bolts:
        print("  Bolts (forces -> kN, checks -> %):")
        for b in sorted(bolts.values(), key=lambda x: NaN_safe(x.get("maxUnityCheck")) or 0, reverse=True):
            ok = "ok" if b.get("checkStatus") else "NOT OK"
            kn = lambda x: (x / 1000) if isinstance(x, (int, float)) else 0
            print(
                f"    {b.get('name'):<5} Ft={kn(b.get('boltTensionForce')):6.1f}kN "
                f"Fv={kn(b.get('boltShearForce')):6.1f}kN  "
                f"UC_t={(NaN_safe(b.get('unityCheckTension')) or 0)*100:4.0f}% "
                f"UC_v={(NaN_safe(b.get('unityCheckShear')) or 0)*100:4.0f}% "
                f"inter={(NaN_safe(b.get('interactionTensionShear')) or 0)*100:5.1f}%  "
                f"{b.get('boltAssemblyName')} [{ok}]"
            )
            # per-load-effect force vectors [n, qy, qz] in N (governing result is above)
            for le_id, f in (b.get("forcesAllLoadCases") or {}).items():
                print(f"           LE {le_id}: n={f[0]/1000:.1f} qy={f[1]/1000:.1f} qz={f[2]/1000:.1f} kN")

    # --- anchors: steel + concrete failure modes; tension dominates ---
    anchors = data.get("boltsAnchor") or {}
    if anchors:
        print("  Anchors (forces -> kN, checks -> %):")
        for a in sorted(anchors.values(), key=lambda x: NaN_safe(x.get("maxUnityCheck")) or 0, reverse=True):
            ok = "ok" if a.get("checkStatus") else "NOT OK"
            kn = lambda x: (x / 1000) if isinstance(x, (int, float)) else 0
            print(
                f"    {a.get('name'):<5} Ft={kn(a.get('boltTensionForce')):6.1f}kN  "
                f"UC_steel_t={(NaN_safe(a.get('unityCheckTension')) or 0)*100:4.0f}% "
                f"UC_cone={(NaN_safe(a.get('unityCheckConeTensionRes')) or 0)*100:4.0f}% "
                f"inter={(NaN_safe(a.get('interactionTensionShear')) or 0)*100:5.1f}%  "
                f"heff={(NaN_safe(a.get('heff')) or 0)*1000:.0f}mm [{ok}]"  # heff is in m
            )

    # --- concrete block: bearing under base plate ---
    for cb in (data.get("concreteBlocks") or {}).values():
        ok = "ok" if cb.get("checkStatus") else "NOT OK"
        fjd = NaN_safe(cb.get("fjd")); avg = NaN_safe(cb.get("averageStress"))
        print(
            f"  Concrete block {cb.get('name')}: avg stress "
            f"{(avg/1e6 if avg else 0):.1f} / fjd {(fjd/1e6 if fjd else 0):.1f} MPa  "
            f"Nsd={(NaN_safe(cb.get('nsd')) or 0)/1000:.1f}kN  UC={(NaN_safe(cb.get('maxUnityCheck')) or 0)*100:.1f}% [{ok}]"
        )

    # --- base plate shear ---
    for bp in (data.get("basePlateShear") or {}).values():
        ok = "ok" if bp.get("checkStatus") else "NOT OK"
        print(
            f"  Base plate shear {bp.get('name')}: V={(NaN_safe(bp.get('v')) or 0)/1000:.1f}kN  "
            f"transfer={bp.get('shearForceTransferMethod')}  "
            f"UC={(NaN_safe(bp.get('maxUnityCheck')) or 0)*100:.1f}% [{ok}]"
        )

    # --- cost: totalEstimatedCost is the headline; the *Costs lists are itemized breakdowns ---
    cost = data.get("costEstimationResults")
    if cost:
        n_steel = len(cost.get("steelCosts") or [])
        n_weld = len(cost.get("filletWeldCosts") or [])
        print(f"  Estimated cost: total={cost.get('totalEstimatedCost'):.2f} "
              f"({n_steel} steel items, {n_weld} fillet-weld items; "
              f"see steelCosts/filletWeldCosts/boltCosts for the breakdown)")


def main(path: str) -> None:
    api = ConnectionApi()
    api.connect()
    project = api.open_project(path)
    pid = project["projectId"]
    try:
        ids = [c["id"] for c in api.connections(pid)]
        if not ids:
            print("No connections.")
            return
        # rawresults-text calculates the connections itself; no calculate call first.
        for cid, data in zip(ids, api.raw_results(pid, ids)):
            print(f"Connection {cid}:")
            report_raw(data)
    finally:
        api.close(pid)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python raw_results.py path/to/model.ideaCon")
        sys.exit(1)
    main(sys.argv[1])
