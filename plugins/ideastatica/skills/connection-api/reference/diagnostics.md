# Diagnostics — "something didn't work, where do I start?"

Entry point for debugging. Symptom → likely cause → how to confirm → where the detail
lives. This file does NOT restate semantics; it routes. The golden rule (SKILL.md rule 3)
governs everything here: **HTTP 200 and `addedWithoutIssues:true` do NOT mean geometry
exists — always verify materialization.**

## How to verify materialization (the four channels)

Pick the channel by what you're checking — they do NOT all show the same things:

| channel | endpoint | shows | blind to |
|---|---|---|---|
| **IOM data** | `GET …/export-iom-connection-data` (JSON by default, XML on `Accept: application/xml`) | plates with their outlines; COUNTS of welds (contacts among them), bolt/anchor grids, concrete blocks | work-planes; **a weld or contact is a bare `{"id": N}` — no type, size, material or parts**, so this channel counts them and cannot tell one from another |
| **IOM full** | `GET …/export-iom` (XML) | **the only channel carrying a weld's LINE**: `<WeldData>` with `<Start>`/`<End>` (world, m), `<WeldType>`, `<Thickness>`, `<IsIntermittent>`, `<ConnectedParts>` | — |
| **scene** | `GET …/presentations/text` (JSON) | solids/holes, blocks, **welds (meshed)**, and an identity on nearly every group | bolts (only holes); nothing NAMES a part — the scene carries ids, not names |
| **wrapper** | the POST/PUT response | `issues[]`, `addedWithoutIssues` | everything else — do not trust alone |

**To measure a weld's LENGTH, read `export-iom`, not connection-data.** connection-data lists
each weld as a bare `{"id": N}`, while `export-iom` gives every `<Start>`/`<End>`. A reader that
defaults a missing coordinate to `0` therefore reads EVERY weld as zero-length.
Note the element is `<WeldData>`, not `<Weld>`.

**One operation can produce SEVERAL welds.** A weld whose FIRST operand is a bare member
(`{memberId}` without `plateSubIndex`) welds every wall of that member: one `edgeToSurface` operation on an
I-section yields three `<WeldData>` entries sharing the operation's name (two flanges and a
web). Count `<WeldData>`, never operations.

A foundation block a grid creates (`blockType: "new"`) appears in IOM as a `ConcreteBlockData`
entry (and in the scene). A `contact` operation rides in the weld collection — there is no separate one — but
only **`export-iom`** identifies it: a `<WeldData>` with the operation name, its `WeldType` and
`ConnectedParts`. In `export-iom-connection-data` every weld entry is a bare `{"id": N}`, so
contacts count there but cannot be distinguished; the 3D scene does not name it either.
Detail: SKILL.md rule 4, `grids.md`.

**The scene DOES mesh welds** — one group per weld. For weld *names* or counts IOM is still the
channel; for geometry the scene has them.

**Every group carries `selected: {id, type:{kind}}`, which is what lets you join geometry to
results** — `member` · `plate` · `weld` · `boltGrid`. See `raw-results.md`
§"Joining results back to the geometry".

**IOM connection-data has NO beam solid and NO member reference line.** A `beam` is only
its `plates[]` (the cross-section walls, each a midsurface outline) — there is no 3D
member volume, no section-outline-with-length, no axis line. A wireframe of a member is
just its wall plates. `beam.cuts[]` (and top-level `cutBeamByBeams[]`) describe a cut as a
PLANE (`planePoint` + `normalVector` + `direction` + `offset`), not an outline — the walls
already come back trimmed in their `Geometry.outline`. For a graphic export (e.g. DXF/OBJ
for Rhino) draw: plate outlines (closed polylines), bolt HOLE AXES (segments on the first
connected item — see grids.md, positions are schematic), weld Start→End segments;
`foldedPlates`, `anchorGrids`, `pinGrids`, `concreteBlocks` are separate collections to
handle too. IFC is NOT a Rhino-native format; DXF/OBJ built from IOM are.

**Scene format** (for geometric checks): top-level `vertices` is a FLAT array
`[x,y,z, x,y,z, …]` (point i = `vertices[3i:3i+3]`); each `groups[]` has `faces` (point
indices) and `text[].value` = the element's NAME. Compute a group's centroid/bbox from
its face-referenced points.

**A group carries more than triangles**, and all of it is transportable — nothing has to be
derived or invented if you are drawing the scene rather than measuring it:

- `groups[].color` — the application's own RGBA 0-255: member `[150,190,240]`,
  plate `[50,75,140]`, weld and boltGrid `[255,210,0]`. Use these and the picture matches the
  desktop instead of a palette someone chose.
- `groups[].lines[].pairs` — the **edges**, as index pairs into the same `vertices` array
  (`[a,b, a,b, …]`), each entry with its own `color` and `thickness`. Do not derive silhouettes
  from the faces; they are already here.
- A group whose `selected` is **`null`** is the **concrete block** — no identity, nothing to
  join a result to, and the desktop draws it see-through.

**A scene id is NOT an operation id.** The two numbering spaces are unrelated: e.g. two
stiffening plates can be scene `id 7` and `8` while their operations are `1` and `3`. To turn a
picked body into something you can act on, bridge through IOM: `plates[].id` is the scene id and
`plates[].name` is the operation name (the `name` you sent, or the generated default such as `StiffeningPlate1`); `beams[]` likewise for members. **Welds and bolt
grids have no IOM name**, so those can only be referred to by id.

**IOM plate geometry** (for checking a plate's real placement / mid-surface, e.g. is it
where you meant, do neighbours share edges): each IOM `plates[]` carries `geometry.outline`
(`startPoint` + line/arc `segments` in the plate's LOCAL 2D metres) and `geometry.openings` (the
cut-outs; bolt holes are not there — `region` repeats the outer outline only), plus `origin` and unit vectors
`axisX`/`axisY`/`axisZ` (the plate frame). World coord of a local outline point
`(lx,ly)`: `world = origin + lx·axisX + ly·axisY`. With that you can test placement
(distance of each world corner from a target), or dedup world corners across plates —
if many corner instances collapse onto few shared locations, the plates' edges JOIN
(a continuous shell) rather than drift/overlap. The outline and `plates[].origin` lie on the
mid-surface (thickness is centred on it).

## Symptom → cause → confirm

### Nothing answers at the base URL (connection refused, timeout)
- **Cause** → the service is not running, or it runs on another port.
- **Confirm** → `GET /heartbeat` (no `ClientId` needed) answers 200 `API is alive`; the root
  `/` redirects to the Swagger UI `/index.html`.
- **Fix** → the user starts `IdeaStatiCa.ConnectionRestApi.exe` from the IDEA StatiCa
  installation folder, by default `C:\Program Files\IDEA StatiCa\StatiCa <major version>`
  (for example `StatiCa 26.1`). The folder can be chosen in the installer, and several
  versions can be installed side by side: use the one the user names. `-port=NNNN` selects
  another port; the default is 5000. While running, the service holds a license seat, so
  start it yourself only when the user agrees.
- **It exits at start with "This API is disabled for Basic license type"** → the API needs a
  Steel, Complete or Enterprise license (Trial and Educational licenses also work, but their
  terms do not allow commercial use). Nothing in the request can fix it; tell the user.
- Do not scan ports or guess an address. Ask the user where the service runs, then
  `GET /api/5/clients/idea-service-version` to learn its build.

### Everything built and calculated, but a CHECK ROW says `Not calculated`

The hardest class to catch, because every signal you would normally trust is green: the
operations report success, the entity counts in IOM are exactly what you asked for, `Analysis`
reads `100 %`, and `results.messages` is `null`. Two parts can still be in the wrong place
relative to each other — one grown through another, a plate buried in a member.

**A check that names a component the model contains, and answers `Not calculated`, is a
finding, not a formality.** Read the row as "this component could not be assessed", and settle
which of two things it means before acting:

- **The part is mis-placed** — grown through another part, buried in a member. Confirm
  geometrically rather than by another status code: take the two parts' frames from
  `export-iom` and compare directions or extents, the way `grids.md` does for a foundation
  block.
- **Something upstream is grossly overloaded**, and the check that depends on it never runs:
  a fastener utilisation far above 100 % can leave the block `Not calculated`. An adjacent row
  far above 100 % is then itself the explanation, and the geometry needs no fixing.

Separate them by **lowering the load until the neighbouring checks come back under 100 %**. If
the row starts reporting, it was the overload; if it still says `Not calculated` on a joint
that is now comfortably utilised, the placement is wrong.

Note what the clash warnings can and cannot do for you here. They ride in the `Analysis` row's
`unityCheckMessage`, concatenated ahead of a more serious complaint (`"Plate clash warning
Weld clash warning There are no loads on members"`), so they surface while the solve is
blocked. **Once the solve succeeds the message is the utilisation and nothing else** — so
never read a clean `Analysis` line as a statement that the parts do not interfere.

### Operation returned 200 / `addedWithoutIssues:true` but nothing materialized
The single most common failure. Ordered by likelihood:
- **`active: false` sent** → stored dormant, zero geometry, no hint. Omitting the field stores
  the operation **active**, so an absent `active` is not the cause (`field-matrix.md`,
  `operations.md`).
- **Dangling `plateId`** (one you didn't get from a live response) → 200 with
  `addedWithoutIssues: false` and *"Some required member is not specified correctly."*, and the
  operation is stored (SKILL.md rule 8). A referenced `operationId` or `memberId` that does not
  exist in the connection is refused instead: **422** *"Operation N does not exist in
  connection C. Existing operations: …"* (*"Member N does not exist in connection C. Existing
  members: …"*). A reference to an existing LATER operation still gets the engine message
  (`operations.md` § Typical `issues[].details` and what they mean). An unknown steel
  `materialId` on a plate is 422 too. Use only ids from a live GET/POST (SKILL.md rule 8;
  `operations.md`).
- **Cut/weld tool doesn't geometrically intersect its target** → no cut face, no weld.
  Confirm: the cut's `welds` don't appear in IOM. Fix the tool's placement/orientation
  so it actually crosses the target. See "floating element" below and `cuts.md`.
- **Grid on the wrong wall** → bolts and success, on the wrong part: a member `plateSubIndex`
  one past the parallel-candidate list binds the last candidate silently, and an in-range index
  can name the opposite wall, and parallel parts that do not overlap still get bolts. (Items
  not parallel, or an index further off the list, are reported — *"Plates must be parallel."*,
  *"Invalid part of connection"*.) Derive the subIndex from IOM and check the bound wall and
  the positions. `grids.md`.

### An element is "floating" in space (visible but off its member)
Its frame/origin is wrong, so it doesn't intersect the member → downstream cuts/welds
silently no-op.
- **Confirm:** compare the target scene against a KNOWN-GOOD reference (e.g. the model
  `examples/typed_operations.py` builds):
  per-group centroid distance from the node and bbox extent. A group far from the node
  that should be near it = mis-placed. (Global joint offset is fine — compare relative to
  each model's own node/centroid, not absolute coords.)
- **Usual causes:** placement not following the member BODY side (`connectedBy`);
  element axes composed wrong for that ROLE (e.g. a plate's y-axis sign differs between a
  through-member and an attached member — don't assume one orientation is universal);
  using `coordinateSystem` (absolute, brittle) where `memberLcs` would track the member.
  `plates.md`, `members.md`.

### A cut "worked" but produced no weld / left a free part
- Cut BY A PLATE **dissects** (splits into two pieces), it does not trim — a member cut
  by a plate keeps both outer stubs; a weld-less `boundingBox` cut can leave a free part
  → mechanism. Give the cut its `websWeld`/`flangesWeld`, or trim with a work-plane
  instead. `cuts.md`.

### `calculate` returns 200 but `passed:false`, or Analysis: Singularity / deformation > 1 m
The model is a MECHANISM (some part or island can move freely), or a dangling/degenerate
weld crashed the solver. **A failed calculate returns a diagnostic `resultSummary` row —
READ it first.** Most failures name the reason: `Analysis: "Singularity"`, `"There are no
loads on members"`. The dangling-weld case is the exception — it gives the GENERIC
`"Cannot execute the operation."` with no culprit named. That message is the one case to
answer by bisection, and welds are the first group to bisect.
- **Islands not tied together:** each element's plates/welds form a local cluster but
  nothing connects the clusters → free motion. Confirm by finding the missing tie
  (compare against a working reference: what welds an attached element to the main one?).
- **Bisect:** toggle operations `active:false` in groups (PUT each typed GET body with only
  `active` changed) and recalc until the summary comes back; the operation that
  restores/breaks it is the culprit (SKILL.md rule 10).
- **A cut tool that got consumed** → any op using it as a tool silently no-ops → the tie never
  forms. Verify the tool still exists in IOM.
- Beware: `passed:true` can still hide `Analysis: Singularity` in the summary rows —
  read the Analysis row, not just `passed` (`plates.md` singular-doubler note).

### HTTP error (not 200)
- **401** → the `ClientId` header is missing, misspelled, not a GUID, or an id the service did
  not issue. SKILL.md rule 1.
- **404** → project closed (by any client — `io-shapes.md` § GET
  /api/5/projects/{projectId}/close), or it belongs to another client session; or `PUT` with an
  unknown operation id. Re-open / use your own session.
- **422** → validation (bad cross-section name — note the SPACE in `"S 355"`; box /
  parametric sections may not exist in the mprl library at all; unknown mprlName).
  `members.md`.
- **400 with an `errors` map** → model binding (bad enum / malformed nested field).
  IGNORE the misleading top-level `"request": ["The request field is required."]`
  entry — the real cause is the OTHER key. `schemas.md` § Errors / `operations.md`.
- **409 on a typed GET `…/operations/{kind}/{id}`, PUT or POST** → that id exists but is a
  DIFFERENT kind; the `detail` names both types and nothing was written. Fix the route, or drop
  the `id` from a POST — retrying cannot help. An id that exists in no kind is 404 on GET and
  PUT; a POST creates the operation under it. Read the generic `…/operations` list to learn an
  id's kind.
  `operations.md`.
- **422 "OffsetX is only supported when Method is ByIntersection. For other methods move the
  plane via Origin."** on a work-plane → `offsetX` is accepted only with
  `method: "byIntersection"`. On every other method (`byAngles`, `byNormalVector`, …) send
  `offsetX: 0.0` and position the plane through `origin`. `cuts.md`.
- **422 "Weld: positioning … gives the operation no plate to weld to"** on a
  stiffening-plate → the plate's integrated `weld` block only works with `member` and
  `plateOnPlate` positioning (and never on `plateType:"negative"`). Drop the `weld` and
  attach the plate with a separate weld operation, or re-position it. `plates.md`.
- **422 naming the grid kind** on a grid sent with `definedBy: "coordinateSystem"` → that mode
  is the CAD/IOM import shape and cannot author a new grid; the message names which of the four
  conditions failed. Author with `definedBy: "plate"`. `grids.md` §"Grid frame".
  (When a grid materializes nothing, do NOT suspect the assembly id — a bolt-grid
  materializes fine with no `boltAssemblyId`.)

### Common `issues[].details` strings
`"No plate is selected."`, `"There is no parallel edge…"`, `"Nothing to connect"`,
`"Input data of generally located plate are not valid."`, `"Geometry of plate <name> is not valid - …"`
(a degenerate outline: `plates.md`), `"Some required member is not
specified correctly."`, `"Object reference not set…"` — meanings and fixes are catalogued
at the end of `operations.md` ("Typical `issues[].details`"). Cascade principle: fix the
FIRST failed operation, not the dependents.
- **All-CHS/RHS joint, a standalone `weld` op throws "Object reference not set…"** →
  `cuts.md` § "Hollow-section (CHS/RHS) joints" carries the whole path.

## Verification discipline
- Check materialization after each GROUP of operations, not just at the end — a silent
  no-op early cascades.
- Re-open the downloaded `.ideaCon` and re-verify: offline state ≠ stored state for some
  ops (SKILL.md rule 4).
- When you bound coverage (skipped a file, didn't calculate), SAY so — don't let silence
  read as "all verified".
- To confirm free-placed plates sit where intended or that adjacent plates share edges,
  transform IOM `geometry.outline` through `origin`+`axisX/Y/Z` to world coords (see "IOM plate
  geometry" above) and measure — don't eyeball the scene, and don't trust the POST body's
  own coordinates (they're the request, not the materialized result).
