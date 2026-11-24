"""
Build one connection that uses all 13 typed operation kinds, calculate it and save it.

The joint is a column base with a beam framing into the column above it:

    COL   HEB300, vertical, starting at the node (z = 0) - the bearing member
    BEAM  IPE300 along +X, raised to z = BEAM_Z, bolted to the column's +X flange

and the operations, in model order (an operation can only reference an earlier one):

    stiffening-plate   BP       base plate, mid-plane at the node
    cut                CUT-COL  column cut by the base plate and welded to it
    negative-member    VENT     CHS volume through the base plate ...
    plate-cut          PC-VENT  ... punched out of it: a grout / vent hole
    contact-grid       CONTACT  base plate bearing on a NEW concrete block
    anchor-grid        ANCHORS  4 anchors into that EXISTING block
    stiffening-plate   EP       end plate on the beam
    work-plane         WP-EP    plane on the outer face of the end plate ...
    cut                CUT-BEAM ... trimming the beam there
    weld               W-*      beam flanges and web welded onto the end plate face
    bolt-grid          BOLTS    8 x M20 through end plate and column flange
    negative-plate     OPENING  circular volume in the beam web ...
    cut                CUT-OPEN ... cut out of it: a web opening
    stiffening-plate   RIB-*    two column stiffeners at the beam's bottom flange ...
    contact            C-RIB-*  ... bearing on the column web (contact, not weld)
    stiffening-plate   DBL      web doublers on both sides of the column web ...
    pin-grid           PIN      ... with a pin through doubler / web / doubler
    stiffening-member  STUB     IPE160 bracket at the -X flange ...
    cut                CUT-STUB ... cut to the flange face and welded there

Rules demonstrated (reference/operations.md):
  - POST/PUT .../operations/{kind} answer {operation, issues, addedWithoutIssues} with
    HTTP 200 for an operation the engine cannot build - read the wrapper every time. Such an
    operation is still stored; there is no per-operation DELETE.
  - PUT .../operations/{kind} replaces the operation whose id is in the body. Send it to the
    route of that operation's own kind, built from its typed GET.
  - Which member wall faces where, and which face a stiffener landed on, is read back from
    the IOM export at runtime, not assumed.
  - SI units: metres, radians, newtons. "active": true is sent on every operation.
  - Catalog ids (cross-sections, materials, assemblies) come from live responses only.

The saved typed_ops_demo.ideaCon can be passed as the model argument to the other examples.

Prereqs: the service running locally, a valid IDEA StatiCa licence, pip install requests.
Run:     python typed_operations.py
"""

import math
import sys

import requests

BASE = "http://localhost:5000/api/5"

# Geometry (metres). HEB300: h = b = 0.300, tw = 0.011, tf = 0.019. IPE300: h = 0.300.
COL_H, COL_TW, COL_TF = 0.300, 0.011, 0.019
BEAM_Z = 0.60            # beam axis height above the node (member eccentricity)
BP_T = 0.030             # base plate thickness
EP_T = 0.020             # end plate thickness
RIB_T = 0.012            # column stiffener thickness
BEAM_BOTTOM_FLANGE_Z = BEAM_Z - 0.300 / 2 + 0.0107 / 2   # mid-surface of the beam's bottom flange


def vec(x=0.0, y=0.0, z=0.0):
    return {"x": x, "y": y, "z": z}


def weld(weld_type, size):
    return {"kind": "continuous", "type": weld_type, "size": size}


def dot(a, b):
    return a["x"] * b["x"] + a["y"] * b["y"] + a["z"] * b["z"]


class Session:
    """ClientId header, base URL and the operation wrapper check."""

    def __init__(self):
        self.s = requests.Session()
        client_id = self.s.get(f"{BASE}/clients/connect-client").text.strip().strip('"')
        self.s.headers.update({"ClientId": client_id, "Accept": "application/json"})
        self.ops = None   # .../connections/{id}/operations, set once the connection is known

    def get(self, url):
        r = self.s.get(url)
        r.raise_for_status()
        return r.json()

    def post(self, url, body):
        r = self.s.post(url, json=body)
        r.raise_for_status()
        return r.json()

    def write_op(self, method, kind, body):
        """POST or PUT one typed operation, check the wrapper, return the operation id."""
        r = self.s.request(method, f"{self.ops}/{kind}", json={"active": True, **body})
        payload = r.json()
        if r.status_code != 200:
            raise RuntimeError(f"{method} {kind} {body.get('name')}: HTTP {r.status_code} "
                               f"{payload.get('detail') or payload.get('errors')}")
        if not payload.get("addedWithoutIssues"):
            issues = "; ".join(f"[{i.get('severity')}] {i.get('details') or i.get('description')}"
                               for i in payload.get("issues") or [])
            # The operation IS stored as sent; fix it with a PUT before going on.
            raise RuntimeError(f"{method} {kind} {body.get('name')} stored WITH ISSUES: {issues}")
        op_id = payload["operation"]["id"]
        print(f"  {method:<4} {kind:<18} {body.get('name'):<10} id={op_id}")
        return op_id


def catalog_id(api, project, kind, name):
    """Add a catalog entry by its library name and return its id.

    A material POST answers the id of the OLDEST entry of that name, so the id of the entry
    just added is taken from the list. (A cross-section POST answers its new entry directly.)
    """
    api.post(f"{project}/materials/{kind}", {"mprlName": name})
    return max(e["id"] for e in api.get(f"{project}/materials/{kind}") if e["name"] == name)


def walls(api, conn, member_name):
    """The member's walls from IOM, in plateSubIndex order (0-based), with their frames."""
    iom = api.get(f"{conn}/export-iom-connection-data")
    beam = next(b for b in iom["beams"] if b["name"] == member_name)
    return beam["plates"]


def build(api, project, conn):
    css_col = api.post(f"{project}/materials/cross-sections", {"mprlName": "HEB300", "materialName": "S 355"})["id"]
    css_beam = api.post(f"{project}/materials/cross-sections", {"mprlName": "IPE300", "materialName": "S 355"})["id"]
    css_stub = api.post(f"{project}/materials/cross-sections", {"mprlName": "IPE160", "materialName": "S 355"})["id"]
    css_vent = api.post(f"{project}/materials/cross-sections", {"mprlName": "CHS60.3/5.0", "materialName": "S 355"})["id"]
    concrete = catalog_id(api, project, "concrete", "C25/30")
    bolt_m20 = catalog_id(api, project, "bolt-assemblies", "M20 8.8")
    anchor_m24 = catalog_id(api, project, "bolt-assemblies", "M24 8.8")
    pin_d20 = api.post(f"{project}/materials/pin", {"mprlName": "D20"})["id"]

    # ---- members: the first one added is the bearing member ---------------------------
    def member(name, css, gama_pitch, offset_ez):
        return api.post(f"{conn}/members", {
            "name": name, "crossSectionId": css, "isContinuous": False, "connectedBy": "begin",
            # send the WHOLE position block: fields left out are written as zeros
            "position": {"definedBy": "rotationsOfX", "betaDirection": 0.0, "gamaPitch": gama_pitch,
                         "alphaRotation": 0.0, "offsetEx": 0.0, "offsetEy": 0.0, "offsetEz": offset_ez},
        })["id"]

    col = member("COL", css_col, math.pi / 2, 0.0)    # local x = global +Z, starts at the node
    beam = member("BEAM", css_beam, 0.0, BEAM_Z)      # along +X, raised to z = BEAM_Z

    # Which column wall faces the beam is read from IOM, not assumed: the flanges are the walls
    # whose normal (axisZ) runs along global X, the web the one whose normal runs along Y.
    col_walls = walls(api, conn, "COL")
    flanges = [i for i, w in enumerate(col_walls) if abs(dot(w["axisZ"], vec(1.0))) > 0.99]
    front = max(flanges, key=lambda i: col_walls[i]["origin"]["x"])    # +X flange, facing the beam
    web = next(i for i, w in enumerate(col_walls) if abs(dot(w["axisZ"], vec(y=1.0))) > 0.99)
    beam_walls = walls(api, conn, "BEAM")
    beam_flanges = sorted((i for i, w in enumerate(beam_walls) if abs(dot(w["axisZ"], vec(z=1.0))) > 0.99),
                          key=lambda i: beam_walls[i]["origin"]["z"])    # bottom, top
    beam_web = next(i for i, w in enumerate(beam_walls) if abs(dot(w["axisZ"], vec(y=1.0))) > 0.99)
    print(f"  COL walls: front flange {front}, web {web} | BEAM walls: flanges {beam_flanges}, web {beam_web}")
    op = api.write_op

    # ---- column base ------------------------------------------------------------------
    # Base plate transverse to the column (memberLcs), mid-plane AT the node and width = width2
    # to centre it. The column end reaches into the plate, which is what lets the cut weld it:
    # placed flush under the column end, the same cut builds no weld at all.
    bp = op("POST", "stiffening-plate", {
        "name": "BP", "plateType": "structural", "shape": "rectangular", "thickness": BP_T,
        "width": 0.25, "width2": 0.25, "height": 0.25, "height2": 0.25,
        "positioning": {"conPlatePositioningType": "memberLcs", "onMemberId": col,
                        "offset": vec(), "rotation": vec()}})
    op("POST", "cut", {
        "name": "CUT-COL",
        "member": {"kind": "member", "memberId": col},
        "cutBy": {"kind": "plateOfOperation", "operationId": bp, "plateSubIndex": 1},
        "cuttingMethod": "surface", "direction": "perpendicular",
        "websWeld": weld("doubleFillet", 0.006), "flangesWeld": weld("doubleFillet", 0.008)})

    # Grout / vent hole: a negative CHS volume through the plate, then a plate-cut by it.
    vent = op("POST", "negative-member", {
        "name": "VENT", "crossSectionId": css_vent, "length1": 0.1, "length2": 0.1,
        "positioning": {"positioningType": "joint", "placementDefinition": "rotationsOfX",
                        "insertPoint": vec(0.0, 0.20, 0.0), "angleAlpha": 0.0, "angleBeta": math.pi / 2,
                        "rotationRx": 0.0}})
    op("POST", "plate-cut", {
        "name": "PC-VENT",
        "modifiedObject": {"kind": "plateOfOperation", "operationId": bp, "plateSubIndex": 1},
        "cutBy": {"kind": "negativeVolumeMember", "operationId": vent},
        "cuttingMethod": "surface"})

    # The base plate bears on a new concrete block below it (plateSide lowerSide); the anchors
    # then go into that same block. The block kind and the reference to an existing block sit
    # inside foundationBlock.
    contact_grid = op("POST", "contact-grid", {
        "name": "CONTACT",
        "connectedItems": [{"operationId": bp, "plateSubIndex": 1}],
        "plateSide": "lowerSide",
        "foundationBlock": {"blockType": "new", "concreteMaterialId": concrete, "height": 0.6,
                            "offsetTop": 0.2, "offsetBottom": 0.2, "offsetLeft": 0.2, "offsetRight": 0.2,
                            "shearForceTransfer": "friction", "contactType": "direct"}})
    a = 0.19   # anchors outside the 300 x 300 column footprint
    op("POST", "anchor-grid", {
        "name": "ANCHORS", "anchorType": "threadedRod", "anchorAssemblyId": anchor_m24,
        "embedmentDepth": 0.30,
        "connectedItems": [{"operationId": bp, "plateSubIndex": 1}],
        "definedBy": "plate", "isExploded": True,
        "geometry": {"type": "orthogonal",
                     "userPositions": [{"x": x, "y": y} for x in (-a, a) for y in (-a, a)]},
        "plateSide": "lowerSide",
        "foundationBlock": {"blockType": "existing", "existingBlockOperationId": contact_grid}})

    # ---- beam to column: bolted end plate ---------------------------------------------
    # End plate transverse to the beam, its mid-plane EP_T/2 outside the column flange face.
    # On a transverse memberLcs plate the WIDTH pair runs along the section depth.
    ep = op("POST", "stiffening-plate", {
        "name": "EP", "plateType": "structural", "shape": "rectangular", "thickness": EP_T,
        "width": 0.22, "width2": 0.22, "height": 0.10, "height2": 0.10,
        "positioning": {"conPlatePositioningType": "memberLcs", "onMemberId": beam,
                        "offset": vec(COL_H / 2 + EP_T / 2), "rotation": vec()}})

    # Trim the beam at the end plate's outer face with a plane in the beam's own LCS.
    wp = op("POST", "work-plane", {
        "name": "WP-EP", "method": "byNormalVector", "relatedTo": "member", "memberId": beam,
        "origin": vec(COL_H / 2 + EP_T), "normalVector": vec(1.0)})
    op("POST", "cut", {
        "name": "CUT-BEAM",
        "member": {"kind": "member", "memberId": beam},
        "cutBy": {"kind": "workPlane", "operationId": wp},
        "cuttingMethod": "surface", "direction": "perpendicular"})

    # Each beam wall's end edge welded onto the end plate FACE (edgeToSurface, wall first).
    # The top flange takes a CJP: a cjp is not rated by stress utilisation, so its
    # raw-results check fields come back as the string 'NaN' with checkStatus true.
    for name, wall, wtype, size in (("W-BF", beam_flanges[0], "doubleFillet", 0.008),
                                    ("W-TF", beam_flanges[1], "cjp", 0.0),
                                    ("W-WEB", beam_web, "doubleFillet", 0.005)):
        op("POST", "weld", {
            "name": name, "placement": "edgeToSurface",
            "firstMemberOrPlate": {"memberId": beam, "plateSubIndex": wall},
            "firstPlateEdgeIndex": [1],
            "secondMemberOrPlate": {"operationId": ep, "plateSubIndex": 1},
            "secondPlateEdgeIndex": 1,
            "weld": weld(wtype, size)})

    # 8 x M20 through the end plate and the column flange it faces. The FIRST item (the end
    # plate) gives the grid its frame: local x along the beam depth, local y across it.
    # In a grid, a member's plateSubIndex counts only the member's walls PARALLEL to that first
    # plate, in wall order - here the two flanges, so the front flange is its place among them.
    positions = [{"x": x, "y": y} for x in (-0.18, -0.09, 0.09, 0.18) for y in (-0.05, 0.05)]
    op("POST", "bolt-grid", {
        "name": "BOLTS", "boltAssemblyId": bolt_m20, "boltShearForceTransfer": "tensionShearInteraction",
        "connectedItems": [{"operationId": ep, "plateSubIndex": 1},
                           {"memberId": col, "plateSubIndex": sorted(flanges).index(front)}],
        "definedBy": "plate", "isExploded": True,
        "geometry": {"type": "orthogonal", "userPositions": positions}})

    # Circular web opening: a negative plate in the web plane, then the beam cut by it.
    opening = op("POST", "negative-plate", {
        "name": "OPENING", "shape": "circle", "radius": 0.06, "thickness": 0.03,
        "positioning": {"conPlatePositioningType": "coordinateSystem",
                        "coordinateSystem": {"origin": vec(0.60, 0.0, BEAM_Z), "xAxis": vec(1.0),
                                             "yAxis": vec(z=1.0), "zAxis": vec(y=-1.0)}}})
    op("POST", "cut", {
        "name": "CUT-OPEN",
        "member": {"kind": "member", "memberId": beam},
        "cutBy": {"kind": "plateOfOperation", "operationId": opening, "plateSubIndex": 1},
        "cuttingMethod": "surface", "direction": "perpendicular"})

    # ---- column panel -----------------------------------------------------------------
    # Stiffeners opposite the beam's bottom flange, on the INNER face of the front flange,
    # each bearing on the web by a CONTACT. Which `location` lands on the inner face depends
    # on the member's frame, so the side is checked in IOM after the POST and corrected with
    # a PUT of the typed GET body. The rib runs from the web face (-tw/2, so the edge sits ON
    # the web surface, which the contact needs) to near the flange tip.
    flange_mid_x = col_walls[front]["origin"]["x"]
    half_web = COL_TW / 2
    for side, (w, w2) in (("A", (0.14, -half_web)), ("B", (-half_web, 0.14))):
        rib = op("POST", "stiffening-plate", {
            "name": f"RIB-{side}", "plateType": "structural", "shape": "rectangular", "thickness": RIB_T,
            "width": w, "width2": w2, "height": COL_H - 2 * COL_TF, "height2": 0.0,
            "weld": weld("doubleFillet", 0.006),
            "positioning": {"conPlatePositioningType": "member", "onMemberId": col,
                            "plateOnMemberIndex": front + 1,    # 1-based, unlike plateSubIndex
                            "function": "rib", "location": "rightSide",
                            "inputMethod": "byAngles", "positionX": BEAM_BOTTOM_FLANGE_Z}})
        placed = next(p for p in api.get(f"{conn}/export-iom-connection-data")["plates"]
                      if p["name"] == f"RIB-{side}")
        if placed["origin"]["x"] > flange_mid_x:    # landed on the outer face: flip the side
            body = api.get(f"{api.ops}/stiffening-plate/{rib}")
            body["positioning"]["location"] = "leftSide"
            op("PUT", "stiffening-plate", body)
        op("POST", "contact", {
            "name": f"C-RIB-{side}", "placement": "edgeToSurface",
            "firstMemberOrPlate": {"operationId": rib, "plateSubIndex": 1},
            "firstPlateEdgeIndex": [1],
            "secondMemberOrPlate": {"memberId": col, "plateSubIndex": web},
            "secondPlateEdgeIndex": 1})

    # Web doublers on both sides of the web (one operation, two plates), and a pin through
    # doubler / web / doubler - a pin needs at least three parallel plates. A plate lying flat
    # on a face takes a single-sided fillet. The web is the column's only wall parallel to the
    # doubler, so it is index 0 of the grid's candidate list.
    dbl = op("POST", "stiffening-plate", {
        "name": "DBL", "plateType": "structural", "shape": "rectangular", "thickness": 0.010,
        "width": 0.09, "width2": 0.09, "height": 0.09, "height2": 0.09,
        "weld": weld("filletFront", 0.005),
        "positioning": {"conPlatePositioningType": "member", "onMemberId": col,
                        "plateOnMemberIndex": web + 1, "function": "doubler", "location": "bothSides",
                        "inputMethod": "byAngles", "positionX": 0.25}})
    op("POST", "pin-grid", {
        "name": "PIN", "pinOriginalId": pin_d20,
        "connectedItems": [{"operationId": dbl, "plateSubIndex": 1},
                           {"memberId": col, "plateSubIndex": 0},
                           {"operationId": dbl, "plateSubIndex": 2}],
        "definedBy": "plate", "isExploded": True,
        "geometry": {"type": "orthogonal", "userPositions": [{"x": 0.0, "y": 0.0}]}})

    # ---- bracket ----------------------------------------------------------------------
    # A horizontal IPE160 cantilever pointing -X at beam level, placed at the joint (azimuth
    # pi) and starting inside the column; a cut by the column trims it to the -X flange face and
    # welds it there - a joint-positioned added member takes no weld of its own.
    stub = op("POST", "stiffening-member", {
        "name": "STUB", "crossSectionId": css_stub, "length1": 0.0, "length2": 0.35,
        "positioning": {"positioningType": "joint", "placementDefinition": "rotationsOfX",
                        "insertPoint": vec(-0.10, 0.0, BEAM_Z), "angleAlpha": math.pi, "angleBeta": 0.0,
                        "rotationRx": 0.0}})
    op("POST", "cut", {
        "name": "CUT-STUB",
        "member": {"kind": "stiffeningMember", "operationId": stub},
        "cutBy": {"kind": "member", "memberId": col},
        "cuttingMethod": "surface", "direction": "perpendicular",
        "websWeld": weld("doubleFillet", 0.004), "flangesWeld": weld("doubleFillet", 0.005)})

    # ---- edit one operation: GET -> change one field -> PUT ---------------------------
    # A PUT replaces the whole operation, so start from its typed GET, never from a body
    # written by hand, and send it to the route of the operation's own kind.
    cut_col = next(o for o in api.get(f"{api.ops}/cut") if o["name"] == "CUT-COL")
    cut_col["flangesWeld"]["size"] = 0.010
    op("PUT", "cut", cut_col)
    return beam


KINDS = ["weld", "cut", "plate-cut", "bolt-grid", "anchor-grid", "pin-grid", "contact", "contact-grid",
         "negative-member", "negative-plate", "stiffening-member", "stiffening-plate", "work-plane"]


def main() -> int:
    api = Session()
    project_id = api.post(f"{BASE}/projects", {"name": "all typed operation kinds", "countryCode": "ecen"})["projectId"]
    project = f"{BASE}/projects/{project_id}"
    try:
        # A new project already holds an empty CON1; build into it, so the saved file's first
        # connection is the modelled one (the other examples take connections[0]).
        conn_id = api.get(f"{project}/connections")[0]["id"]
        conn = f"{project}/connections/{conn_id}"
        api.ops = f"{conn}/operations"
        print(f"Project {project_id}, connection {conn_id}")

        beam = build(api, project, conn)

        # Count what was built: an operation can report success and build nothing.
        iom = api.get(f"{conn}/export-iom-connection-data")
        print("IOM: " + ", ".join(f"{k} {len(iom.get(k) or [])}" for k in
                                   ("plates", "beams", "welds", "boltGrids", "anchorGrids", "pinGrids", "concreteBlocks")))
        present = [k for k in KINDS if api.get(f"{api.ops}/{k}")]
        print(f"Typed list GETs with items: {len(present)} of {len(KINDS)} kinds")

        # Loads need not be in equilibrium: the bearing member (COL) and the concrete block
        # take the reactions. Set this BEFORE adding the load effect. N and N*m, never kN.
        api.post(f"{conn}/load-effects/set-load-settings", {"loadsInEquilibrium": False, "loadsInPercentage": False})
        api.post(f"{conn}/load-effects", {
            "name": "LE1", "active": True, "isPercentage": False,
            "memberLoadings": [{"memberId": beam, "position": "End",
                                "sectionLoad": {"n": 0.0, "vy": 0.0, "vz": -40000.0, "mx": 0.0, "my": 25000.0, "mz": 0.0}}]})
        summary = api.post(f"{conn}/calculate", None)      # single connection: one object back
        print(f"Calculate: passed={summary.get('passed')}")
        for row in summary.get("resultSummary") or []:
            if not row.get("skipped"):
                print(f"  {row.get('name'):<16} {row.get('unityCheckMessage')}")

        r = api.s.get(f"{project}/download")
        r.raise_for_status()
        with open("typed_ops_demo.ideaCon", "wb") as f:
            f.write(r.content)
        print("Saved typed_ops_demo.ideaCon")
        return 0
    finally:
        api.s.get(f"{project}/close")


if __name__ == "__main__":
    sys.exit(main())
