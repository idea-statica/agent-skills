"""
Read detailed CBFEM check results from the IDEA StatiCa Connection REST API
(Connection Rest API 5.0) using raw HTTP with the `requests` library.

What it does:
  1. Connects a client (gets a ClientId).
  2. Opens a .ideaCon project.
  3. Calculates, then POSTs the connection ids to .../connections/results, which READS
     the last calculation and returns one ConnectionCheckRes per connection (the
     detailed, structured result). /results does NOT calculate: called before
     /calculate, or after an edit that invalidated the results, it answers 200 with
     every checkRes* array empty and no message saying why.
  4. Walks each result's check categories (summary, plates, welds, bolts, anchors,
     buckling) and prints the worst unity check per category plus an overall pass/fail.
  5. Surfaces any validation/calculation messages (OpenMessages) returned.

Notes on the result shape (per io-shapes.md, Calculation group):
  - Plates are checked by strain/stress (maxStrain / maxStress), NOT a unityCheck ratio,
    so there is no unity-check value to report for plates -- only pass/fail + extrema.
  - Buckling results carry a buckling `factor` (not a unity check); we report the
    smallest (worst) factor.
  - Welds / bolts / anchors each carry a `unityCheck` (utilisation, in percent).
  - The summary rows carry `checkValue` (utilization) + `checkStatus`.

Prereqs:
  - The Connection REST API service running locally (default http://localhost:5000).
    Verify it is up:  GET http://localhost:5000/swagger/5.0/swagger.json
  - A valid IDEA StatiCa license installed on the machine (needed to calculate).
  - pip install requests

Run:
  python detailed_results.py path/to/model.ideaCon
"""

import sys
import requests

BASE = "http://localhost:5000/api/5"


class ConnectionApi:
    """Thin wrapper that keeps the ClientId header on every request."""

    def __init__(self, base_url: str = BASE):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.client_id = None

    def connect(self) -> str:
        # connect-client is one of the only endpoints that does NOT need ClientId.
        # It returns a RAW GUID string (text/plain), not JSON.
        resp = self.session.get(f"{self.base}/clients/connect-client")
        resp.raise_for_status()
        self.client_id = resp.text.strip().strip('"')
        # From now on, attach ClientId to every request.
        self.session.headers.update({"ClientId": self.client_id})
        return self.client_id

    def open_project(self, idea_con_path: str) -> dict:
        # multipart/form-data; the file field MUST be named "ideaConFile".
        with open(idea_con_path, "rb") as f:
            files = {"ideaConFile": (idea_con_path, f, "application/octet-stream")}
            resp = self.session.post(f"{self.base}/projects/open", files=files)
        resp.raise_for_status()
        return resp.json()  # ConProject { projectId, projectInfo, connections[] }

    def get_connections(self, project_id: str) -> list:
        resp = self.session.get(f"{self.base}/projects/{project_id}/connections")
        resp.raise_for_status()
        return resp.json()  # [ ConConnection { id, name, ... } ]

    def calculate(self, project_id: str, connection_ids: list[int]) -> list:
        # Body is a JSON array of ints, e.g. [1] or [1, 2, 3].
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/calculate",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.json()  # [ ConResultSummary ]

    def detailed_results(self, project_id: str, connection_ids: list[int]) -> list:
        # Body is a JSON array of ints, e.g. [1] or [1, 2, 3].
        # IMPORTANT: you must call calculate() first in the SAME client session — otherwise
        # the result arrays come back empty. /results returns the already-computed results.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/results",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.json()  # [ ConnectionCheckRes ]

    def close(self, project_id: str) -> None:
        # Frees the project from the service's memory. Always do this.
        resp = self.session.get(f"{self.base}/projects/{project_id}/close")
        resp.raise_for_status()


def worst_unity(rows: list, value_field: str) -> tuple:
    """Return (max_value, all_passed, count) over rows carrying a unityCheck-style
    ratio field plus a `checkStatus` bool. Rows are CheckResWeld / CheckResBolt /
    CheckResAnchor (welds also have items[], but we only read the documented fields).
    """
    worst = None
    all_ok = True
    for r in rows:
        # checkStatus is documented for weld/bolt/anchor: true = passed.
        if not r.get("checkStatus", True):
            all_ok = False
        v = r.get(value_field)
        # An N/A result arrives as the STRING 'NaN' (or 'Infinity'), not as null,
        # so `v is not None` lets it through and the caller's :.1f then raises
        # "Unknown format code 'f'". Several welds of one connection can all read
        # 'NaN' (e.g. `cjp` or `edgeToEdge` welds) — this is the difference between a
        # report and a crash. Same trap in raw_results.py; see its NaN_safe().
        if isinstance(v, str):
            continue
        if v is not None and (worst is None or v > worst):
            worst = v
    return worst, all_ok, len(rows)


def print_category(label: str, rows: list, value_field: str) -> None:
    """Print the worst unity check for a weld/bolt/anchor category.
    NOTE: in the simplified /results endpoint, `unityCheck` is ALREADY A PERCENT
    (in the simplified endpoint these are already percentages). Do NOT multiply
    by 100. (Raw results from rawresults-text are the 0..1 ratio instead — see raw_results.py.)"""
    if not rows:
        print(f"  {label}: none")
        return
    worst, all_ok, n = worst_unity(rows, value_field)
    status = "PASS" if all_ok else "FAIL"
    if worst is None:
        print(f"  {label}: {n} item(s), worst unity n/a [{status}]")
    else:
        print(f"  {label}: {n} item(s), worst unity {worst:.1f}% [{status}]")


def print_plates(rows: list) -> None:
    """Plates are strain/stress checked (CheckResPlate: name, checkStatus, loadCaseId,
    maxStrain, maxStress, items). There is no unityCheck ratio for plates, so we report
    pass/fail and the worst strain/stress instead."""
    if not rows:
        print("  Plates: none")
        return
    all_ok = True
    worst_strain = None
    worst_stress = None
    for r in rows:
        if not r.get("checkStatus", True):
            all_ok = False
        s = r.get("maxStrain")
        if s is not None and (worst_strain is None or s > worst_strain):
            worst_strain = s
        st = r.get("maxStress")
        if st is not None and (worst_stress is None or st > worst_stress):
            worst_stress = st
    status = "PASS" if all_ok else "FAIL"
    # In the simplified /results, maxStress is MPa and maxStrain is the plastic strain on a
    # ratio×10000 scale (so eps_pl[%] = maxStrain/100). The app rounds eps_pl to 0.0 % when
    # small. (rawresults-text gives maxStrain as a 0..1 ratio instead.)
    strain_txt = f"{worst_strain / 100:.2f}%" if worst_strain is not None else "n/a"
    stress_txt = f"{worst_stress:.1f} MPa" if worst_stress is not None else "n/a"
    print(
        f"  Plates: {len(rows)} item(s), max plastic strain {strain_txt}, "
        f"max stress {stress_txt} [{status}]"
    )


def print_buckling(rows: list) -> None:
    """Buckling results (BucklingRes: loadCaseId, shape, factor). These carry a buckling
    factor, not a unity check, so we report the smallest (most critical) factor."""
    if not rows:
        print("  Buckling: none (not analyzed or no shapes)")
        return
    factors = [r.get("factor") for r in rows if r.get("factor") is not None]
    if factors:
        print(f"  Buckling: {len(rows)} shape(s), min factor {min(factors):.2f}")
    else:
        print(f"  Buckling: {len(rows)} shape(s), factor n/a")


def print_summary_rows(rows: list) -> None:
    """CheckResSummary rows: checkValue, checkStatus, loadCaseId, name, unityCheckMessage,
    skipped. IMPORTANT: in the simplified endpoints `checkValue` is NOT a uniform unit —
    it is a percent for Analysis/Welds (e.g. 85.35) but a small ratio for Plates
    (e.g. 0.006). So we do NOT compute a number from it; we display the preformatted
    `unityCheckMessage` (which matches the GUI) and fall back to the raw checkValue only
    for context. Skipped rows must be ignored entirely."""
    all_ok = True
    printed = 0
    for r in rows:
        if r.get("skipped"):
            continue
        printed += 1
        if not r.get("checkStatus", True):
            all_ok = False
        name = r.get("name")
        ok = "ok" if r.get("checkStatus") else "NOT OK"
        msg = r.get("unityCheckMessage") or f"checkValue={r.get('checkValue')}"
        print(f"    - {name}: {msg} [{ok}]")
    if printed == 0:
        print("    (no summary rows)")
    status = "PASS" if all_ok else "FAIL"
    print(f"  Summary overall: [{status}]")


def print_messages(messages: dict | None) -> None:
    """OpenMessages: { messages: [ OpenMessage ] }, each with `number` and `description`.
    A `$type` or `propertyName`, when a message carries one, is printed too."""
    if not messages:
        return
    items = messages.get("messages") or []
    if not items:
        return
    print("  Messages (OpenMessages):")
    for m in items:
        kind = (m.get("$type") or "").split(",")[0].split(".")[-1] or "Message"
        desc = m.get("description") or ""
        prop = m.get("propertyName")
        num = m.get("number")
        where = f" ({prop})" if prop else ""
        num_txt = f" #{num}" if num is not None else ""
        print(f"    [{kind}{num_txt}]{where} {desc}".rstrip())


def main(idea_con_path: str) -> None:
    api = ConnectionApi()

    client_id = api.connect()
    print(f"Connected. ClientId = {client_id}")

    project = api.open_project(idea_con_path)
    project_id = project["projectId"]
    print(f"Opened project {project_id}")

    # Everything after the project is open must go through the finally so the
    # project is always released from the service cache, even on error.
    try:
        connections = api.get_connections(project_id)
        if not connections:
            print("No connections in project.")
            return

        ids = [c["id"] for c in connections]
        print(f"Connections: {[(c['id'], c.get('name')) for c in connections]}")

        # Must calculate first (same session) — then /results returns the structured data.
        api.calculate(project_id, ids)
        results = api.detailed_results(project_id, ids)

        for res in results:
            # ConnectionCheckRes documented fields: name, connectionID, id, messages,
            # checkResSummary, checkResPlate, checkResWeld, checkResBolt,
            # checkResAnchor, checkResConcreteBlock, bucklingResults.
            con_id = res.get("id")
            con_name = res.get("name")
            print(f"\n=== Connection {con_id} ({con_name}) ===")

            summary = res.get("checkResSummary") or []
            plates = res.get("checkResPlate") or []
            welds = res.get("checkResWeld") or []
            bolts = res.get("checkResBolt") or []
            anchors = res.get("checkResAnchor") or []
            buckling = res.get("bucklingResults") or []
            # Note: checkResConcreteBlock is also documented (per-concrete-block results)
            # but is out of scope for this example's per-category walk.

            # Per-category worst unity check / extrema:
            print_plates(plates)
            print_category("Welds", welds, "unityCheck")
            print_category("Bolts", bolts, "unityCheck")
            print_category("Anchors", anchors, "unityCheck")
            print_buckling(buckling)

            # Summary rows give the overall per-check utilization + status.
            print("  Summary rows:")
            print_summary_rows(summary)

            # Overall pass/fail: derive from the summary rows' checkStatus.
            # (A connection passes only if every non-skipped summary check passes.)
            overall_ok = all(
                r.get("checkStatus", False)
                for r in summary
                if not r.get("skipped")
            )
            overall = "PASS" if (summary and overall_ok) else "FAIL"
            print(f"  OVERALL: {overall}")

            # Surface any validation / calculation messages.
            print_messages(res.get("messages"))
    finally:
        api.close(project_id)  # release service memory even on error
        print("\nProject closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python detailed_results.py path/to/model.ideaCon")
        sys.exit(1)
    main(sys.argv[1])
