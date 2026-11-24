"""
Define load effects then calculate — IDEA StatiCa Connection Rest API 5.0.

This example shows the full load-effects workflow against the local
the Connection REST API service using the raw `requests` library:

  1. connect (obtain a ClientId) and open a .ideaCon project
  2. pick the first connection
  3. list its members (GET .../members) to learn the real member ids and
     each member's connectedBy / isContinuous, which decide on which side
     of the node a loading's stub lies and so its sign
  4. read the existing load effects (GET .../load-effects)
  5. POST a brand-new load effect carrying memberLoadings with section loads
     (n/vy/vz/mx/my/mz) for every active member at its position
  6. PUT to update one existing load effect (rename + change its forces)
  7. (optional) set the connection's load settings (loadsInEquilibrium,
     loadsInPercentage) and run the Load Extremes (LEX) reduction
  8. calculate and print a per-connection pass/fail summary

Field names used here come only from the documented LoadEffect / Member /
Calculation DTOs (see reference/io-shapes.md). Where the service enriches a
response with fields that are out of scope for this example, that is noted in
comments rather than read.

Prereqs:
  - The Connection REST API service running locally (default http://localhost:5000).
    Verify it is up:  GET http://localhost:5000/swagger/5.0/swagger.json
  - A valid IDEA StatiCa license installed on the machine (needed to calculate).
  - The .ideaCon project must already contain at least one connection with members.
  - pip install requests

Run:
  python load_effects.py path/to/model.ideaCon
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

    # --- Members -----------------------------------------------------------

    def get_members(self, project_id: str, connection_id: int) -> list:
        # GET .../members returns array<ConMember>. The server populates each
        # item's `position` and `model` (and `stiffnessAnalysis` only for
        # stiffness analysis). We only read documented ConMember fields below.
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/members"
        )
        resp.raise_for_status()
        return resp.json()  # [ ConMember { id, name, isContinuous, connectedBy, ... } ]

    # --- Load effects ------------------------------------------------------

    def get_load_effects(self, project_id: str, connection_id: int) -> list:
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/load-effects",
            params={"isPercentage": "false"},  # absolute N / N·m
        )
        resp.raise_for_status()
        return resp.json()  # [ ConLoadEffect { id, name, active, isPercentage, memberLoadings[] } ]

    def add_load_effect(self, project_id: str, connection_id: int, load_effect: dict) -> dict:
        # POST body is a ConLoadEffect. `id` is ignored (server assigns the next
        # id); `active` is honoured, so send it explicitly.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/load-effects",
            json=load_effect,
        )
        resp.raise_for_status()
        return resp.json()  # ConLoadEffect (with server-assigned id)

    def update_load_effect(self, project_id: str, connection_id: int, load_effect: dict) -> dict:
        # PUT body is a ConLoadEffect; its `id` selects which load effect to update.
        # name, active and member loadings are applied; the body is echoed back on 200.
        # An omitted `active` is true, so a PUT without it re-activates the load
        # effect: send the target's own `active` unless you mean to change it.
        resp = self.session.put(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/load-effects",
            json=load_effect,
        )
        resp.raise_for_status()
        return resp.json()  # ConLoadEffect (echoed)

    def set_load_settings(self, project_id: str, connection_id: int, settings: dict) -> dict:
        # Body is a ConLoadSettings { loadsInEquilibrium, loadsInPercentage }.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}"
            f"/load-effects/set-load-settings",
            json=settings,
        )
        resp.raise_for_status()
        return resp.json()  # ConLoadSettings (echoed)

    def calculate_load_extremes(self, project_id: str, connection_id: int) -> list:
        # Runs the Load Extremes (LEX) reduction. No request body. Returns all
        # load effects of the connection with updated `active` flags.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}"
            f"/load-effects/calculate-load-extremes"
        )
        resp.raise_for_status()
        return resp.json()  # [ ConLoadEffect ]

    # --- Calculation -------------------------------------------------------

    def calculate(self, project_id: str, connection_ids: list[int]) -> list:
        # Body is a JSON array of ints, e.g. [1] or [1, 2, 3].
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/calculate",
            json=connection_ids,
        )
        resp.raise_for_status()
        return resp.json()  # [ ConResultSummary { id, passed, resultSummary[] } ]

    def close(self, project_id: str) -> None:
        # Frees the project from the service's memory. Always do this.
        resp = self.session.get(f"{self.base}/projects/{project_id}/close")
        resp.raise_for_status()


def build_member_loadings(members: list[dict], known_slots: dict | None = None) -> list[dict]:
    """Build a ConLoadEffectMemberLoad[] — one section load per active member.

    A member with "active": false is skipped: one loading on an inactive member
    makes the service refuse the whole POST with 422 "ConLoadEffectMemberLoad is
    defined for member 'N' that is not active".

    For each member we use:
      - memberId   <- ConMember.id
      - position   <- read from an existing load effect when there is one
        (known_slots): the first load effect that loads a member fixes the end
        it accepts (reference/io-shapes.md, LoadEffect). A member no load effect
        has loaded yet accepts either end, so the fallback below is free. A wrong
        end is refused with 422
        "Defined member loading Member:N, Position:X is not defined in
        connection M". NOTE a loading is a vector in the member LCS at a
        stub's free end, and its sign follows the stub's side of the node: a
        positive N is tension in a stub on +x (an ended connectedBy "begin"
        member, or a continuous member's "End" loading) and compression on -x
        (an ended "end" member, or a continuous member's "Begin" loading). An
        ended member's loading acts the same under either position label.
        NOTE: ConLoadEffectPositionEnum wire values are PascalCase
        ("Begin"/"End"), unlike ConMember.connectedBy's lowercase — don't mix
        the two up (input binding is in fact case-insensitive, but emit
        PascalCase). Members omitted from memberLoadings are NOT an error; GET
        the load effect back to see the rows it stored. Send all six sectionLoad
        components, spelled exactly. See reference/io-shapes.md § LoadEffect.
      - sectionLoad components n/vy/vz/mx/my/mz (ConLoadEffectSectionLoad).
    """
    loadings = []
    for m in members:
        if not m.get("active", True):
            continue  # an inactive member cannot carry a loading (422)
        member_id = m["id"]
        if known_slots and member_id in known_slots:
            position = known_slots[member_id]
        elif m.get("isContinuous"):
            position = "Begin"
        else:
            # Free choice for a member no load effect has loaded yet.
            position = "End"
        loadings.append(
            {
                "memberId": member_id,
                "position": position,
                "sectionLoad": {
                    "n": 100000.0,  # N, axial (positive = tension in a stub on +x of the node)
                    "vy": 0.0,      # N, shear in local Y
                    "vz": 50000.0,  # N, shear in local Z
                    "mx": 0.0,      # N·m, torsion
                    "my": 25000.0,  # N·m, bending about local Y
                    "mz": 0.0,      # N·m, bending about local Z
                },
            }
        )
    return loadings


def print_summary(summaries: list[dict]) -> None:
    for s in summaries:
        status = "PASS" if s.get("passed") else "FAIL"
        print(f"  Connection {s['id']}: {status}")
        for chk in s.get("resultSummary") or []:
            if chk.get("skipped"):
                continue
            # checkValue is not a uniform 0..1 ratio; use the preformatted message.
            ok = "ok" if chk.get("checkStatus") else "NOT OK"
            msg = chk.get("unityCheckMessage") or f"checkValue={chk.get('checkValue')}"
            print(f"    - {chk.get('name')}: {msg} [{ok}]")


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

    connection_id = connections[0]["id"]
    print(f"Using connection {connection_id} ({connections[0].get('name')})")

    try:
        # 1) Learn the member ids / positions that load effects must reference.
        members = api.get_members(project_id, connection_id)
        if not members:
            print("Connection has no members; cannot define load effects.")
            return
        print(f"Members: {[(m['id'], m.get('name')) for m in members]}")

        # 2) Read existing load effects (so we have an id to PUT later) — and, more
        #    importantly, learn which (memberId, position) slots this connection
        #    actually registers. That is not derivable from connectedBy; see
        #    build_member_loadings(). A model imported with results has at least one LE.
        existing = api.get_load_effects(project_id, connection_id)
        print(f"Existing load effects: {[(le['id'], le.get('name')) for le in existing]}")
        known_slots = {}
        if existing:
            known_slots = {ld["memberId"]: ld["position"]
                           for ld in (existing[0].get("memberLoadings") or [])
                           if ld.get("memberId") is not None and ld.get("position")}
            if known_slots:
                print(f"  slots in use: {known_slots}")

        # 3) POST a new load effect with per-member section loads.
        member_loadings = build_member_loadings(members, known_slots)
        new_le = {
            "name": "API LE1",
            "active": True,        # honoured; send it explicitly
            "isPercentage": False,  # always: absolute N / N·m values
            "memberLoadings": member_loadings,
        }
        created = api.add_load_effect(project_id, connection_id, new_le)
        created_id = created["id"]
        print(f"Created load effect id={created_id} name={created.get('name')}")

        # 4) PUT to update one existing load effect (rename + change forces).
        #    Prefer a pre-existing one; otherwise update the one we just created.
        #
        #    PUT can only UPDATE member/position slots the load effect already has —
        #    it cannot add one. A slot that isn't there is 422:
        #      "Updating loading : MemberId:1 - Position:Begin was not found in internal
        #       forces of Load effect 1 ... Available forces BeamId:2, IsBegin:False"
        #    (and a member with no internal forces in the model, e.g. the bearing member
        #    of a simple joint, has no slot at all). So take the slots from the target
        #    itself and rewrite their magnitudes; use POST to introduce a new set.
        target = existing[0] if existing else created
        target_id = target["id"]
        updated_body = {
            "id": target_id,            # selects which load effect to update
            "name": "API LE1 updated",
            "active": target["active"],  # keep the flag: omitted, it would be true
            "isPercentage": False,
            "memberLoadings": [
                {
                    "memberId": ml["memberId"],
                    "position": ml["position"],
                    "sectionLoad": {
                        "n": 100000.0,
                        "vy": 0.0,
                        "vz": 50000.0,
                        "mx": 0.0,
                        "my": 25000.0,
                        "mz": 0.0,
                    },
                }
                for ml in target.get("memberLoadings", [])
            ],
        }
        updated = api.update_load_effect(project_id, connection_id, updated_body)
        print(f"Updated load effect id={updated['id']} name={updated.get('name')}")

        # 5) (Optional) Set load settings, then run the Load Extremes reduction.
        settings = api.set_load_settings(
            project_id,
            connection_id,
            {"loadsInEquilibrium": False, "loadsInPercentage": False},
        )
        print(
            "Load settings: "
            f"equilibrium={settings.get('loadsInEquilibrium')} "
            f"percentage={settings.get('loadsInPercentage')}"
        )

        lex = api.calculate_load_extremes(project_id, connection_id)
        active_after = [(le["id"], le.get("name")) for le in lex if le.get("active")]
        print(f"Load extremes -> active load effects: {active_after}")

        # 6) Calculate the connection and print pass/fail.
        print("Calculating...")
        summaries = api.calculate(project_id, [connection_id])
        print_summary(summaries)
    finally:
        api.close(project_id)  # release service memory even on error
        print("Project closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_effects.py path/to/model.ideaCon")
        sys.exit(1)
    main(sys.argv[1])
