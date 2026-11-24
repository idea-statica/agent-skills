# Fastener grids — bolt-grid / anchor-grid / pin-grid / contact-grid

**COUNTING** materialized fasteners = `GET .../export-iom-connection-data`
(`boltGrids[]` / `anchorGrids[]` / `concreteBlocks`); the presentation scene draws bolts only as
the holes they punch in plates (it does draw reinforcement anchors). `addedWithoutIssues: true` does
NOT imply any fastener exists — always count via IOM.

**But IOM is not the channel for every question — pick it per datum, or you will measure
something that is already a datum somewhere else:**

| what you want | channel | why not the others |
|---|---|---|
| how many fasteners, and where | **IOM** `boltGrids[]` / `anchorGrids[]` | the scene has holes, not bolts |
| bolt axis / direction | **IOM** `boltGrids[].axisZ` | IFC placement is identity — the orientation hides in an `IfcMappedItem` |
| which wall a grid bit into | **IOM** `boltGrids[].connectedParts[].element` (`origin`, `axisZ`, `thickness`) | the only discriminator; see §"Decoding any grid you were given" |
| assembly name, diameter, grade, fy/fu | **IFC** psets | read as attributes, never measure |
| grip length (clamped stack) | **computed from the IFC mesh** | it is a datum in no channel |

This table is a router, not the reference — the pset names, the reason IFC cannot give the
axis, and the washer-gap method for grip length are all in
§"Bolt properties & grip length — which channel holds which datum". Correct that section, not
this table, when something changes.

**FOUR operations live on this page** — `bolt-grid`, `anchor-grid`, `pin-grid`,
`contact-grid`. Start at `## Prerequisites` (assemblies must exist in the project before any
grid materializes), then note that the early sections are written mostly around bolts and
anchors:
- `## Authoring positions` is **preferred for bolt-grid AND anchor-grid**; `contact-grid`
  has no geometry at all (see `field-matrix.md`), so that section does not apply to it.
- **`pin-grid` and `contact-grid` have their own section**, §"contact-grid / contact /
  pin-grid" — pin's three-plate rule, `pinOriginalId` and the pin material endpoints are
  *only* there. Nothing about pins is in the bolt/anchor sections above it.

**Does NOT answer:** `contact` (the weld-shaped operation, distinct from `contact-grid`) →
`welds.md` · which grid fields apply for the `anchorType` / `definedBy` you are sending →
`field-matrix.md` · plate geometry the grid mounts to → `plates.md`.

## Prerequisites

- Bolt/anchor assemblies: a fresh API project has NONE.
  `POST .../materials/bolt-assemblies {"mprlName": "M16 8.8"}` — the returned id feeds
  `boltAssemblyId` / `anchorAssemblyId`. A grid POST with NO `boltAssemblyId` still succeeds
  and materializes bolts with a default assembly, so an empty field is not the reason a grid
  produced nothing.
  **Send the full `"<size> <grade>"` spelling** — an unknown name is refused with 422 naming
  the value: `{"mprlName": "M16"}` → *"Bolt assembly 'M16' was not found in the library for
  design code ECEN."* List the valid names with
  `GET .../materials/bolt-assemblies/library`.
  **The library is design-code specific and the vocabularies do not overlap** — ECEN has 133
  metric names (`M12 10.9`, `M16 8.8`, …), `american` has 94 imperial ones (`1 1/2 A325`,
  `1 1/2 A490`, …). So `M16 8.8` is a 422 on an AISC project, with the same "not found in the
  library for design code" wording an outright typo produces. Read the project's
  `countryCode` before blaming the spelling, and take names from that project's own library.
  **Send a `boltAssemblyId` / `anchorAssemblyId` that exists in the project** — a supplied id
  that does not is refused with 422 naming the value, and no fasteners are created. Leaving
  the field out, or sending `0`, is the documented fallback: the grid materializes with the
  project's first assembly, so re-read the id from the typed GET when the grade matters. On a
  `threadedRod` anchor-grid `anchorAssemblyId` reads back as `1` even when it was never sent.
- **Author with `definedBy:"plate"`** — it anchors the pattern to the host plate.
  `definedBy:"coordinateSystem"` also round-trips, but it is the CAD/IOM **import** shape and
  is refused for authoring by four separate 422 gates — see "Grid frame" below.
- Concrete for blocks: `POST .../materials/concrete {"mprlName": "C25/30"}` — use the
  RETURNED id in `foundationBlock.concreteMaterialId`. The POST/PUT wrapper carries no block;
  the typed GET and `export-iom` (`<ConcreteBlockData><Material>`) return the id you sent.
- **`connectedItems` reference PARALLEL, overlapping faces.** Each item is one of:
  a plate operation `{operationId, plateSubIndex}` (plateSubIndex 1) OR a member's own
  plate `{memberId, plateSubIndex}` (a flange/web of a member — see the subIndex rule
  below). Faces not parallel → "Plates must be parallel.". **Overlap is not checked**: two
  parallel plates that do not overlap still get their bolts, with 200 and no issue — check in
  IOM that the positions lie on both parts. Bolting an end plate straight to a member
  flange/web works this way — no intermediate doubler plate is needed.
- **The grid's CSYS = the FIRST connected item.** `userPositions` are in that item's
  local XY, and the grid is only valid if the first item's frame suits the layout.
  Lead with an item whose CSYS you CONTROL — for an end-plate joint that's your end
  plate (a plate operation you authored), not a member plate whose local axes are
  engine-internal.
- **`plateSubIndex` on a `{memberId}` item = index into that member's plates FILTERED
  to those PARALLEL to the first item's face, IOM order preserved.** It is NOT the
  absolute IOM plate index. To derive it invariantly: from `export-iom-connection-data`
  take the member's `plates[]`, keep only those whose normal is parallel to the leading
  plate's normal, and among those pick the one on the **SAME SIDE** as the leading plate
  (the wall the end plate actually faces, not the opposite one), then use its 0-based
  index in that filtered list.
  - **"Same side" must be computed from a RELIABLE outward direction — do NOT trust the
    raw IOM `axisZ` sign.** Relative to the outward normal, some walls' `axisZ` point INWARD
    (both flanges of an I-section share one `axisZ`), so a naive `dot(axisZ, beam_dir) > 0` picks the wrong
    (opposite) wall on some orientations. Instead derive each wall's true outward normal
    from geometry, e.g. `outward = sign(dot(wall_centroid − node, n)) · n` (node = the
    joint/column-axis point), then pick the candidate whose outward normal points the
    same way as the end plate / beam axis. This is the exact step where a sign slip sends
    the whole grid to the OPPOSITE wall while still materializing 4 bolts and reporting
    success — so verify the bound wall with the side check in §"Decoding any grid you were
    given".
  - Example: bolting to an I-column flange, the two flanges are the two parallel
    candidates → subIndex 0/1; the web is the sole parallel candidate for a cross-web
    plate → subIndex 0 (1 is one past the list and binds the web again; 2 is reported). The
    same-side rule holds for any column roll or flip: when the column rotates or reverses
    under a beam of fixed direction, the IOM wall order (hence the raw index) shifts, yet the
    rule keeps landing the grid on the wall the beam faces.
    Closed sections too (RHS: only the 2 walls parallel to the plate are candidates,
    their many rounded IOM wall-segments excluded by the parallel filter).
- **Through / multi-plate joints: ONE grid, ≥3 connectedItems.** A set of bolts passing
  through plate + member + plate (e.g. two opposed end plates and the column web
  between them) is a single bolt-grid with three items. First item = a plate you
  authored (CSYS); the middle/through member plate follows.
- **A member `plateSubIndex` two or more past the list is REPORTED**: the response comes back
  `addedWithoutIssues: false` with the issue *"Invalid part of connection"*, and no
  fasteners are created. Read the issues array on every grid write — and still count via
  IOM, because an in-range index landing on the wrong parallel wall reports success either
  way. The grid's `userPositions` survive a download and re-open even when the grid built
  nothing (the stored geometry and `connectedItems` come back unchanged), so fix the
  `plateSubIndex` and re-write the operation rather than re-entering the positions.
  **An index ONE past the last candidate is taken as the last candidate**, with no issue — on a
  two-wall list, `2` binds the same wall as `1`. Derive the index from the filtered list and
  check the bound wall (§"Decoding any grid you were given"); only indices beyond that are
  reported.
- **Check the GET before you PUT it back.** A typed GET echoes `geometry.userPositions` (each
  position gaining a `gridIndex`), `boltAssemblyId` / `anchorAssemblyId` and, for
  `definedBy:"coordinateSystem"`, the frame — so a `userPositions` grid round-trips GET → edit
  one field → PUT under either `definedBy`, and a layer grid reads back its groups in `rows` and
  round-trips the same way, desktop-authored grids included (§"Orthogonal layers"). **A PUT
  replaces the whole geometry**, so a position grid sent with no `geometry.userPositions` is
  emptied and still reports 200 with `addedWithoutIssues: true` and no issues — a lost-geometry
  write looks exactly like a successful edit. Assert the body carries the layout the grid was
  built with (`userPositions`, or the layer `values`/`rows`) before you send it. This is the
  hazard on any hand-built or trimmed PUT body.
- **`userPositions` are taken as sent, not clipped to the connected parts** — see
  "Authoring positions" below.

## Authoring positions

### `geometry.userPositions` — PREFERRED for bolt-grid AND anchor-grid (exact XY)

List of `{x, y, gridIndex?, slottedHoles?, hookRotation?}` in the plate's local XY.
Set `geometry.type:"orthogonal"` (ignored when userPositions present), OMIT all
layer/polar fields. Result is EXACT to the mm (IOM returns precisely the sent points).
Compute any pattern yourself and hand over XY — the universal, unambiguous method.
- **Do NOT mix `userPositions` with layer fields** — REJECTED on write with HTTP 422:
  *"Grid geometry: UserPositions cannot be combined with
  TopLayers/LeftLayers/Radii/Angles/PolarCounts. Use UserPositions
  for explicit positions OR the layer/radius inputs for a regular grid."* Pick one input
  style per grid.
- **userPositions WORKS on anchor-grid too** — materializes the sent positions and keeps
  the foundation block. Layers work on anchor-grid the same way as on bolt-grid
  (§"Orthogonal layers"). Pick whichever suits the layout — `userPositions` for an explicit
  pattern, layers for a regular one — and note that embedment materializes on both paths.
- **Check your own coordinates: a position outside the parts is honoured, not refused.**
  Positions are not clipped to the connected parts. Every sent position comes back unchanged
  in the IOM export and is built as a real fastener with its holes cut, and **the member
  being bolted stretches to reach it** while the plate does not — e.g. bolts placed 2 m off
  the plate stretch the member out to them, with 200 and no issue reported. So a mistyped coordinate gives you a silently oversized model rather than
  an error. Read the positions back from the IOM export and check them against the pattern
  you intended.

### Orthogonal layers — signed cumulative COORDINATES in the grid's local CSYS

- **A grid has two lists, as in the desktop: `topLayers` = Rows = local y lines, `leftLayers` =
  Positions = local x lines.** Fasteners = x-lines × y-lines cartesian product. A line on the
  negative side is a negative value in the same list, as its own group in `rows`:
  `[[{"value": 0.08}], [{"value": -0.08}]]` gives lines at ±0.08, `0.04; -0.06` lines at +0.04
  and −0.06. A single value is a single line: `topLayers` and `leftLayers` `{values: [0.06]}`
  give ONE fastener at (0.06, 0.06). Bolt-grid and anchor-grid read the layers identically.
  Example — four fasteners at (±0.06, ±0.06):
  `"topLayers": {"rows": [[{"value": 0.06}], [{"value": -0.06}]]}` and the same `leftLayers`.
- **`bottomLayers` / `rightLayers` are not grid fields**: a body carrying them is accepted, they
  are ignored, and a grid described only by them builds no fasteners. **Count the fasteners in
  IOM.**
- `values[]` are a CHAIN: first = absolute coordinate of the first line, each next = a
  pitch ADDED on. Anchor: `[0.08,0.06,0.06,0.06,0.08]` → lines at 0.08, 0.14, 0.20,
  0.26, 0.34. This is the desktop's `80 60*3 80` Rows/Positions syntax pre-expanded
  (`*n` = repeat). `values[]` is always ONE chain.
- **`rows` carries the desktop's `;` GROUPS** — independent chains, one inner list per group,
  each entry `{value, repeatCount}` (`repeatCount` = the desktop's `*n`, omitted = 1). Two groups
  at ±0.08: `{"rows": [[{"value": 0.08}], [{"value": -0.08}]]}` — lines at 0.08 and −0.08. The
  same numbers as `values: [0.08, -0.08]` are one chain: lines at 0.08 and 0. A typed GET returns
  both, `rows` with the groups and `values` flattened, so an unmodified GET → PUT keeps the
  layout. **Send `rows` for a layer with more than one group**, every group a list; send `values`
  and `rows` together only when they describe the same layout. A contradiction (*"Grid positions:
  Values and Rows describe different layouts…"*), `repeatCount` ≤ 0 or a `null` entry inside a
  group is **422**; a `null` in place of a whole group is dropped at 200. Decode a grid you did not
  author from the IOM positions.
- Values are signed coordinates from the host plate's CSYS origin, not sizes (same principle
  as plate width/width2) — center the plate CSYS so a ± pair lands symmetric on the plate.
- **`rowsGridLayout` staggers the rows** (here: the `topLayers` lines, not the `rows` field). `regular` keeps every
  row on the `leftLayers` positions. `firstShiftedFull` shifts the first row and every second
  row after it, `secondShiftedFull` the others: in a shifted row each fastener moves to the
  middle of the gap to the next `leftLayers` line, and the last one by half the last pitch — so
  lines at ±0.04 / ±0.08 become −0.06 / 0 / 0.06 / 0.10, off-centre. The `…Short` variants then
  drop the last fastener of each shifted row. Example, 3 rows × 4 positions at ±0.04 / ±0.08: `regular` and
  both `…Full` give 12, `firstShiftedShort` 10, `secondShiftedShort` 11. Read the positions
  back from IOM.

### Polar

- **`radii` and `angles` are `ConGridPositions` objects, the same shape as the layer fields** —
  `"radii": {"values": [0.08, 0.15]}`, not a bare array. Only `polarCounts` is a plain list of
  ints (`[4, 8]`).
- `polarInput:"byAngle"` + `angles` (radians) → exactly one bolt per listed angle.
- `polarInput:"byCount"` — `polarCounts` is CONTEXT-derived, not literal (same value →
  different counts on different host plates; `[4,8]` → 8+8=16). Read the result from IOM.
- `radii` are CUMULATIVE: `{"values": [0.08, 0.15]}` → rings at 0.08 and 0.23.

### Grid frame

Two frames, and the choice decides where the pattern's origin sits.

- **`definedBy:"plate"`** anchors the pattern to the HOST PLATE's own CSYS origin — the
  geometry block has no origin field of its own. A corner-referenced plate lands the
  pattern in the corner; center the plate via `width=width2` + `height=height2` half-sizes
  (NOT width2=−width, that's degenerate — see plates.md). Any `coordinateSystem` object
  sent alongside is dropped, since the plate supplies the frame.
- **`definedBy:"coordinateSystem"` is NOT an authoring choice — you cannot start a grid this
  way.** It is the shape CAD/IOM import produces, and the API refuses anything else with a 422
  naming the reason. Four gates, on all three kinds (`bolt-grid` / `anchor-grid` / `pin-grid`,
  each message carrying its own prefix):

  | what you send | answer |
  |---|---|
  | no `coordinateSystem` block | 422 *"requires the CoordinateSystem block (origin and axes)"* |
  | `isExploded` false or omitted | 422 *"cannot author a new grid — the mode is produced by CAD/IOM import"* |
  | no / empty `geometry.userPositions` | 422 *"has no positions to place fasteners at"* |
  | any layer or polar input beside the positions | 422 *"accepts only explicit positions"* |

  So the only accepted body is the import shape — frame + `isExploded: true` +
  `geometry.userPositions`, no layout fields — and it round-trips completely: typed GET carries
  the frame back, PUT of the unmodified body is identity, POST of it creates a second grid, and
  save + reopen preserves all four. **To author a grid yourself, use `definedBy:"plate"`.**

  **`definedBy`, `coordinateSystem` and `isExploded` sit at the ROOT of the operation, not
  inside `geometry`** — nested, they are silently dropped and the POST answers 200 with
  `addedWithoutIssues: true` having stored `definedBy: null`, which reads exactly like the gate
  failing to fire. A wrong shape is not dropped the same way: `topLayers`, `leftLayers`,
  `radii` and `angles` are `ConGridPositions` = `{"values": [...], "rows": [[...]]}`, and a bare
  array in their place is not bound — the request is refused with HTTP 400 and nothing is
  stored. **Read the typed GET back before believing any grid result.**
- **Anchor embedment materializes on BOTH geometry paths.** Sending `embedmentDepth: 0.3`
  yields IOM `AnchoringLength = 0.3` whether the grid is defined by orthogonal LAYERS
  (`topLayers` / `leftLayers`) or by `userPositions`. Choose the layout that suits the
  geometry; embedment is not a reason to prefer one.

## anchor-grid: choosing the anchor type

**`anchorType` decides which other fields mean anything — send it first.** Omit it and the
grid silently becomes `threadedRod`, so every field belonging to another type is dropped
without a word (200, `addedWithoutIssues: true`, and the typed GET reads them back as
`null`/`0`).

Which field identifies the fastener, and which extra fields each type reads: `field-matrix.md`.
The split there is the trap: the first four types take a **bolt assembly**, `headedStud` and
`reinforcement` take a **bare diameter** — send `anchorDiameter` for those two. An
`anchorAssemblyId` sent to them is dropped. Without a diameter a `reinforcement` grid is 422
(*"A reinforcement anchor requires AnchorDiameter (rebar diameter) greater than zero."*); a
`headedStud` grid is stored with diameter 0 (200, no issue): IOM lists its positions, but the studs
have no solid.

**There is no `installationProcess` field on the operation** even though the desktop has one
(*Post-installed* / *Cast-in-place*) and it governs which types the GUI offers there. Over
REST it is **derived from `anchorType`**: `threadedRod` comes back as post-installed, the
other five as cast-in-place. Do not look for the field on the operation —
read it from `export-iom` (XML), as `<AnchorInstallationProcess>`.

**Units are not uniform inside this one operation** — as the desktop shows them:

| field | unit | sent → shown in the desktop |
|---|---|---|
| `embedmentDepth`, `anchorDiameter`, `headDiameter`, `washerPlateSize` | **metres** | `0.056` → *Washer plate size 56 mm* |
| `hookLength` on `reinforcement` | **metres** | `0.15` → *Hook length 150 mm* |
| **`hookLength` on `hookedAnchor`** | **multiple of ø** | `5.0` → *Hook length **[d]** 5* |
| **`mandrelDiameter`** | **multiple of ø** | the design-code value is used (below) |

So the same field name carries different units depending on `anchorType`. None of this is in
the schema — the anchor-grid operation carries **no property descriptions at all**.

**`mandrelDiameter` (bend radius as a multiple of ø) is set by the design code** — 7.0 for a
ø20 bar on EN — whatever you send. The typed GET echoes what was sent (0 when omitted); read the
value the model uses from `export-iom` (XML) `ReinforcementMandrelDiameter`.

**`hookLength` must reach the code minimum: 5 ø on EN, 3 ø on AISC, 1 ø on the other codes** —
on `hookedAnchor` that is the number itself (`5.0`), on `reinforcement` metres (0.10 for ø20 on
EN). A shorter hook is 422 naming the minimum (*"HookLength 0.09 m is below the minimum for
design code ECEN: a reinforcement anchor's hook must be at least 5 times AnchorDiameter,
0.1 m."*).

**Hook rotation (radians, reinforcement anchors) has one channel per layout:** on a
`userPositions` grid send `hookRotation` on each position; on a layer grid send the grid-level
`hookRotations` array, one value per anchor — check in the scene which anchor took which value.
Each form acts only on its own layout — `hookRotations` on a `userPositions` grid stores and
echoes but turns nothing.

**Read the rotation from the typed GET and see it in the scene.** No IOM channel carries a hook
rotation, and the IFC export does not tessellate the hooks. The presentation scene draws the
reinforcement anchors with their rotation.

A working body:

```json
{ "anchorType": "reinforcement", "anchorDiameter": 0.02, "embedmentDepth": 0.3,
  "reinforcementMaterialId": 4, "reinforcementShape": "lShape",
  "hookLength": 0.15,
  "geometry": { "type": "orthogonal", "userPositions": [
      {"x": 0.1, "y": 0.1, "hookRotation": -0.7854},
      {"x": 0.1, "y": -0.1, "hookRotation": 0.7854} ] } }
```

**Read the anchor type from the typed GET or from `export-iom` (XML), not from
`export-iom-connection-data`.** The XML `<AnchorGrid>` carries the IOM type — vocabulary
`Straight, WasherPlateCircular, WasherPlateRectangular, Hook, HeadedStud, Reinforcement,
GeneralAnchor` — and `AnchorInstallationProcess`. The XML `HookLength` is the hook as the code
measures it — on EN a `hookedAnchor` reads the sent value plus half a diameter, a
`reinforcement` hook the value sent — and `ReinforcementMandrelDiameter` is the mandrel the
model uses.
`export-iom-connection-data` reports every anchor grid as `anchorType: "straight"`,
`postInstalled`, with hook length and mandrel 0.

## anchor-grid specifics

- **Layers on an anchor-grid** work as on a bolt-grid (§"Orthogonal layers"); the foundation
  block is built either way. A full IOM import (`AnchorGrid.Positions` in the OpenModelContainer XML +
  `POST /projects/import-iom-file`) also works if you already have an IOM; how the import sets a
  new block's height: `io-shapes.md` § POST /api/5/projects/import-iom-file.
- **`plateSide` picks WHICH FACE of the host plate the block is built on** — send it whenever
  the grid carries a `foundationBlock`. Values are `lowerSide` · `upperSide` · `bothSides` ·
  `center` · `default` (`default` reads back as the side it resolved to); a value from the plate
  `location` vocabulary (`leftSide`/`rightSide`) is refused with a bare **HTTP 400**.

  It is read against the **plate's own normal**, not the member's axis, so re-orienting the
  plate takes the block with it — and which of the two names is correct therefore depends on
  how the plate was built, not on where the member points. **Derive it, do not carry a value
  over from another model**: build the grid, take the block's `AxisZ` from `export-iom` and dot
  it with the member's `axisX`; the block must point AWAY from the steel, and if it does not,
  send the other side.

  Getting it wrong is silent in every channel the API offers — the add succeeds, the scene and
  IOM counts are right, and `Analysis` still reads `100 %`. The one hint is the **`Concrete
  block` row coming back `Not calculated`**, which reads like "not applicable" rather than
  "geometry is wrong" — and it is not exclusive to this mistake, so use the direction check as
  the actual test.
- **Foundation block — everything sits inside `foundationBlock`.** The service's messages and the
  desktop also call it the *concrete block*, IOM `ConcreteBlockData`; it is one object. An anchor grid requires it
  (omitted or `null` → 400 naming `foundationBlock`). A new block is `foundationBlock` with
  `blockType: "new"` (the default) and its definition, all lengths in metres. Send
  `blockType` and `existingBlockOperationId` inside `foundationBlock`: at the operation root they
  are dropped, so the grid has no `foundationBlock` — an anchor grid answers the 400, and a
  contact grid is taken as a plate-to-plate contact (§ "contact-grid / contact / pin-grid").
  **The plan offsets are `offsetTop`/`offsetBottom`/`offsetLeft`/`offsetRight` and the depth is
  `height` — NOT `offsetX`/`offsetY`/`depth`.** Names outside that set are dropped, so with the
  offsets misnamed the block still materializes but sits flush with the plate footprint (all
  offsets 0). **Always send a positive `height`**: a missing or ≤ 0 value — including one lost
  to a misspelled field name — is rejected with 422 *"Foundation block height must be greater
  than zero."* To confirm the offsets landed, read the outline from **`export-iom`** — its
  `<ConcreteBlockData>` carries `OutlinePoints`, `Material` (the `MatConcrete` reference of your
  concrete) and the block's axes; `<Length>` and `<Width>` are the plan size along the host
  plate's local x and y, and `<Height>` and `<Depth>` both carry the block's stored `height` — the
  sent value, or after an IOM import the height the import set (`io-shapes.md` § POST
  /api/5/projects/import-iom-file).
  `export-iom-connection-data` lists the block as a bare `{"id": N}`: it counts blocks and says
  nothing else about them.
  `contactType` mortar/gap lower the block top by `mortarThickness` (e.g. `mortarThickness`
  0.03 lowers it by 30 mm). A free stiffening-plate binds the grid fine.
  **An existing block is shared between grids — send
  `"foundationBlock": {"blockType": "existing", "existingBlockOperationId": N}`** with `N` the
  id of an EARLIER operation that created the block, and no definition values: both grids
  then share one block in the IOM export (no new `concreteBlocks[]` entry). Each mistake is a
  422 that names it and stores nothing:
  - no `existingBlockOperationId` → *"An existing foundation block requires
    ExistingBlockOperationId — the operation that produced the block."*;
  - an id that is not an earlier block-creating operation →
    *"FoundationBlock.ExistingBlockOperationId 999 does not identify a concrete block. …
    Operations before operation 25 that create a concrete block: 5."* (the list is the valid
    set);
  - a definition field with a value — a non-zero height, offset, material or mortar thickness,
    a transfer other than `friction`, a contact other than `direct`, a lug →
    *"… apply to a new foundation block only; an existing block takes them from the operation
    that produced it."*;
  - `existingBlockOperationId` on a `new` block → *"FoundationBlock.ExistingBlockOperationId
    applies to an existing block only; a new block is defined by its own fields."*
  The typed GET of a grid on an existing block returns the definition fields as zeros (and
  `friction` / `direct`); that body PUTs back unchanged. (plates.md's `concreteBlockIndex` takes
  the same kind of value.)
- **The four offsets are in the HOST PLATE's frame, not global axes.** The block hangs off the
  plate named in `connectedItems` (GUI: *Related to = Plate*), so Top/Bottom/Left/Right are read
  in that plate's local x/y. Rotating the host plate 90° about z leaves the `OutlinePoints` in
  `export-iom` **unchanged**, while the block's `AxisX`/`AxisY` rotate with the plate. So the
  outline is local too — convert with
  `origin + u·axisX + v·axisY`, exactly as for plates. Do not compare a block outline against
  global coordinates. (All of this is `export-iom`; the connection-data export has only the id.)
  Each offset extends its own side beyond the plate edge: a 0.3 × 0.3 plate with
  Top/Bottom/Left/Right = 0.3/0.1/0.2/0.05 gives a block spanning 0.3+0.3+0.1 = **0.7** by
  0.2+0.3+0.05 = **0.55** (matches the GUI's own dimension lines). The GUI shows all four in one
  `Offsets [mm]` field in that order — `300 100 200 50` for the example above.
- `shearForceTransfer`: `friction`, `anchorBending`, `sliding`, or `shearLug` **together with**
  `foundationBlock.shearLug` = `{crossSectionId, length, positionX, positionY, rotation,
  flangesWeld, websWeld}` (a project cross-section; metres and radians; the welds are
  `ConWeldData`, `noWeld` when omitted). The lug is built as a member with its welds — count it
  in the scene. A `shearLug` block with any other `shearForceTransfer` is **422**; `shearLug`
  without the block answers 200 with `addedWithoutIssues: false` and *"Cannot create steel
  material ''."*. The typed GET returns the block, so GET → PUT keeps it.
  **The lug is placed in the host plate's frame:** `positionX` / `positionY` are metres along
  the plate's local x / y from the plate's CSYS origin (not the plate or block centre) — on an
  `upperSide` block `positionY` runs along −y, because the block's frame is turned over;
  at `rotation` 0 the section depth runs along the plate's local y, and a positive `rotation`
  turns it right-handed about the normal pointing from the block towards the steel; the lug runs
  `length` into the block from the plate face on the `plateSide`. In IOM the lug is an extra
  entry in `beams[]`.
- GUI mapping: the GUI "Fastener grid or Contact" operation switches REST kind by its
  Fastener dropdown (Bolts→bolt-grid, Anchors→anchor-grid, Contact→contact-grid). GUI
  "Shear force transfer: Anchors" ↔ enum `anchorBending`. GUI "Embedment depth" reads
  back in `embedmentDepth`, round-tripping the sent value. GUI *Anchored to* ↔
  `foundationBlock.blockType`, GUI *Concrete block* ↔ `foundationBlock.existingBlockOperationId`;
  the last connected item of a GUI contact is the block or, for a plate-to-plate contact, a plate.
  A desktop grid's `connectedItems` can end with `{plateId: 0}`: on a grid with a concrete
  block it stands for the block side and is harmless to send back.
- **Read an exploded grid's layout from IOM** — `anchorGrids[].positions` /
  `boltGrids[].positions` always hold the real fasteners; the typed GET's `rows` matches them
  only for a grid that is not exploded. **GET→PUT of the unmodified body is an
  IDENTITY operation** (anchors + block preserved). To change the layout, send `userPositions`
  or import IOM.
  (Watch the operation KIND too: a grid the desktop made as part of a composite end-plate / base-plate operation is not a
  `bolt-grid` operation at all — the bolt-grid list comes back empty while IOM shows the
  bolts.)
- **`isExploded` records HOW the layout was entered** — the *Plate editor*'s explode state,
  which the desktop sets itself when someone enters fasteners by position instead of by grid.
  The dialog switches whole field groups on it: exploded hides the row/polar rows, not exploded
  shows them.
  **Send `isExploded: true` alongside `userPositions`.** Sending positions IS the
  entered-by-position case, and the flag is settable over the API — sent on POST it comes back
  `true`, and `PUT isExploded: true` onto an existing grid is accepted and stored — but the API
  does not *derive* it: omit it and it stays `false`. Fasteners materialise either way; leaving
  it out only leaves the desktop dialog showing empty `Item` rows and polar parameters that
  were never sent.
  **Never send `isExploded: true` with layer or polar input.** The flag is stored as sent, and
  on an exploded grid the engine removes every fastener the layout generates — the write is not
  refused and the grid ends up with no fasteners; its typed GET then shows an empty
  `userPositions` and no layers. Send `false` or omit it unless the grid is given by
  `userPositions`.

## Decoding any grid you were given

IOM `export-iom-connection-data` materializes fasteners regardless of authoring style —
including the desktop's composite end-plate / base-plate operations, which appear with full
positions even though the typed GETs return `[]` for them.
- `positions[]` = `{x,y,z}` in the GRID's local frame; entry carries `origin` +
  `axisX` (global). **Global = origin + x·axisX + y·axisY**, axisY = n × axisX
  (n = plate normal).
- **Bolt positions are SCHEMATIC — they sit on the FIRST connected item, not on the
  member the grid ties to.** The grid `origin`/`axisZ` equal the first connected item's
  midsurface origin/normal (for an end-plate joint: the end plate). Each bolt is a
  segment centred on that plane, normal to it. So the drawn geometry is IDENTICAL whether
  the grid attached to the correct member wall or the OPPOSITE one — **which wall a grid
  is analytically bolted to is NOT derivable from bolt positions (IOM or IFC).**
- **The wall side lives ONLY in `boltGrids[].connectedParts`** — it lists the actual
  plates the grid ties (end plate + the connected member wall), each entry
  `{typeName, id, element}` with the plate's `name`, `thickness`, `origin` and `axisZ` under
  `element`. **Side check = the wall's distance from the end plate along the end plate's
  normal**: `|dot(wall.origin − endplate.origin, endplate.axisZ)|` equals
  `(wall.thickness + endplate.thickness) / 2` (plus any gap you built in) for the wall the end
  plate faces, and is larger for any wall further away. Use only the projection on the normal —
  a wall's `origin` can lie far from the end plate in-plane. Comparing the two `axisZ` does not
  work: both flanges of an I-section carry the same `axisZ`, and on a hollow section the sign
  flips with the end plate's normal. A grid on the wrong wall still materializes bolts and
  reports success.
  The grid-level `boltGrids[].length` reads 0 — the grip is not there (measure it, below).
- **Dead ends — do NOT try these to find the side:** neither bolt position, nor the IFC
  fastener name, nor a shank-vs-material collision test can tell the wall side. The IFC
  exporter carves each hole (`IfcOpeningElement`, tied via `IfcRelVoidsElement`) from the
  shank geometry itself, so the model is ALWAYS internally collision-free even when the
  grid is physically wrong (a shank shoved through a hollow section gets holes cut in both
  walls it crosses). Geometry is internally consistent regardless of analytical
  correctness. `connectedParts[].element` (the side check above) is the only discriminator.
- `boltGrids` is an ENVELOPE — not 1:1 with operations. To attribute positions to one
  operation: toggle `active:false`, diff IOM, toggle back.
- The layout is reachable multiple ways (no unique inverse) — never reverse-engineer
  someone else's layer values.
- Grid counts depend on CONNECTION CONTEXT, not just geometry fields (host plate size,
  edge distances, spacing rules) — confirm actual counts via IOM.

## Bolt properties & grip length — which channel holds which datum

Don't measure what is already a datum. Three channels, three roles:
- **IFC property sets** (`GET .../export-ifc`, parse with IfcOpenShell) — the RICHEST bolt
  data source. `IfcMechanicalFastener` carries pset `IDEA_BoltGrid`
  {`Assembly` e.g. "M20 8.8", `Diameter`, `Hole diameter`, `Plane in thread`} and
  `IDEA_MaterialBoltGrade` {grade, fy, fu, E}. Welds come through as `IfcFastener` with
  pset `IDEA_Weld` {`Type`, `Throat thickness`} — **IFC carries welds as geometry AND data; the
  scene carries their drawn geometry, one group per weld; IOM has weld data but no solids.**
  Plates and sections have `IDEA_Plate` / `IDEA_CrossSection`. Read these as attributes; never
  measure.
- **IOM** (`export-iom-connection-data`) — the only channel with the bolt DIRECTION as a
  declared datum: `boltGrids[].axisZ` (+ positions, + `connectedParts[].element` for the wall side).
  IFC does NOT expose the axis: the fastener `ObjectPlacement` is identity, the real
  orientation is baked into an `IfcMappedItem`.
- **GRIP LENGTH (clamped stack thickness) is in NO channel as a datum — compute it from the
  IFC mesh.** A bolt tessellates to disjoint solids (shank + head + nut + 2
  washers); the washers are the thin (~3 mm) discs. Grip = gap between the two outermost
  washers' inner faces along the shank axis. Measure on ONE bolt per grid (all share it).
  It is a real discriminator the schematic bolt position is not: a grid biting one wall
  reads ~= t_plate + t_wall; one passing through a hollow section reads the full
  through-thickness.

## contact-grid / contact / pin-grid

- **contact-grid foundation block IS authorable over REST** — POST a contact-grid with a
  `foundationBlock` (`blockType: "new"`, valid `concreteMaterialId`, positive `height`) and the
  block materializes; `blockType: "existing"` bears the plate on another grid's block, exactly
  as for an anchor grid (§ anchor-grid specifics). The block is sized by `height` plus four
  `offsetTop/Bottom/Left/Right` — there are no `width`/`depth` inputs; the plan outline is the
  connected plate grown by those offsets.
  **Verify it in `export-iom`**: its `<ConcreteBlockData>` reads exactly as for an anchor grid's
  block (§ anchor-grid specifics); `export-iom-connection-data` only counts blocks.
  The typed GET reads back the whole `foundationBlock` — `concreteMaterialId` included — so a
  GET → edit → PUT round-trip is safe for a grid with a block.
- **A contact-grid without `foundationBlock` is a plate-to-plate contact.** Give it at least
  two DISTINCT plates in `connectedItems` and no `plateSide`; it creates no concrete block. One
  plate (or the same plate twice) is 422 *"Contact grid: a contact without a concrete block
  connects at least 2 distinct plates, but ConnectedItems references 1."*, and a `plateSide` is
  422 *"PlateSide applies to a contact on a foundation block only; a plate-to-plate contact has
  none."* The typed GET of such a grid — desktop-made ones included — reads `foundationBlock`
  and `plateSide` absent and both plates in `connectedItems`, and an unmodified GET → PUT keeps
  it as it was.
- **contact** (weld-shaped, no weld data): accepted between a plate operation and a
  member (`edgeToSurface`), and it needs the same edge-on-surface geometry a weld does. It
  rides in the weld collection, so it is countable everywhere — but only `export-iom`
  identifies it, as a `<WeldData>` with `WeldType` = **`Contact`** (`welds.md` owns the
  details). `export-iom-connection-data` gives it as a bare `{"id": N}` and the scene tags it
  `kind: "weld"`, same as a real weld.
- **pin-grid**: a pin connects at least THREE distinct parallel plates, so give a pin-grid at
  least three `connectedItems` — two plates is a bolt-grid, and a 2-item pin-grid is refused
  with 422 stating the rule. Identify the pin with `pinOriginalId` — or omit it: an empty pin
  catalog gets the default pin added for you (available under ECEN).
  Pin materials have their own endpoints: `GET .../materials/pin/library` lists the available
  names (`D16`, `D20`, `D24`, `D27`, `D30`, `D36`), `POST .../materials/pin
  {"mprlName": "D20"}` creates one and returns the id to feed `pinOriginalId`, and
  `GET .../materials/pin` lists what the project holds. The pin also carries
  `holeDiameter`, `hasPinCap`, `pinCapDiameter`, `pinCapThickness` and `pinOverlap`, all
  derived from the library name.
  **The three-plate rule counts DISTINCT plates.** The same `plateId` twice counts once, and
  `plateSubIndex` does not split one plate into two. Give every member item its
  `plateSubIndex`: a bare `{memberId}` passes the count but is reported *"Invalid part of
  connection"* and builds nothing.
  Three parallel plates plus a pin id gives one pin in the IOM export (`pinGrids`).
