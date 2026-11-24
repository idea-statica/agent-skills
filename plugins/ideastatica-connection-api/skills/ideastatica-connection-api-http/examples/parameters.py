"""
Read and update connection parameters (parametric design) using the
IDEA StatiCa Connection REST API (Connection Rest API 5.0) via raw HTTP
with the `requests` library.

What this example does:
  1. Connects to the service and opens an .ideaCon project.
  2. GET .../parameters?includeHidden=true and prints each IdeaParameter
     (key, expression, value, unit, validationStatus).
     When the model has a plate operation, creates `demo_p`, links it to that plate's
     thickness, reads the thickness back from IOM, updates it and unlinks it.
  3. PUT .../parameters with an array of IdeaParameterUpdate to change one
     parameter's expression (targeted by its Key) and reads the
     ParameterUpdateResponse (setToModel, resulting parameters, failedValidations).
  4. POST .../evaluate-expression with a string body (e.g. "2 * Width + 5")
     and prints the evaluated result.
  5. Recalculates the connection so the parameter change takes effect.

Prereqs:
  - The Connection REST API service running locally (default http://localhost:5000).
    Verify it is up:  GET http://localhost:5000/swagger/5.0/swagger.json
  - A valid IDEA StatiCa license installed on the machine (needed to calculate).
  - Any .ideaCon model. With a plate operation the example also creates and links its own
    parameter (`demo_p`); with no parameter at all it stops after reading them.
  - pip install requests

Run:
  python parameters.py path/to/model.ideaCon
  # optionally pass an expression to evaluate as the 2nd argument:
  python parameters.py path/to/model.ideaCon "2 * Width + 5"
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

    def get_parameters(self, project_id: str, connection_id: int,
                       include_hidden: bool = True) -> list:
        # GET .../parameters -> array<IdeaParameter>.
        # includeHidden=false returns only parameters with isVisible true;
        # true includes hidden ones too.
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/parameters",
            params={"includeHidden": str(include_hidden).lower()},
        )
        resp.raise_for_status()
        return resp.json()  # [ IdeaParameter { key, expression, value, unit, ... } ]

    def update_parameters(self, project_id: str, connection_id: int,
                          updates: list[dict]) -> dict:
        # PUT .../parameters; body is an array<IdeaParameterUpdate>.
        # Each update targets an existing parameter by `key`. If any key does
        # not match an existing parameter, the whole call fails (HTTP 422).
        resp = self.session.put(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/parameters",
            json=updates,
        )
        resp.raise_for_status()
        return resp.json()  # ParameterUpdateResponse { setToModel, parameters[], failedValidations[] }

    def create_parameter(self, project_id: str, connection_id: int, key: str,
                         parameter_type: str, expression: str, **extra) -> dict:
        # POST .../parameters. The expression is EVALUATED before the parameter is
        # stored, so a bad one is refused here (422) - unlike a PUT, which stores it
        # and answers 200 - and a dependent parameter must be created driver-first.
        # A String expression needs quotes: "'S 355'", not "S 355".
        body = {"key": key, "parameterType": parameter_type, "expression": expression, **extra}
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/parameters",
            json=body,
        )
        resp.raise_for_status()
        return resp.json()  # IdeaParameter, already evaluated: value + validationStatus

    def linkable_properties(self, project_id: str, connection_id: int,
                            owner_kind: str = None, owner_id: int = None) -> list:
        # Never guess a propertyId - ask the owner. Without an owner you get every
        # drivable property in the connection, each row carrying its own `owner`.
        # A nonexistent owner id is 404 here (but 422 on POST .../links).
        base = f"{self.base}/projects/{project_id}/connections/{connection_id}"
        url = (f"{base}/parameters/linkable-properties" if owner_kind is None
               else f"{base}/{owner_kind}s/{owner_id}/linkable-properties")
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()  # [ { propertyId, name, group, valueType, currentValue? } ]

    def link_parameter(self, project_id: str, connection_id: int, key: str,
                       owner_kind: str, owner_id: int, property_id: str) -> dict:
        # POST .../parameters/links - applies the value at once, no separate call.
        # owner_kind is "operation" or "member"; the id field is named accordingly.
        body = {"parameter": key, "kind": owner_kind,
                f"{owner_kind}Id": owner_id, "propertyId": property_id}
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/parameters/links",
            json=body,
        )
        resp.raise_for_status()
        return resp.json()  # { id, parameter, owner, propertyId }

    def get_links(self, project_id: str, connection_id: int) -> list:
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/parameters/links")
        resp.raise_for_status()
        return resp.json()

    def unlink(self, project_id: str, connection_id: int, link_id: int) -> None:
        # 204. The last applied value stays in the model - unlinking does not undo it.
        resp = self.session.delete(
            f"{self.base}/projects/{project_id}/connections/{connection_id}"
            f"/parameters/links/{link_id}")
        resp.raise_for_status()

    def export_iom(self, project_id: str, connection_id: int) -> dict:
        # The oracle for "did the value actually apply". A 200 on a link means the value
        # type fits the property, not that the model changed, so read the model back.
        resp = self.session.get(
            f"{self.base}/projects/{project_id}/connections/{connection_id}"
            f"/export-iom-connection-data")
        resp.raise_for_status()
        return resp.json()

    def evaluate_expression(self, project_id: str, connection_id: int,
                            expression: str) -> str:
        # POST .../evaluate-expression; body is a single JSON string.
        # Response is a single JSON string: the evaluated result rendered to text.
        resp = self.session.post(
            f"{self.base}/projects/{project_id}/connections/{connection_id}/evaluate-expression",
            json=expression,
        )
        resp.raise_for_status()
        return resp.json()  # plain string, not an object

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


def print_parameters(params: list) -> None:
    """Print the documented IdeaParameter fields for each parameter."""
    if not params:
        print("  (no parameters defined for this connection)")
        return
    for p in params:
        # All fields below are documented for IdeaParameter in io-shapes.md.
        # (IdeaParameter also exposes default/parameterType/description/isVisible/
        #  lowerBound/upperBound/parameterValidation; out of scope here.)
        print(
            f"  key={p.get('key')!r} "
            f"expression={p.get('expression')!r} "
            f"value={p.get('value')!r} "
            f"unit={p.get('unit')!r} "
            f"validationStatus={p.get('validationStatus')!r}"
        )


def main(idea_con_path: str, expression: str = "2 * Width + 5") -> None:
    api = ConnectionApi()

    client_id = api.connect()
    print(f"Connected. ClientId = {client_id}")

    project = api.open_project(idea_con_path)
    project_id = project["projectId"]
    print(f"Opened project {project_id}")

    # Once the project is open, everything is wrapped in try/finally so the
    # project is always released from the service even if a later call fails.
    try:
        connections = api.get_connections(project_id)
        if not connections:
            print("No connections in project.")
            return

        connection_id = connections[0]["id"]
        print(f"Using connection {connection_id} ({connections[0].get('name')})")

        # 1) Read all parameters (including hidden ones).
        params = api.get_parameters(project_id, connection_id, include_hidden=True)
        print(f"\nParameters ({len(params)}):")
        print_parameters(params)

        # 1b) Create a parameter and link it to a property, so this runs against a
        #     model that defines no parameters at all. This is the flow that turns a
        #     connection built by a script into a reusable parametric model.
        catalog = api.linkable_properties(project_id, connection_id)
        # Match the target on the property name, not on the first Float in catalog
        # order - that one may be unrelated (e.g. a cut's Offset) and the read-back
        # would then show no change. Read back the quantity that name refers to.
        target_prop = next((p for p in catalog
                            if p.get("name") == "Thickness"
                            and p.get("valueType") == "Float"
                            and (p.get("owner") or {}).get("kind") == "operation"
                            and p.get("group", "").endswith("plate")), None)
        if target_prop:
            owner = target_prop["owner"]
            demo_key = "demo_p"
            try:
                created = api.create_parameter(project_id, connection_id, demo_key,
                                               "Float", "0.02", description="created by the example")
                print(f"\nCreated {demo_key!r}: value={created['value']} "
                      f"status={created['validationStatus']}")
                link = api.link_parameter(project_id, connection_id, demo_key,
                                          "operation", owner["operationId"],
                                          target_prop["propertyId"])
                print(f"  linked to {target_prop['name']!r} "
                      f"(operation {owner['operationId']}, propertyId {target_prop['propertyId']}) "
                      f"as link {link['id']}")
                # VERIFY BY READING THE MODEL BACK. A 200 on the link says the value type
                # fits, not that it applied; the status code is not evidence.
                thick = lambda: [(p.get("name"), p.get("thickness"))
                                 for p in (api.export_iom(project_id, connection_id).get("plates") or [])]
                print(f"  IOM plate thickness after linking 0.02: {thick()}")
                api.update_parameters(project_id, connection_id,
                                      [{"key": demo_key, "expression": "0.03"}])
                print(f"  after PUT 0.03:                          {thick()}")
                print("  ^ unchanged here would mean the value did not apply, whatever the status said")
                api.unlink(project_id, connection_id, link["id"])
                print(f"  unlinked; the last applied value stays:  {thick()}")
            except requests.HTTPError as e:
                # A 422 here names what it refused - print it rather than swallowing it.
                print(f"  create/link refused: {e.response.status_code} {e.response.text[:200]}")
            params = api.get_parameters(project_id, connection_id, include_hidden=True)

        if not params:
            print("\nNo parameters to update; nothing else to demonstrate.")
            return

        # 2) Update one parameter's expression by its Key.
        #    We bump the first parameter's expression by appending "+ 0" so the
        #    example runs against any model without guessing valid numeric ranges.
        target = params[0]
        target_key = target["key"]
        old_expr = target.get("expression")
        new_expr = f"({old_expr}) + 0" if old_expr else "0"

        updates = [
            {
                "key": target_key,
                "expression": new_expr,
            }
        ]
        print(f"\nUpdating parameter {target_key!r}: {old_expr!r} -> {new_expr!r}")
        result = api.update_parameters(project_id, connection_id, updates)

        # ParameterUpdateResponse: setToModel, parameters[], failedValidations[]
        print(f"  setToModel = {result.get('setToModel')}")
        failed = result.get("failedValidations") or []
        if failed:
            print("  failedValidations:")
            for fv in failed:
                # IdeaParameterValidationResponse: key, message, validationStatus
                print(
                    f"    key={fv.get('key')!r} "
                    f"validationStatus={fv.get('validationStatus')!r} "
                    f"message={fv.get('message')!r}"
                )
        # A PUT stores an expression it cannot evaluate and still answers 200; that
        # shows only on the parameter's own validationStatus, not in failedValidations.
        for p in result.get("parameters") or []:
            if p.get("validationStatus") not in (None, "Ok"):
                msg = (p.get("parameterValidation") or {}).get("message")
                print(f"  WARNING key={p.get('key')!r} "
                      f"validationStatus={p.get('validationStatus')!r} message={msg!r}")
        print("  Resulting parameters:")
        print_parameters(result.get("parameters") or [])

        # 3) Evaluate a free-form expression against the connection's parameters.
        #    Note: this uses parameter names (e.g. Width) that must exist in the
        #    model. Pass a model-appropriate expression as the 2nd CLI argument.
        # A self-contained expression always works; one naming a parameter needs that
        # parameter to exist first - see below.
        print("\nEvaluating '1+1' (self-contained)")
        print(f"  result = {api.evaluate_expression(project_id, connection_id, '1+1')!r}")

        print(f"\nEvaluating {expression!r}")
        try:
            evaluated = api.evaluate_expression(project_id, connection_id, expression)
            print(f"  result = {evaluated!r}")
        except requests.HTTPError as exc:
            # A 500 here means the expression could not be evaluated - an undefined name,
            # a typo or a bad arity alike, with no diagnosis. POST .../parameters refuses
            # the same expression with a 422 that names the fault.
            print(f"  evaluate-expression failed: {exc.response.status_code} "
                  f"- expected if {expression!r} names a parameter this model does not define")

        # 4) Recalculate so the parameter change is reflected in the results.
        print("\nRecalculating...")
        summaries = api.calculate(project_id, [connection_id])
        for s in summaries:
            status = "PASS" if s.get("passed") else "FAIL"
            print(f"  Connection {s['id']}: {status}")
    finally:
        api.close(project_id)  # release service memory even on error
        print("\nProject closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parameters.py path/to/model.ideaCon [expression]")
        sys.exit(1)
    expr = sys.argv[2] if len(sys.argv) > 2 else "2 * Width + 5"
    main(sys.argv[1], expr)
