"""
Asynchronous calculation with job polling, and calculating a load-effect SUBSET,
for the IDEA StatiCa Connection REST API (Connection Rest API 5.0)
using raw HTTP with the `requests` library.

What this example does:
  1. Connects a client and opens an existing .ideaCon project.
  2. Reads the connection's load effects.
  3. Starts an ASYNC job for a SUBSET of the load effects (all but the last; on a model with one
     load effect the subset is that one)
     (POST .../connections/{id}/calculate-async?loadEffectIds=1&loadEffectIds=2),
     then polls GET .../calculation-jobs/{jobId} until the status is terminal.
  4. Prints the result summary the finished job carries.
  5. Shows the same subset selector on the SYNCHRONOUS single-connection endpoint.

WHY ASYNC — it is not faster; the solver takes just as long. It buys three things:
  - No long-held request. The synchronous POST .../connections/calculate keeps the
    socket open for the whole solve (minutes on a large project), so the client needs a
    timeout longer than the run; dropping it cancels the calculation and can leave partial
    results (reference/endpoints.md § Calculation). calculate-async answers 202
    immediately.
  - Visible progress. The job's `message` names the load effect and solver iteration
    being computed right now; a synchronous call is a black box until it returns.
  - Cancellable. DELETE .../calculation-jobs/{jobId} cancels the job (202); poll the
    job until it is terminal (reference/endpoints.md § CalculationJobs).

WHY THE SUBSET — `?loadEffectIds=` solves only the listed load effects, EVEN IF the
others are active. In a parametric loop, restricting each iteration to the few governing
load effects is usually the single biggest saving. The selector works on both the
synchronous and the async single-connection endpoints; the plural body-array endpoints
(POST .../connections/calculate) have no such option.

SIZING A LOAD RAMP — if you are generating a series of load effects (a sweep, a batch,
a "how much can this joint take" study), do NOT guess the top of the range: a load effect
the joint cannot carry is the slowest of all, because the solver retries it in ever
smaller increments before giving up. Ask the engine instead. Set the connection's
analysisType to "total_Design" (the desktop's "Joint design resistance") and read the
multiplier from rawresults-text for ONE load effect - the selector goes on rawresults-text
itself, which calculates:

    PUT  .../connections/{id}          the full GET body, "analysisType":"total_Design"
    POST .../connections/{id}/rawresults-text?loadEffectIds=<one LE>
        -> totalCapacity["<loadCaseId>"].appliedLoadPercentage   e.g. 4.55
    PUT  .../connections/{id}          the full GET body, "analysisType":"stress_Strain"   # restore

(Always send the whole connection body you read — reference/io-shapes.md
§ PUT /api/5/projects/{projectId}/connections/{connectionId}.)

That factor scales THAT load effect to the joint's resistance, so a ramp at
0.5 / 0.7 / 0.9 x factor stays inside the envelope and every run converges quickly. With
several load effects there is one entry per load effect (keyed by loadCaseId) — take the
MINIMUM, as the desktop report does. See reference/raw-results.md (`totalCapacity`) and
reference/schemas.md (analysis-type table).

Prereqs:
  - The Connection REST API service running locally (default http://localhost:5000).
  - A valid IDEA StatiCa license installed on the machine (needed to calculate).
  - pip install requests

Run:
  python async_calculation.py path/to/model.ideaCon

The connection must already carry load effects — this example calculates an existing
model, it does not author one. To build a model from scratch over the typed API, see
examples/typed_operations.py.
"""

import sys
import time

import requests

BASE = "http://localhost:5000/api/5"
POLL_SECONDS = 1.0
TERMINAL = {"finished", "failed", "cancelled"}


class ConnectionApi:
    """Thin wrapper that keeps the ClientId header on every request."""

    def __init__(self, base_url: str = BASE):
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.client_id = None

    def connect(self) -> str:
        # connect-client does NOT need ClientId and returns a RAW GUID as
        # text/plain — never resp.json() here, it would raise.
        resp = self.session.get(f"{self.base}/clients/connect-client")
        resp.raise_for_status()
        self.client_id = resp.text.strip().strip('"')
        self.session.headers.update({"ClientId": self.client_id})
        return self.client_id

    def open_project(self, idea_con_path: str) -> dict:
        with open(idea_con_path, "rb") as f:
            files = {"ideaConFile": (idea_con_path, f, "application/octet-stream")}
            resp = self.session.post(f"{self.base}/projects/open", files=files)
        resp.raise_for_status()
        return resp.json()

    def get_load_effects(self, project_id: str, connection_id: int) -> list:
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/load-effects",
            params={"isPercentage": "false"},
        )
        resp.raise_for_status()
        return resp.json()

    def start_async(self, project_id: str, connection_id: int,
                    load_effect_ids: list[int] | None = None) -> dict:
        # Repeatable query parameter: ?loadEffectIds=1&loadEffectIds=2&...
        # requests emits that shape from a list value. Omit it to solve them all.
        params = {"loadEffectIds": load_effect_ids} if load_effect_ids else None
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/calculate-async",
            params=params,
        )
        # 202 Accepted; 409 means a job is already running for this project.
        resp.raise_for_status()
        return resp.json()  # ConCalculationJob

    def get_job(self, project_id: str, job_id: str) -> dict:
        resp = self.session.get(f"{self.base}/projects/{project_id}/calculation-jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()

    def cancel_job(self, project_id: str, job_id: str) -> dict:
        # 202; poll get_job until terminal, then read POST .../connections/results per
        # connection — reference/endpoints.md § CalculationJobs.
        resp = self.session.delete(f"{self.base}/projects/{project_id}/calculation-jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()

    def calculate_one(self, project_id: str, connection_id: int,
                      load_effect_ids: list[int] | None = None) -> dict:
        # Synchronous single-connection calculate — returns ONE ConResultSummary
        # object (the plural endpoint returns an ARRAY).
        params = {"loadEffectIds": load_effect_ids} if load_effect_ids else None
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/calculate",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self, project_id: str) -> None:
        resp = self.session.get(f"{self.base}/projects/{project_id}/close")
        resp.raise_for_status()


def print_summary(summary: dict) -> None:
    if not summary:
        print("    (no result summary)")
        return
    print(f"    passed = {summary.get('passed')}")
    for chk in summary.get("resultSummary") or []:
        if chk.get("skipped"):
            continue
        ok = "ok" if chk.get("checkStatus") else "NOT OK"
        msg = chk.get("unityCheckMessage") or f"checkValue={chk.get('checkValue')}"
        print(f"    - {chk.get('name')}: {msg} [{ok}]")


def poll_until_done(api: ConnectionApi, project_id: str, job: dict) -> dict:
    """Poll a job to a terminal status, printing what the solver is doing."""
    while job.get("status") not in TERMINAL:
        time.sleep(POLL_SECONDS)
        job = api.get_job(project_id, job["jobId"])
        # `message` carries the live solver line (load effect + iteration).
        # `progress` is a 0..1 fraction for the CURRENT connection (endpoints.md § CalculationJobs).
        print(f"    {job['status']:9s} {job.get('progress') or 0.0:.2f}  "
              f"{job.get('message') or ''}")
    return job


def main(idea_con_path: str) -> None:
    api = ConnectionApi()
    print(f"Connected. ClientId = {api.connect()}")

    project = api.open_project(idea_con_path)
    project_id = project["projectId"]
    connections = project.get("connections") or []
    if not connections:
        print("No connections in project.")
        api.close(project_id)
        return
    connection_id = connections[0]["id"]
    print(f"Opened project {project_id}, using connection {connection_id}")

    try:
        effects = api.get_load_effects(project_id, connection_id)
        print(f"Load effects: {[(e['id'], e.get('name')) for e in effects]}")
        if not effects:
            print("The connection has no load effects — nothing to calculate.")
            return

        # --- 1) async job over a SUBSET of the load effects -------------------
        # Deliberately leave the last load effect out: it stays active but is
        # never solved, which is the whole point of the selector.
        subset = [e["id"] for e in effects[:-1]] or [effects[0]["id"]]
        job = api.start_async(project_id, connection_id, subset)
        print(f"Started job {job['jobId']} for load effects {subset} "
              f"(status {job['status']})")

        job = poll_until_done(api, project_id, job)
        print(f"Job {job['status']}: "
              f"{job.get('connectionsCompleted')} of {len(job.get('connectionIds') or [])} "
              f"connection(s) completed")

        if job["status"] == "failed":
            print(f"  error: {job.get('error')}")
        else:
            # `results` holds one ConResultSummary per calculated connection.
            for summary in job.get("results") or []:
                print(f"  connection {summary.get('id')}:")
                print_summary(summary)

        # --- 2) the same subset selector, synchronously -----------------------
        # Use this when the solve is short enough that polling is not worth it.
        single = api.calculate_one(project_id, connection_id, subset)
        print(f"Synchronous calculate of the same subset:")
        print_summary(single)
    finally:
        api.close(project_id)
        print("Project closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python async_calculation.py path/to/model.ideaCon")
        sys.exit(1)
    main(sys.argv[1])
