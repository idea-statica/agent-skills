"""
List the operations that the Connection REST API can only read. Typically these are composite
operations created in the desktop application, such as an end plate or a base plate built as one
assembly.

    python check_operations.py FILE.ideaCon [--service http://localhost:5000]
    python check_operations.py --client-id ID --project-id GUID [--service http://localhost:5000]

With a file, the script opens it under its own ClientId, reads it and closes it again. With
--client-id and --project-id, it reads a project the agent already has open (a second ClientId
cannot see it).

An operation counts as read-only when the plain list GET .../operations returns it but none of
the typed GETs .../operations/{kind} does. The API cannot change such an operation. A typed PUT
or POST at its id answers 409, and only DELETE .../operations removes it, together with every
other operation, the applied templates and the parameters.

Prints one JSON object. "readOnlyCount" is the number of such operations, and "message" is a
sentence for the user. Exit codes: 0 done (also when operations were found), 1 error.
Python 3.8 or later, standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

KINDS = ["weld", "cut", "plate-cut", "bolt-grid", "anchor-grid", "pin-grid", "contact", "contact-grid",
         "negative-member", "negative-plate", "stiffening-member", "stiffening-plate", "work-plane"]


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class Api:
    def __init__(self, base: str, client_id: str | None = None):
        self.base = base.rstrip("/") + "/api/5"
        self.client_id = client_id

    def request(self, method: str, path: str, body: bytes | None = None, content_type: str | None = None):
        req = urllib.request.Request(self.base + path, data=body, method=method)
        if self.client_id:
            req.add_header("ClientId", self.client_id)
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, f"{method} {path} -> {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
        except urllib.error.URLError as e:
            raise ApiError(0, f"Nothing answers at {self.base}: {e.reason}. Is the Connection REST API service "
                              f"running?") from None
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return raw.strip().strip('"')

    def get(self, path: str):
        return self.request("GET", path)

    def open_file(self, path: Path) -> str:
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"ideaConFile\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8") + path.read_bytes() + \
            f"\r\n--{boundary}--\r\n".encode("utf-8")
        project = self.request("POST", "/projects/open", body, f"multipart/form-data; boundary={boundary}")
        return project["projectId"]


def read_only_operations(api: Api, project_id: str) -> dict:
    """Per connection: the operations the plain list returns but no typed GET does."""
    result, missing_kinds = [], set()
    for con in api.get(f"/projects/{project_id}/connections") or []:
        con_path = f"/projects/{project_id}/connections/{con['id']}/operations"
        listed = api.get(con_path) or []
        typed_ids = set()
        for kind in KINDS:
            try:
                typed_ids.update(op.get("id") for op in api.get(f"{con_path}/{kind}") or [])
            except ApiError as e:
                if e.status != 404:
                    raise
                missing_kinds.add(kind)  # an older service without this typed route
        read_only = [{"id": op.get("id"), "name": op.get("name"), "operationType": op.get("operationType"),
                      "active": op.get("active")} for op in listed if op.get("id") not in typed_ids]
        result.append({"id": con["id"], "name": con.get("name"), "operations": len(listed), "readOnly": read_only})
    count = sum(len(c["readOnly"]) for c in result)
    if count:
        parts = [f"{c['name']}: " + ", ".join(f"{o['name']} ({o['operationType']})" for o in c["readOnly"])
                 for c in result if c["readOnly"]]
        message = ("Created in the desktop application, these operations can only be read through the API, not "
                   "changed: " + "; ".join(parts) + ".")
    else:
        message = "Every operation can be read and changed through the API."
    if missing_kinds:
        message += (" This service has no typed route for " + ", ".join(sorted(missing_kinds)) +
                    ", so operations of those kinds are listed as read-only too.")
    return {"connections": result, "readOnlyCount": count, "missingTypedRoutes": sorted(missing_kinds),
            "message": message}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", nargs="?", help="an .ideaCon file to open, check and close")
    parser.add_argument("--service", default="http://localhost:5000", help="base URL of the service")
    parser.add_argument("--client-id", help="ClientId of the session that has the project open")
    parser.add_argument("--project-id", help="projectId of a project that is already open")
    a = parser.parse_args()
    if bool(a.file) == bool(a.project_id) or bool(a.client_id) != bool(a.project_id):
        parser.error("give either FILE, or both --client-id and --project-id")
    try:
        if a.file:
            path = Path(a.file)
            if not path.is_file():
                parser.error(f"{path} does not exist")
            api = Api(a.service)
            api.client_id = api.get("/clients/connect-client")
            project_id = api.open_file(path)
            try:
                report = read_only_operations(api, project_id)
            finally:
                api.get(f"/projects/{project_id}/close")
        else:
            report = read_only_operations(Api(a.service, a.client_id), a.project_id)
    except ApiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
