"""
Quickstart for the IDEA StatiCa Connection REST API (Connection Rest API 5.0)
using raw HTTP with the `requests` library.

Prereqs:
  - The Connection REST API service running locally (default http://localhost:5000).
    Verify it is up:  GET http://localhost:5000/swagger/5.0/swagger.json
  - A valid IDEA StatiCa license installed on the machine (needed to calculate).
  - pip install requests

Run:
  python quickstart.py path/to/model.ideaCon
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

    def create_empty_project(self, info: dict | None = None) -> dict:
        body = info or {"name": "API project", "countryCode": "ecen"}
        resp = self.session.post(f"{self.base}/projects", json=body)
        resp.raise_for_status()
        return resp.json()

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
        return resp.json()  # [ ConResultSummary { id, passed, resultSummary[] } ]

    def detailed_results(self, project_id: str, connection_ids: list[int]) -> list:
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/results",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.json()  # [ ConnectionCheckRes ]

    def report_pdf(self, project_id: str, connection_id: int) -> bytes:
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/reports/pdf"
        )
        resp.raise_for_status()
        return resp.content

    def download(self, project_id: str) -> bytes:
        resp = self.session.get(f"{self.base}/projects/{project_id}/download")
        resp.raise_for_status()
        return resp.content  # updated .ideaCon bytes

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

    ids = [c["id"] for c in connections]
    print(f"Connections: {[(c['id'], c.get('name')) for c in connections]}")

    try:
        summaries = api.calculate(project_id, ids)
        for s in summaries:
            status = "PASS" if s.get("passed") else "FAIL"
            print(f"  Connection {s['id']}: {status}")
            for chk in s.get("resultSummary") or []:
                if chk.get("skipped"):
                    continue
                # NOTE: checkValue is NOT a uniform 0..1 ratio. Depending on the check it
                # may be a percentage (Analysis=100.0, Welds=98.0) or a small ratio
                # (Plates=0.0069). The service already provides a formatted, human-readable
                # string in unityCheckMessage (e.g. "98.0 < 100%") — prefer it for display.
                ok = "ok" if chk.get("checkStatus") else "NOT OK"
                msg = chk.get("unityCheckMessage") or f"checkValue={chk.get('checkValue')}"
                print(f"    - {chk.get('name')}: {msg} [{ok}]")

        # Save a PDF report and the updated project.
        pdf = api.report_pdf(project_id, ids[0])
        with open("report.pdf", "wb") as f:
            f.write(pdf)
        out = api.download(project_id)
        with open("result.ideaCon", "wb") as f:
            f.write(out)
        print("Saved report.pdf and result.ideaCon")
    finally:
        api.close(project_id)  # release service memory even on error
        print("Project closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python quickstart.py path/to/model.ideaCon")
        sys.exit(1)
    main(sys.argv[1])
