"""
Batch calculate, production cost, and multi-connection report
for the IDEA StatiCa Connection REST API (Connection Rest API 5.0)
using raw HTTP with the `requests` library.

What this example does:
  1. Connects a client and opens an existing .ideaCon project.
  2. Calculates ALL connections in the project ASYNCHRONOUSLY
     (POST .../connections/calculate-async, then polls .../calculation-jobs/{jobId}).
  3. For each connection, reads its production cost
     (GET .../connections/{id}/production-cost -> ConProductionCost) and prints it.
  4. Generates a SINGLE multi-connection PDF report and a multi-connection Word report
     by POSTing the array<int> of connection ids to .../reports/pdf and .../reports/word.
  5. Also generates a single-connection PDF (GET .../connections/{id}/reports/pdf).

  WHY ASYNC HERE — a batch is exactly the case that justifies it. The synchronous
  POST .../connections/calculate holds the request open until the LAST connection is
  solved, so a project with many connections forces a long, blind timeout. The async
  job answers 202 at once, reports which connection is being solved as it goes, and
  can be cancelled with DELETE .../calculation-jobs/{jobId}. For a batch, follow
  `connectionsCompleted`: the job's `progress` restarts at 0 for each connection.
  A single quick connection does not need this — see examples/async_calculation.py
  for the async mechanics on their own, plus the ?loadEffectIds= subset selector.

  EXPECT A LONG RUN. The wall time is the solver's, not this script's: it scales with
  (connections) x (active load effects), and a load effect the joint cannot carry is the
  slowest of all — the solver retries it in ever smaller load increments before giving up.
  A batch can therefore run for many minutes. Judge a slow run by the job's `message`
  (it names the load effect being solved) rather than assuming the service is stuck.
  Note the batch endpoints always solve every ACTIVE load effect of every listed
  connection; to restrict the solve, use the per-connection endpoints with
  ?loadEffectIds= (see examples/async_calculation.py).

  IMPORTANT — binary streams: every Report endpoint returns a RAW BINARY FILE STREAM
  (Content-Type: application/octet-stream), NOT JSON. So we read resp.content and write
  the bytes straight to disk. The global camelCase/JSON rules do not apply to these bodies.

Prereqs:
  - The Connection REST API service running locally (default http://localhost:5000).
    Verify it is up:  GET http://localhost:5000/swagger/5.0/swagger.json
  - A valid IDEA StatiCa license installed on the machine (needed to calculate & report).
    Note: HTML report generation is blocked for Trial/Education licenses; PDF/Word are not.
  - pip install requests

Run:
  python batch_report_and_cost.py path/to/model.ideaCon
"""

import os
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
        # SYNCHRONOUS batch: body is a JSON array of ints, e.g. [1] or [1, 2, 3].
        # Kept here for reference — this example uses calculate_async() below.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/calculate",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.json()  # [ ConResultSummary { id, passed, resultSummary[] } ]

    def start_calculate_async(self, project_id: str, connection_ids: list[int]) -> dict:
        # Same body (array of ints), but returns 202 + ConCalculationJob immediately.
        # 409 = another job is already running for this project.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/calculate-async",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.json()

    def get_job(self, project_id: str, job_id: str) -> dict:
        resp = self.session.get(f"{self.base}/projects/{project_id}/calculation-jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()

    def cancel_job(self, project_id: str, job_id: str) -> dict:
        # 202; poll the job until terminal, then read POST .../connections/results per
        # connection — reference/endpoints.md § CalculationJobs.
        resp = self.session.delete(f"{self.base}/projects/{project_id}/calculation-jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()

    def calculate_async(self, project_id: str, connection_ids: list[int]) -> list:
        """Start the batch job and poll it to a terminal status; return its results."""
        job = self.start_calculate_async(project_id, connection_ids)
        print(f"  job {job['jobId']} started for connections {connection_ids} "
              f"(status {job['status']})")
        while job.get("status") not in TERMINAL:
            time.sleep(POLL_SECONDS)
            job = self.get_job(project_id, job["jobId"])
            # `currentConnectionId` = the one being solved right now;
            # `message` = the live solver line; `connectionsCompleted` = the job's progress
            # (`progress` covers only the current connection — endpoints.md § CalculationJobs).
            done = job.get("connectionsCompleted")
            print(f"  {job['status']:9s} {done}/{len(connection_ids)} done, "
                  f"current={job.get('currentConnectionId')} {job.get('message') or ''}")
        if job["status"] != "finished":
            raise RuntimeError(f"calculation {job['status']}: {job.get('error')}")
        return job.get("results") or []

    def production_cost(self, project_id: str, connection_id: int) -> dict:
        # GET .../connections/{connectionId}/production-cost -> ConProductionCost (JSON).
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/production-cost"
        )
        resp.raise_for_status()
        return resp.json()  # ConProductionCost { totalEstimatedCost }

    def report_pdf_multi(self, project_id: str, connection_ids: list[int]) -> bytes:
        # POST .../reports/pdf with a JSON array<int> of connection ids -> ONE combined PDF.
        # Response is a RAW BINARY STREAM (application/octet-stream), not JSON.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/reports/pdf",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.content  # PDF bytes

    def report_word_multi(self, project_id: str, connection_ids: list[int]) -> bytes:
        # POST .../reports/word with a JSON array<int> of connection ids -> ONE combined .docx.
        # Response is a RAW BINARY STREAM (application/octet-stream), not JSON.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/reports/word",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.content  # Word (.docx) bytes

    def report_pdf_single(self, project_id: str, connection_id: int) -> bytes:
        # GET .../connections/{connectionId}/reports/pdf -> single-connection PDF.
        # Response is a RAW BINARY STREAM (application/octet-stream), not JSON.
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/reports/pdf"
        )
        resp.raise_for_status()
        return resp.content  # PDF bytes

    def close(self, project_id: str) -> None:
        # Frees the project from the service's memory. Always do this.
        resp = self.session.get(f"{self.base}/projects/{project_id}/close")
        resp.raise_for_status()


def main(idea_con_path: str) -> None:
    api = ConnectionApi()

    client_id = api.connect()
    print(f"Connected. ClientId = {client_id}")

    project = api.open_project(idea_con_path)
    project_id = project["projectId"]
    print(f"Opened project {project_id}")

    connections = api.get_connections(project_id)
    if not connections:
        print("No connections in project.")
        api.close(project_id)
        return

    # Every step below is expensive: the async job solves each connection, and the
    # reports reuse that run only while nothing in the model changes in between. So
    # this demo caps itself — on a real project pass MAX_CONNECTIONS=0 (or drop the
    # slice) once you know what it will cost. With dozens of connections the uncapped
    # run takes minutes, and the solver is serialized per project, so it does not
    # parallelize away.
    MAX_CONNECTIONS = int(os.environ.get("MAX_CONNECTIONS", "2"))
    all_ids = [c["id"] for c in connections]
    ids = all_ids[:MAX_CONNECTIONS] if MAX_CONNECTIONS else all_ids
    print(f"Connections: {[(c['id'], c.get('name')) for c in connections]}")
    if len(ids) < len(all_ids):
        print(f"  (using the first {len(ids)} of {len(all_ids)} — set "
              f"MAX_CONNECTIONS=0 to use them all)")

    try:
        # 1) Calculate ALL connections at once, asynchronously.
        summaries = api.calculate_async(project_id, ids)
        for s in summaries:
            status = "PASS" if s.get("passed") else "FAIL"
            print(f"  Connection {s['id']}: {status}")
            for chk in s.get("resultSummary") or []:
                if chk.get("skipped"):
                    continue
                # checkValue is not a uniform 0..1 ratio (Analysis/Welds are percentages,
                # Plates is a small ratio). Display the preformatted unityCheckMessage.
                ok = "ok" if chk.get("checkStatus") else "NOT OK"
                msg = chk.get("unityCheckMessage") or f"checkValue={chk.get('checkValue')}"
                print(f"    - {chk.get('name')}: {msg} [{ok}]")

        # 2) Production cost per connection (ConProductionCost).
        #    The only documented field is totalEstimatedCost (double).
        print("Production cost per connection:")
        for cid in ids:
            cost = api.production_cost(project_id, cid)
            print(f"  Connection {cid}: totalEstimatedCost = {cost['totalEstimatedCost']}")

        # 3) Multi-connection reports (binary streams). One PDF / one Word covering all ids.
        pdf_multi = api.report_pdf_multi(project_id, ids)
        with open("report_all.pdf", "wb") as f:
            f.write(pdf_multi)
        word_multi = api.report_word_multi(project_id, ids)
        with open("report_all.docx", "wb") as f:
            f.write(word_multi)
        print(f"Saved report_all.pdf ({len(pdf_multi)} bytes) and "
              f"report_all.docx ({len(word_multi)} bytes)")

        # 4) Single-connection PDF (binary stream) for the first connection.
        pdf_single = api.report_pdf_single(project_id, ids[0])
        with open(f"report_connection_{ids[0]}.pdf", "wb") as f:
            f.write(pdf_single)
        print(f"Saved report_connection_{ids[0]}.pdf ({len(pdf_single)} bytes)")
    finally:
        api.close(project_id)  # release service memory even on error
        print("Project closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_report_and_cost.py path/to/model.ideaCon")
        sys.exit(1)
    main(sys.argv[1])
