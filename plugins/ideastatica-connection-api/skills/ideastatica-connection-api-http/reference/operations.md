# Typed operations — wire contract

> All 13 kinds are available. On a service that does not expose a kind, its collection route
> answers **404** while `GET .../operations` still answers `200 []` — the route is absent, not
> the project. See `endpoints.md` for how to
> ask.

Endpoint pattern, response wrapper and the 13 kinds: see SKILL.md.

**Answers:** the POST/PUT response wrapper (`ConAddOperationResult`) · rules that hold for every
typed operation · **wire gotchas** — read these before composing any operation body · the two
non-CRUD Operation-tag endpoints · the shared building blocks (`ConConnectedItem`,
`ConWeldData`, positioning, grid geometry) · the own-fields table for all 13 DTOs · example
bodies · what a given `issues[].details` message means.

**Does NOT answer:** what any field *means* geometrically → `members.md`, `cuts.md`,
`plates.md`, `grids.md`, `welds.md` · whether a field applies for the enum value you are
sending → `field-matrix.md` · stable-API request/response shapes → `io-shapes.md`.

## POST/PUT response wrapper (`ConAddOperationResult`)

Every typed `POST`/`PUT .../operations/{kind}` answers this wrapper; `common-properties` and
`weld-sizing` do not.

```json
{ "operation": { "id": 1, "name": "CUT1", "operationType": "CutBeamData",
                 "active": true, "isImported": false },
  "issues": [ { "operationId": 2, "description": "Cannot execute the operation.",
                "details": "...", "severity": "error" } ],
  "addedWithoutIssues": true }
```

`severity` ∈ `info | warning | error | terminatedError`. Same wrapper on PUT.
The server geometrically validates on add (full regeneration runs) and names most failures in
`issues[]` — but `addedWithoutIssues: true` still does not prove geometry (see SKILL.md
rule 3). Verify materialization.

## Rules that hold for every typed operation

- **`name` omitted gets you a generated one** (`Cut7`, `GRD7`, `WorkPlane5`, …). Fine for
  throwaway work; name them if you will look for them later.
- **A body without a required property is 400 naming it** (`cut` `member`/`cutBy`, `plate-cut`
  `modifiedObject`/`cutBy`, `anchor-grid` `foundationBlock`), omitted or `null` alike; nothing is
  written.
- **Nothing is half-applied.** A refused add or update leaves the model exactly as it was;
  which refusals still empty the stored results: `io-shapes.md` § POST
  /api/5/projects/{projectId}/connections/results. An operation the engine cannot build is not
  refused: **it is stored** and answers 200 with `addedWithoutIssues: false`. Correct it with a
  PUT on its `id`; a corrected POST without that `id` adds a second operation.
- **A PUT replaces the whole operation; it does not merge with the stored one.** An omitted
  weld block becomes no weld and an omitted enum takes its default (only the plate editor's
  edits, which a plate DTO cannot express, are kept — `plates.md`). Build the body from the
  typed GET of that operation, change the fields, send the whole body back.
- **An unmodified typed GET body PUT back re-creates the operation.** The read side leaves out a
  stored value that would fail its own validation (a weld a plate could never make, a
  `cuttingPlane` its method never reads); everything else comes back — the catalog ids (a plate's
  `materialId`, an added member's `crossSectionId`, a weld block's `materialId`), a layer grid's
  groups in `rows` (`grids.md`), a grid's `foundationBlock` — and its absence on a
  plate-to-plate contact-grid — and an added member's host (`members.md`). A plate sent with
  `materialId: 0` is stored with the project's first steel and reads back that id (`plates.md`). One case does not round-trip: a grid
  driven by parameters — change it through its parameters (`parameters.md`).
- **Send a PUT to the route of the operation's own kind, with a body from that kind's typed
  GET.** The body's `id` picks the target: an unknown id is 404, an id holding an operation of
  another kind is **409** with the typed GET's message (*"Operation 1 exists but is of type
  'StiffeningPlateOperation', not 'WeldOperation'."*), and nothing is written.
- **A POST that carries an `id` already in use replaces that operation** when it is of the same
  kind (200, same id) and is 409 when it is of another kind. An
  unused `id` creates the operation under that id. Leave `id` out to append a new operation.
- **`active` omitted means active.** Send `false` explicitly to add a dormant operation.

## Wire gotchas

- Enum casing: requests/responses camelCase (`"surface"`, `"doubleFillet"`,
  `"memberLcs"`); `operation.operationType` is a PascalCase label that does not follow the
  route's `{kind}` (`CutBeamData` for a cut, `GeneralPlateData` for a stiffening plate,
  `NegativeVolumePlateOperation` for a negative plate, …); never string-match on it.
- Bad enum / malformed nested field → HTTP 400 with an `errors` map; ignore the
  misleading `"request": ["The request field is required."]` cascade entry.
- `GET .../operations/{kind}/{id}` with an id of another kind → **HTTP 409** (a PUT or a POST
  with such an id too, § Rules that hold for every typed operation), with a
  ProblemDetails `detail` naming BOTH types: *"Operation 1 exists but is of type
  'StiffeningPlateOperation', not 'BoltGridOperation'."* This is a routing mistake, not a
  transient conflict — retrying is pointless; use the named type to pick the right endpoint,
  or read the generic `GET .../operations` list to learn "what kind is id N". An id that
  exists in no kind at all → 404.
- `PUT` with unknown id → clean 404 "Operation N not found in connection C."
- Typed operations survive `/download` → re-open (`isImported` stays false).
- Grids wire quirk: POST wrapper says `isImported: true` (typed GET then says false).
  The typed GET DOES echo `geometry.userPositions` (each position gaining a `gridIndex`)
  and the catalog id `boltAssemblyId` / `anchorAssemblyId`, so a plate-defined grid — with
  explicit positions or with layers — can be read back and re-POSTed. On a plate-defined grid `coordinateSystem` reads back `null`; a
  grid stored as `definedBy: "coordinateSystem"` carries its frame back and replays (see
  `grids.md`).
- Send a `materialId` that came from a live response, or omit it: an omitted `materialId` gives
  the **project's first steel material** (lowest id in `GET .../materials/steel`), not the project
  settings' default material (`materials/<code>/MaterialDefaults/*`). An unknown id is 422
  *"Steel material with id N was not found in the project…"*.
- `stiffening-member` / `negative-member` POST accepts a MISSING `crossSectionId` — the
  member defaults to an available cross-section and materializes normally. Pass `crossSectionId`
  (a live id) only to choose a specific profile. The typed GET returns it.
- Simple desktop-authored ops of a typed kind (plate cuts, grids, welds, plates) ARE
  readable via typed GETs; desktop-authored composites — a base-plate or end-plate
  assembly — are not (generic list only, read-only, no decompose path —
  `templates/explode` only strips parameters).

## Two non-CRUD Operation-tag endpoints

- **`POST .../operations/weld-sizing`** — NO request body; the method is the optional query
  parameter **`?designType=`**. Resizes ALL welds in the connection at once and answers 200 with
  a JSON string naming the method applied; read the status, not just the body. Values, defaults
  and refusals: `io-shapes.md` § POST …/operations/weld-sizing and § Enum: ConWeldSizingMethodEnum.
- **`GET` / `PUT .../operations/common-properties`** — a one-shot bulk edit, **not a default**.
  `PUT` rewrites the material / bolt assembly of every operation that exists at that moment
  (204); an operation added afterwards still gets the project's first steel. `GET` reports the
  id the current operations share (null when they differ, or on a fresh model), so it reads
  like a stored setting but is derived. DTO `ConOperationCommonProperties =
  {weldMaterialId, plateMaterialId, boltAssemblyId}` (all nullable int).

## Shared building blocks

### `ConConnectedItem` — "member or plate" reference
Used by weld/contact (`firstMemberOrPlate`, `secondMemberOrPlate`) and grids'
`connectedItems[]`. Set exactly the fields that identify the target:
`memberId` (a member's surface) | `plateId` (standalone plate) | `operationId` (the
plate created by operation N) | `plateSubIndex` (which plate of a multi-plate object).

**`plateSubIndex` convention DIFFERS by context** — the bases are in `field-matrix.md`; what
each context does with a bad value:
- on a cut / plate-cut target: **required**; omitted or `0` is refused with 422 naming the
  field. **1-based for `plateOfOperation`, but read as a 0-based wall index for `memberPlate`**:
  there `1` is the member's second wall and the first wall cannot be selected (`cuts.md`). An out-of-range value comes back `addedWithoutIssues: false` with
  *"Some required member is not specified correctly."* — reported, not silent.
- in a weld or contact member reference: required, and **`0` is a valid index.** A bare
  `{memberId}` with no sub-index is not index 0: as the second operand it welds nothing and is
  reported (`addedWithoutIssues: false`, *"There is no parallel edge on the second plate…"*);
  as the first it is accepted and welds every wall of the member. Qualify every operand and
  count the welds in IOM.
- in a grid's `connectedItems` on a `{memberId}` item: **0-based over the member's plates
  filtered to those PARALLEL to the grid's first item**, IOM order kept — not the absolute
  export index. Derive it from the export and check the bound wall — an index one past the list
  binds the last candidate silently, and a wrong parallel wall reports success; see grids.md.

The grid takes its CSYS from the FIRST connectedItem — lead with a plate whose frame you
control (an operation you authored), not an engine-framed member plate.

### `ConWeldData` (weld, cut, plate-cut, stiffening-member, stiffening-plate, an anchor grid's shear lug)
`{ kind: continuous|intermittent, type: noWeld|filletFront|filletRear|doubleFillet|cjp|pjp,
   size (m), materialId, beginOffset, endOffset, length, gap }` — which fields each `kind`
reads: `field-matrix.md` § by `weld.kind`; stitches only on a `weld` operation (`welds.md` §
Stitched welds). Semantics + size conventions: `welds.md`.

### `ConCutMemberTarget` / `ConCutByTarget` (cut, plate-cut)
Target: `{ kind: member|stiffeningMember|negativeVolumeMember|stubMember, memberId,
operationId, remainingPart: begin|end }`. CutBy: same + `plateId`, `plateSubIndex` and
kinds `plate | plateOfOperation | memberPlate | stiffeningMemberPlate |
negativeVolumeMemberPlate | stubMemberPlate | workPlane`. Semantics: `cuts.md`.

### `ConPlatePositioning` (stiffening-plate, negative-plate)
Discriminator `conPlatePositioningType` ∈ `concreteBlock | coordinateSystem | joint |
memberLcs | member | plateOnPlate`; supply the chosen mode's fields. Semantics and the
per-mode recipes: `plates.md`.

### `ConGridGeometry` (bolt-grid, anchor-grid, pin-grid)
`shearPlaneInThread` (bool) sits at the geometry's top level and applies to ALL grid types,
not just orthogonal ones. `rowsGridLayout` takes `regular | firstShiftedFull |
secondShiftedFull | firstShiftedShort | secondShiftedShort`. There is NO origin field — the
pattern anchors to the host plate's CSYS origin. Which input style reads which fields:
`field-matrix.md`; semantics: `grids.md`.

### `ConAddedMemberPositioning` (stiffening-member, negative-member)
`positioningType` ∈ `joint | onMember | onPlate`; `placementDefinition` ∈
`rotationsOfX | lcs`; `insertPoint` (Point3D, GLOBAL), `eccentricity` (Vector3D, LOCAL),
`angleAlpha/angleBeta/rotationRx` (rad) or explicit `axisX/Y/Z`; mount fields
`onMemberId`, `onPlateOperationId`, `onMemberPlateIndex`, `mountType`, `mountLocation`,
`plateEdgeIndex`, `positionX/Y`, `rotation`, `pitch`. Semantics: `members.md`.

## The 13 DTOs (own fields; all also carry `id`, `name`, `active`, `isImported`, `operationType`; grids add `isExploded`; omit `id` on POST unless you mean the § Rules `id` semantics)

| kind | DTO | own fields |
|---|---|---|
| `weld` | ConWeldOperation | `placement` (`edgeToSurface`\|`edgeToEdge`), `firstMemberOrPlate`, `secondMemberOrPlate`, `firstPlateEdgeIndex` (**array<int>**), `secondPlateEdgeIndex` (**plain int — array → HTTP 400**), `weld` |
| `cut` | ConCutOperation | `member`, `cutBy` (both **required**), `cuttingMethod` (`boundingBox`\|`surface`\|`surfaceAllAround`\|`mitreCut`), `cuttingPlane` (`closer`\|`farther`), `direction` (`parallel`\|`perpendicular`), `offset` (m), `extendMember`, `websWeld`, `flangesWeld` |
| `plate-cut` | ConPlateCutOperation | `modifiedObject` (ConCutByTarget — the plate being cut), `cutBy` (both **required**), `cuttingMethod`, `remainingPart` (ConPlateSide), `offset`, `weld` |
| `bolt-grid` | ConBoltGridOperation | `boltAssemblyId`, `boltShearForceTransfer` (`tensionShearInteraction`\|`friction`), `connectedItems[]`, `definedBy` (`plate`\|`coordinateSystem`), `coordinateSystem`, `geometry` |
| `anchor-grid` | ConAnchorGridOperation | like bolt-grid (`anchorAssemblyId`) + `anchorType` (`threadedRod`\|`generalAnchor`\|`hookedAnchor`\|`headedStud`\|`washerPlate`\|`reinforcement`), `anchorDiameter`, `embedmentDepth` (the embedment depth; round-trips the sent value), `hookLength`, `hookRotations[]`, `mandrelDiameter`, `headDiameter`, `headedStudMaterialId`, `reinforcementMaterialId`, `reinforcementShape` (`lShape`\|`uShape`), `washerPlateShape` (`circular`\|`rectangular`), `washerPlateSize`, `plateSide`, `foundationBlock` (**required**) |
| `pin-grid` | ConPinGridOperation | `connectedItems[]`, `definedBy`, `coordinateSystem`, `geometry`, `pinOriginalId` |
| `contact` | ConContactOperation | weld-shaped without the weld: `placement`, `firstMemberOrPlate`, `secondMemberOrPlate`, `firstPlateEdgeIndex` (array), `secondPlateEdgeIndex` (int) |
| `contact-grid` | ConContactGridOperation | `connectedItems[]`, `foundationBlock` (omit it for a plate-to-plate contact), `plateSide` |
| `negative-member` | ConNegativeMemberOperation | `crossSectionId`, `length1`, `length2`, `mirrorY/Z`, `positioning` |
| `negative-plate` | ConNegativePlateOperation | `shape` (`rectangular`\|`circle`\|`polygon`), `thickness`, `width/width2`, `height/height2`, `radius`, `polygonData` (string), `materialId`, `positioning` |
| `stiffening-member` | ConStiffeningMemberOperation | `crossSectionId`, `materialId`, `length1/2`, `mirrorY/Z`, `positioning`, `weld` |
| `stiffening-plate` | ConStiffeningPlateOperation | `plateType` (`structural`\|`negative`), `shape`, `thickness`, `width/width2`, `height/height2`, `radius`, `polygonData`, `materialId`, `plateDataId`, `positioning`, `weld` |
| `work-plane` | ConWorkPlaneOperation | `method` (`byAngles`\|`byNormalVector`\|`byIntersection`), `relatedTo` (`joint`\|`member`\|`plate`), `memberId`, `plateId`, `plateOperationId`, `relatedMemberId`, `origin`, `normalVector`, `rotationX/Y/Z` (rad), `offsetX` (⚠️ acts ONLY for byIntersection; a nonzero value on byAngles/byNormalVector is rejected 422 *"OffsetX is only supported when Method is ByIntersection. For other methods move the plane via Origin."*; see cuts.md), `nearIntersection`, `isFatigue` |

`foundationBlock` = ConFoundationBlockDto: `blockType` (`new`\|`existing`), `existingBlockOperationId`
(with `existing` only), and for a new block `concreteMaterialId`,
`offsetTop/Bottom/Left/Right`, `height`, `shearForceTransfer`
(`friction`|`shearLug`|`anchorBending`|`sliding`), `contactType`
(`direct`|`mortar`|`gap`), `mortarThickness`, `shearLug` (ConShearLugDto: `crossSectionId`,
`length`, `positionX`, `positionY`, `rotation`, `flangesWeld`, `websWeld`) — send it with
`shearForceTransfer: shearLug`, `grids.md` § anchor-grid specifics.

## What each kind builds

Every kind materializes geometry visible in IOM/scene: `cut`, `plate-cut`, `stiffening-plate`
(member/memberLcs/coordinateSystem/plateOnPlate), `stiffening-member`, `negative-plate`,
`negative-member`, `work-plane`, `weld` (edgeToEdge), `bolt-grid` (layers AND
userPositions), `anchor-grid` (layers and userPositions both expand to the full pattern, and the foundation
block materializes),
`contact-grid` (the foundation block materializes and IS exported to IOM as
`ConcreteBlockData`; without a block it is a plate-to-plate contact of at least two distinct
plates and creates no block), `contact` (**a contact adds one entry to the weld collection**,
but only `export-iom` tells it from a weld: there it is a `<WeldData>` carrying the operation
name, its `WeldType` and `ConnectedParts`. In `export-iom-connection-data` a weld entry is a
bare `{"id": N}` with no type, so contacts can be counted there but not identified. There is
no separate contact collection either way). `pin-grid` works: it needs **three
distinct parallel plates** (two → 422 naming the rule), and the pin material endpoints plus
library browse exist.

## Example bodies

Cut BEAM (member 2) by COL (member 1), welding the cut:

```json
POST .../operations/cut
{ "name": "CUT1", "active": true,
  "member":  { "kind": "member", "memberId": 2 },
  "cutBy":   { "kind": "member", "memberId": 1 },
  "cuttingMethod": "surface", "cuttingPlane": "closer", "direction": "perpendicular",
  "websWeld":    { "kind": "continuous", "type": "doubleFillet", "size": 0.004 },
  "flangesWeld": { "kind": "continuous", "type": "doubleFillet", "size": 0.006 } }
```

Stiffening plate in member 1's local CSYS:

```json
POST .../operations/stiffening-plate
{ "name": "RIB1", "active": true, "plateType": "structural",
  "shape": "rectangular", "thickness": 0.01, "width": 0.18, "height": 0.18,
  "positioning": { "conPlatePositioningType": "memberLcs", "onMemberId": 1,
                   "offset": {"x":0,"y":0,"z":0}, "rotation": {"x":0,"y":0,"z":0} } }
```

Weld the plate created by operation 4 to member 1 (both references carry
`plateSubIndex`; a standalone weld materializes only when edges geometrically line up —
otherwise "There is no parallel edge..." → prefer the host operation's own `weld` field):

```json
POST .../operations/weld
{ "name": "W1", "active": true, "placement": "edgeToSurface",
  "firstMemberOrPlate":  { "operationId": 4, "plateSubIndex": 1 },
  "secondMemberOrPlate": { "memberId": 1, "plateSubIndex": 0 },
  "weld": { "kind": "continuous", "type": "doubleFillet", "size": 0.005 } }
```

Update = PUT the **whole** stored operation WITH `id` — its typed GET body with the changed
fields (§ Rules that hold for every typed operation). A hand-written body for CUT1 that left out
`direction` and the weld blocks would reset `direction` to `parallel` and remove both welds:

```python
cut = get(".../operations/cut/1")          # CUT1 above: every stored field, `id` included
cut.update(name="CUT1 v2", cuttingMethod="boundingBox", offset=0.005)
put(".../operations/cut", cut)             # the body's `id` picks the target
```

> **In a loop over operations, PUT each one only to the route of its own kind** (§ Rules that hold
> for every typed operation): match the `id` to `operationType` from `GET .../operations` first. An
> operation the typed GET cannot read (a desktop composite) answers a typed PUT or POST at its id
> with 409 and stays as it is.

## Typical `issues[].details` and what they mean

- `"No plate is selected."` — the first weld/contact operand is empty.
- `"There is no parallel edge on the second plate which could welded to the selected edge."`
  — the second operand is empty, a bare `{memberId}` or out of range, the edges don't line
  up, or the first operand's edge passes THROUGH the second's surface instead of lying on it; qualify
  the operand, else use the host op's integrated `weld` field, and trim a penetrating plate with a
  `plate-cut` before the weld (`welds.md` § Read this before authoring any weld).
- `"Nothing to connect"` — a grid's connected items aren't valid plates (e.g. a `{memberId}`
  item listed first). Parallel plates that merely do not overlap are not reported (`grids.md`).
- `"Input data of generally located plate are not valid."` — a `member`-positioned plate whose
  `plateOnMemberIndex` is missing, 0 or past the member's plates (`plates.md`).
- `"Some required member is not specified correctly."` — a reference the engine cannot
  resolve: a forward reference to a later (existing) operation — fix the order
  (`DELETE .../operations` — it also drops the templates and parameters — then re-POST in
  sequence) — a raw `plateId` that resolves to nothing, or a `plateSubIndex` past the plate's
  last sub-plate. A referenced `operationId` or `memberId` that does not exist in the
  connection never reaches the engine: it is **422** *"Operation N does not exist in
  connection C. Existing operations: …"* / *"Member N does not exist in connection C. Existing
  members: …"*, and the operation is not stored.
- `"Object reference not set to an instance of an object."` on weld — hollow sections:
  `cuts.md` § tube-to-tube.
- `"Cutting along a beam is not allowed."` on a `mitreCut` — a member too short for the mitre
  plane, or a wrong `remainingPart` pairing on a nearly straight joint; `cuts.md` § cuttingMethod.
- `"The continuous member cannot be cut."` — `boundingBox` / `mitreCut` on a continuous member;
  `members.md` § `connectedBy` + `isContinuous`.
- Cascade principle: one broken early operation makes every dependent operation fail —
  always fix the FIRST failed operation, not the cascades.
