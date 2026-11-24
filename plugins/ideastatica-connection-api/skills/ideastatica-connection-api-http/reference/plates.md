# Plates — stiffening-plate / negative-plate positioning

**Answers:** plate footprint conventions (the x mirror, two-sided extents) ·
`conPlatePositioningType` modes · `polygonData` · `plateType: negative` · **and the `weld`
gate — which positionings accept an integrated `weld` at all.** That gate is for plates; added members: `members.md`.

**Does NOT answer:** added-member placement, `length1`/`length2`, `mountType` →
`members.md` · which fields apply for the positioning you are sending → `field-matrix.md` ·
how a negative plate actually removes material (it needs a follow-up `cut`) → `cuts.md` ·
weld typology, edge candidates and verification → `welds.md`.

## Conventions that apply to ALL plate-creating operations

- **Footprint x is MIRRORED for a rectangle**: it extends from the positioning origin
  into **−xAxis** of the declared frame (that is its `width`; `width2` grows into +x); y
  (height) follows +yAxis normally. **`polygonData` is NOT mirrored**: its coordinates are used
  as sent in every positioning mode and IOM echoes them unchanged — only the frame differs (in
  `memberLcs`, plate x = member local z, plate y = member local y). To center a rectangle on a
  point, place the origin at `center + width/2 · xAxis`.
- **Thickness is CENTERED on the positioning plane** (20 mm plate at z=0 occupies
  z ∈ [−0.01, +0.01]). Exception: a `concreteBlock` plate lies ON the block face, it is not
  centred on it — a thicker plate keeps one face on the block and grows away from it.
- **FLUSH placement — how much you correct for depends on the JOINT you are after.** Every
  plate is positioned by its MID-plane, and the target face you read from IOM
  (`region`/`origin`) is the target's MID-surface too. Two cases, and conflating them is the
  usual reason a plate ends up buried in its host:

  | joint | correct for |
  |---|---|
  | **EDGE on surface** — a weld or a `contact`, e.g. a rib standing on a face | the TARGET's half-thickness: `offset = (distance to target mid-surface) + t_target/2`. The plate's OWN thickness does not move where its edge lands — it only sets how wide the weld comes out: a perpendicular rib welds identically whatever its thickness, and so does one tilted up to 45°. |
  | **SURFACE on surface** — two faces bearing on each other, the `contact-grid` case | BOTH half-thicknesses, since each face sits half a thickness off its own mid-plane: `offset = (distance to target mid-surface) + t_target/2 + t_plate/2` |

  Dropping the `t_target/2` term buries the plate half the target's thickness INTO it — a
  silent clash the wrapper won't flag; `calculate` then reports a "Plate clash warning". Read
  the target's own thickness from IOM; don't assume it's thin. (On a thin wall the error is
  only t_target/2, which is easy to miss.)

  **Easier than computing either:** position the rib with
  `conPlatePositioningType: "member"` and it lands on the chosen wall by construction — the
  recipe in `welds.md` §"Read this before authoring any weld". Compute an offset only for a place
  that mode cannot reach.
- Rectangular plates are CORNER-anchored at the frame origin; `shape:"circle"`
  (+`radius`) is CENTER-anchored — the convention differs between shapes.

## `width`/`width2`, `height`/`height2` — TWO-SIDED EXTENTS from the frame origin

One model, ALL positioning modes: each pair holds the
plate's two extents taken FROM the frame origin — `width` grows into **−xAxis**,
`width2` into **+xAxis** (signed; a negative value pulls that edge to the opposite
side). `height` grows into **+yAxis**, `height2` into −yAxis.
- `width=0.2, width2=0` → footprint from origin 0.2 into −xAxis (the "x mirror").
- **`width=width2` (same positive value) → plate CENTERED on the origin** — the
  standard centering idiom (e.g. a 220×120 plate from the GUI stores `0.11/0.11` +
  `0.06/0.06`; a coordinateSystem plate with `0.1/0.1` spans ±0.1). Use this instead
  of shifting the origin.
- `width=0.25, width2=−0.2` → both edges on the −xAxis side: a band spanning
  [−0.25, −0.2] (width2's negative sign flips its edge across).
- **Keep a non-zero gap between the two extents.** `width2 = −width` exactly puts the
  two edges on top of each other, giving a zero-area outline: the operation is refused
  with `addedWithoutIssues: false` and *"Geometry of plate <name> is not valid - plate area is
  zero."*. Use e.g. `width: 0.2, width2: -0.19`.
- **A rectangular plate needs BOTH `width` and `height` non-zero.** Leave either out (or
  send zero) and the operation is refused the same way — *"Geometry of plate <name> is not valid
  - plate area is zero."* — so read `addedWithoutIssues` rather than assuming a default
  fills in.
- width2/height2 don't apply to circle/polygon; radius ignored for rectangular. No taper
  is produced.
- **Send a positive `thickness` in metres** — 0 or a negative value is accepted with
  `addedWithoutIssues: true`.

## The integrated `weld` block works with only TWO positionings

> **Being accepted is not the same as welding.** Passing this 422 gate only means the
> operation HAS a host plate to weld to; whether a weld actually materializes depends on
> the plate's geometry — its edge must lie ON the host surface, not penetrate it.
> A rib with `height2: 0.02` instead of `0` is accepted, stored, and welds nothing.
> Read `welds.md` ("the geometry decides") before sizing the plate, and prefer the
> `plate-cut` route for anything non-trivial.

A stiffening-plate's own `weld` field welds the new plate to the **host plate that the
positioning hands the operation** — and only `member` and `plateOnPlate` supply one.
Everything else is REJECTED with 422 before it reaches the model; an omitted positioning
defaults to `joint`, so it is refused too. Which positioning takes a weld: `field-matrix.md`.

Also 422 regardless of positioning: `plateType: "negative"` + a weld (*"a negative volume
is not welded"*). Sending `weld.type: "noWeld"` or omitting `weld` is always fine.

The 422 names both the cause and the remedy, e.g.:

```
Weld: positioning MemberLcs gives the operation no plate to weld to - so this weld would be
dropped without an error and the plate would be left unattached. Either position the plate
by Member or PlateOnPlate, or remove the weld and attach the plate with a separate weld
operation.
```

So for the common `memberLcs` plate: create it WITHOUT `weld`, then attach it with a
separate weld operation — or switch to `member` positioning if a rib/doubler on a member
face is what you actually want. Note the read side is symmetric: a plate persisted with a
weld it could never make does not echo that weld back, so an unmodified GET → PUT does not
trip this validation.

## Positioning modes (`conPlatePositioningType`)

### `memberLcs` — plate in the host member's local CSYS (the go-to mode)

`onMemberId` + `offset` (Point3D, host member's LOCAL axes) + `rotation` (Point3D:
x = in-plane spin about the normal, y/z = out-of-plane tilts). Default plate normal =
the member axis (a transverse plate, below); corner at the member's local origin.

**`onMemberId` is the only field you must send.** `inputMethod`, `normalVector`, `offset`
and `rotation` are all optional: omit them and you get a plate TRANSVERSE to the member
axis (normal ∥ the member axis) at the member origin, with `addedWithoutIssues: true`.
That transverse orientation is the default — with the default `inputMethod: "byAngles"`,
**`normalVector`'s VALUE is IGNORED** (even on a tilted member, (0,0,1), (1,0,0) and (0,1,0)
all give the identical plate). `inputMethod: "byNormalVector"` makes `normalVector`, in the
member's local axes, the plate normal, and `rotation` is then ignored.
Send `offset` to move the plate along the member's local axes and `rotation` to turn it.
So an end/base/splice plate needs only the member and an offset; the fuller block is
equally valid:

**Which of the plate's two in-plane directions is which does not follow the field names, and
on a transverse plate the pairing is the opposite of the obvious reading**: the `width` pair
runs along the host section's DEPTH and the `height` pair across its WIDTH. So on an I section
it is `width`/`width2` that must clear the flanges and `height`/`height2` the flange tips.
Sizing them the other way round builds a plate that is too short in one direction and too
long in the other — accepted without complaint, and visible only as walls that fail to weld
(`welds.md`) or fasteners that land off the plate. **Derive the mapping instead of assuming
it**: give the plate deliberately different extents in the two directions, read the outline
back from IOM and see which one grew. A grid mounted on the plate inherits this frame, so the
same pairing governs its positions.

```json
"positioning": {
  "conPlatePositioningType": "memberLcs", "onMemberId": 1,
  "inputMethod": "byAngles", "normalVector": {"x": 0, "y": 0, "z": 1},
  "offset": {"x": -0.2, "y": 0, "z": 0}, "rotation": {"x": 0, "y": 0, "z": 0}
}
```

Example: on a vertical column, offset.x runs ALONG the member axis from the joint, so the body
above gives a horizontal plate 0.2 m below the node.

### `coordinateSystem` — absolute placement

`coordinateSystem: {origin, xAxis, yAxis, zAxis}`. **`offset`/`rotation` are DEAD in
this mode** (consumed in memberLcs, nulled here) — move/orient via origin + axes only.
Predictable but brittle if the joint changes.

A weld-less `coordinateSystem` plate comes back `addedWithoutIssues: true` with no issues,
exactly like `memberLcs`, `joint` and `concreteBlock` — judge the outcome by the flag as
usual. Add a `weld` to it and you hit the ordinary 422 gate above instead.

### `concreteBlock` — plate on a face of an existing foundation block

Stands a stiffening plate on a face of the anchor-grid's foundation block — GUI *Origin =
Existing block*, then a *Concrete block* picker and a *Surface* number. Works over REST the
same way.

```json
"positioning": {
  "conPlatePositioningType": "concreteBlock",
  "concreteBlockIndex": 2,      // the OPERATION id that created the block
  "concreteSurface": 3,         // 1..6, a face of the block
  "positionX": 0.0, "positionY": 0.0,   // m, along the face's local x / y
  "rotationAngle": 0.0                  // rad, about the face normal
}
```
plus the usual plate `width/width2/height/height2/thickness`.

- **`concreteBlockIndex` is the id of the OPERATION that created the block** — i.e. the
  anchor-grid (or contact-grid) whose `foundationBlock` has `blockType: "new"`. It is **NOT** the block's
  IOM `id`, and **NOT** its name: IOM reports the block as `{id: 1, name: "CB 1"}`, yet only the
  operation id is accepted. Sending the name as the index → **400**; a `concreteBlockName` field
  does not exist. Any other value is refused with **422**, and the message lists the ids that
  are valid at that point: *"ConcreteBlockIndex 1 does not identify a concrete block. It takes
  the id of the operation that creates the block, not a block index. Operations before
  operation 7 that create a concrete block: 3, 5."* With a valid index the plates materialize
  on the block faces (visible in IOM and in the GUI).
- **The block must come from an EARLIER operation.** A plate can only stand on a block created
  before it, so a PUT moving an existing plate onto the block of a later grid is 422 (*"…
  a plate can only reference a block created by an earlier operation …"*) and the stored plate
  stays as it was. A plate on the block of an inactive grid is stored but not built: 200,
  `addedWithoutIssues: false`, *"Input data of concrete block are not valid."* — activate the
  grid.
- **`concreteSurface` is 1-based, valid 1..6** — 1 to 4 the sides, 5 the bottom and 6 the top of
  the block. A value outside that range is **422** naming the range: *"ConcreteSurface 7 is out of
  range. The concrete block created by operation 3 has surfaces 1 to 6."*
- **Discovering the index:** read the grids with `GET .../operations/anchor-grid` and
  `GET .../operations/contact-grid`; a grid whose `foundationBlock.blockType` is `new` creates a
  block, and its `id` is the value (a grid on an `existing` block, or a contact-grid without
  `foundationBlock`, creates none — `grids.md`).
  With several blocks, pick the grid whose `foundationBlock` you want. The 422 above lists the
  valid ids too.
- **Only `concreteBlockIndex`, `concreteSurface`, `positionX`, `positionY` and `rotationAngle`
  are read in this mode** — `function`, `location` and `inputMethod` are ignored. A typed GET
  still shows `function: rib`, `location: leftSide` and `inputMethod: byAngles` on positionings
  that do not read them: DTO defaults, not stored values. Do NOT send
  `onMemberOperationId` — the GUI-authored form leaves it null; the working REST body omits it.
- GUI note: if a concreteBlock plate in a desktop file shows "Input data of concrete block are
  not valid", re-selecting the same Surface in the GUI recomputes and clears it.

### `member` — rib/doubler/widener on a host member's plate

Host plate selected by **`plateOnMemberIndex` (REQUIRED, 1-BASED**, IOM wall order —
§ Placement below; GUI "Plate: Bottom flange 1" = 1). Omit it, or send 0 or a value past
the last host plate, and the operation is refused with `addedWithoutIssues: false` and
*"Input data of generally located plate are not valid."* NOT selected by
`plateIndex`/`plateEdgeIndex` (other modes' fields). Working minimal body:
`{conPlatePositioningType:"member", onMemberId, plateOnMemberIndex:1, function:"rib",
location:"leftSide", inputMethod:"byAngles", positionX}`.
- `positionX` slides along the member axis 1:1. **`positionY` is not read in this mode at
  all** — any value leaves the plate origin where it was — so place the plate across the member with `width`/`width2` (equal values centre
  it) rather than with `positionY`. `pitch` tilts a rib; a doubler ignores it. `function` takes rib/doubler/widener as for
  added members; `location: "bothSides"` builds TWO plates, one per side.
- Placement: `plateOnMemberIndex` counts the member's walls from 1 in IOM wall order (on an
  I-section 1 and 2 are the flanges, 3 the web). **`leftSide` / `rightSide` does not name a
  fixed face** — `rightSide` is the inner face of one flange and the outer face of the other.
  Read the plate's origin back from IOM and compare it with the flange's mid-plane before you
  weld or contact against it.
- **The weld type has to suit how the plate stands, or the model goes SINGULAR** — and the
  right choice is the OPPOSITE for the two cases. Both are load paths, not API quirks:
  - **FLAT on a member face (doubler): single-sided fillet (`filletFront`/`filletRear`),
    NEVER `doubleFillet`** — with nothing behind the plate the far-side weld shell floats.
  - **Standing on its edge (rib): two-sided — `doubleFillet` or `cjp`.** A one-sided weld
    (`filletFront`, `filletRear`, `pjp`) does not restrain the plate from rotating out of its
    plane. With a single rib: `doubleFillet` and `cjp` → `Analysis 100 %`; `filletFront`, `filletRear` and `pjp` →
    `Singularity`, `Welds 0.0 %`.

    **The rigid-body mode needs the welds to leave the rotation free, so it appears when the
    joint has a single edge weld — or several that all lie on ONE line.** Edge welds spread
    across a shape that is not a line restrain each other, and a one-sided weld then solves
    normally: e.g. three `filletFront` welds on the two flanges and the web of an I section
    give `Analysis 100 %`. What it costs is capacity, not stability — one-sided welds there
    reach a markedly higher weld utilisation than `doubleFillet`. So choose two-sided for a butted end because of the throat you get, and
    treat the singularity as the separate, sharper failure it is.
  In both cases the operation is accepted with `addedWithoutIssues: true` and an **empty
  `issues[]`**, and the weld is real and full-length in IOM — so neither the wrapper nor a
  weld count tells you. **Read the `Analysis` row, never `passed`**: it can say
  `passed: true` alongside `Analysis: Singularity`. Only `Analysis 100 %` means the parts
  are actually bonded. A 422 is not owed here — stability is not decidable from the request.
- Orientation follows the host plate: a `rib` stands **PERPENDICULAR** to the host wall, a
  `doubler` lies flat on its face (normal parallel to the face's), and a `widener` extends the
  wall in its own plane (coplanar, in the wall's mid-plane). So a vertical column DOES yield
  horizontal ribs: `plateOnMemberIndex` 1..3 with `location` leftSide/rightSide each give a
  horizontal rib on the corresponding flange or web face. For a differently-oriented host, re-derive from that
  host's axes; use `memberLcs` when you need an orientation none of the host faces offers.
- **`location: "center"` belongs to `function: "widener"`.** On a widener it centres the
  plate on the member axis at the node and `positionX` is not read — use `leftSide` or
  `rightSide` when you need to slide the plate along the axis with `positionX`. For `rib`
  and `doubler`, `center` is refused with HTTP 422: *"location 'Center' is not valid for
  function 'Rib'. Allowed locations: LeftSide, RightSide, BothSides."*

### `plateOnPlate` — stack a plate on another operation's plate

Name the host plate with `operationId` plus `plateIndex` (**1-based**). A `rib` or `doubler`
starts at the host plate's origin, moved by `positionX`/`positionY` along the host's x/y; only
a `widener` attaches to an edge (`plateEdgeIndex`).
- **`plateEdgeIndex` is consumed ONLY by `function:"widener"`** (the GUI shows the
  "Edge index" field only for Type=Widener); rib/doubler ignore it. It selects
  WHICH edge of the host plate the widener extends: **0-based on the wire, 1-based
  in the GUI** (GUI "2" ↔ wire `plateEdgeIndex: 1`); out-of-range clamps silently
  to the last valid edge.
- **Edge numbering: reliable = region-segment order ONLY on a plain rectangular
  host** (0-based; `export-iom-connection-data` `plates[].region` path segments;
  GUI shows the numbering 1-based — the editor can display edge numbers on the
  plate). On polygon or edited hosts the index order is not the outline order, and
  several indexes can map to one edge; out-of-range clamps silently. **For anything
  non-rectangular, decode empirically: post an index, verify the actual edge via
  IOM/scene, iterate.** A widener is anchored at the **start point** of the chosen edge,
  in the host plate's frame (`width`/`width2` along host x, `height`/`height2` along host
  y) — it is not aligned with the edge and not centred on it, on a horizontal and a vertical
  edge alike; read its outline from IOM and size it from there. The typed GET echoes `plateEdgeIndex` back but
  carries no edge GEOMETRY — for that, IOM is the channel, and the outline there is
  `plates[].geometry.outline` (startPoint + segments); `plates[].outlinePoints` reads back
  `null`. `plates[].region` is the legacy SVG string of the same outline. Vertices are
  plate-frame 2D on the MIDSURFACE; world = `origin + u·axisX + v·axisY`.
- **`location` = the side along the HOST PLATE'S NORMAL, and the GUI labels those same two
  values Front / Rear.** A rib and a doubler read it in opposite senses:
  - **Rib:** its origin (its edge) lies ON the host face — `leftSide` on the face against the
    host normal, `rightSide` on the face along it. Its body grows with `height` BACK THROUGH the
    host and with `height2` away from it, so size a standing rib with `height2`.
  - **Doubler:** lies flush on the face, but `leftSide` on the face ALONG the normal and
    `rightSide` on the face against it — the opposite of a rib.

  The displacement has no in-plane component, so the reference frame is
  the host plate's, never a global axis. Anyone matching the API against what they see on screen needs the Front/Rear naming.
- `location` on a plateOnPlate **widener** behaves differently from a rib/doubler: send
  `leftSide` or `rightSide`. `rightSide` flips which side of the edge's start point the
  height extends to (with `leftSide` on edge 0 the widener lies inside the host outline, with
  `rightSide` outside); neither shifts it along the edge — read the outline from IOM. `center` and
  `bothSides` are refused with HTTP 422 naming the allowed values, and nothing is written
  to the model.

### `joint` — fixed at origin

Places the plate at the global joint origin in the global XY plane, corner-anchored.
`positionX`, `positionY` and `rotationAngle` are ignored in this mode. `offset` and
`rotation` are read: the origin lands on exactly the vector you send in `offset`, and
`rotation` turns the frame (the same Point3D angle triple as in `memberLcs`).

## `shape:"polygon"` — `polygonData`

SVG-like path STRING: `"M x y L x y L x y Z"` — coordinates in METRES in the plate's
local xy, ≥3 vertices, non-self-intersecting, trailing **`Z` mandatory**. A string without
`M`/`Z` or an `"x,y;"` list is refused with 422 naming the expected format, and a JSON array
with 400. **Posting does not fully validate it**: a string that passes that check but is not a
valid path (e.g. `"M foo Z"`) is stored with 200 and `addedWithoutIssues: false`
(*"Object reference not set…"*) — read the flag. E.g.
`"M 0 0 L 0.18 0 L 0.09 0.18 Z"` → exactly that triangle. An outline with fewer than 3
distinct vertices, or a self-intersecting one, is refused with `addedWithoutIssues: false`
(self-intersection is named outright: *"Geometry of plate <name> is not valid - plate outline is
self intersected."*) — read the flag, acceptance of the string is not acceptance of the
geometry.
Coordinates are used as sent in every positioning mode — there is no x mirror for a polygon
(only a rectangle's `width` extends into −x); in `memberLcs` the plate's x runs along the
member's local z and its y along local y. Negative coordinates are fine.
- **ARC segments ARE supported on input**: `A rx ry rot large-arc sweep x y` inside
  the path materializes rounded corners/notches (the radii read back in the IOM
  region). So chamfered/filleted outlines are directly authorable.
- **A second closed subpath draws an opening.** `"M … Z M … Z"` puts the extra loop into IOM
  `plates[].geometry.openings` and into the IFC solid, and it survives a save and reopen.
  Whether the cost and the analysis see it depends on the plate: on an end plate both can, on a
  **doubler** (`member` positioning, `function: "doubler"`) the production cost ignores it and
  the stresses barely move. For a hole that must count, punch it with a `plate-cut` against a
  negative volume and confirm the production cost moves.
- **GUI-editor shape modifications live OUTSIDE the DTO**: a plate edited in the
  plate editor (chamfers, roundings, notches, holes) still echoes its ORIGINAL
  pristine `polygonData` — by design (the DTO is the operation DEFINITION); the
  true outline is in IOM `plates[].geometry.outline` (line and arc segments; `region` repeats it
  as an SVG path with `A` arcs). So you STILL can't
  read the edited outline from the typed DTO — read it from IOM. **GET→PUT of the
  unmodified body keeps the editor's edits** — outline, arcs, holes, chamfers and roundings,
  one corner or several per edit.
- **The typed GET returns the plate's `materialId`**, so a GET → PUT keeps its steel; a body
  you build without it gets the project's first steel (`operations.md`), and so does one sent
  with `materialId: 0` — it is stored as that steel's id and reads back as it. To give a plate a
  grade, send that grade's id.

> **To see a hole, read `plates[].geometry.openings` — not `region`.**
> `region` is the OUTER boundary only: a 300×300 plate with a Ø60 hole through it reads back
> as the same four-segment rectangle, one `M` loop, as a plate with no hole at all. The
> openings live in their own collection alongside it, one entry per hole.
>
> To confirm that material really went away, use a channel that carries the SOLID:
> - **`export-ifc` — the best one, because it carries names.** Count the faces of the
>   product's `IFCCLOSEDSHELL` **before and after** the operation: a hole adds one facet per
>   segment of its outline, so the count jumps. Always compare the same plate against itself —
>   the absolute number means nothing on its own (it depends on the outline: a polygon, an
>   arc or a chamfer all change it). `IFCPLATE('…',…,'PL')` ties the shell to the plate NAME,
>   which `presentations` does not.
> - **`presentations`** works too and is NOT anonymous: a plate group carries
>   `selected: {id, type: {kind: "plate"}}`. It is `selected.type` that holds only `kind` —
>   the id sits one level up. What the scene lacks is a NAME, so bridge through IOM
>   (`plates[].id` is the scene id, `plates[].name` the operation name). Note the id is unique
>   only within a kind — a weld and a plate can both be id 7. Face count jumps the same way, so
>   a before/after comparison works there too.
>
> Related: a **negative volume does not appear in IFC at all** — by design. It is a cutting
> tool, not a body: it contributes nothing to the FEM model, it exists so one volume can
> punch several parts, and only the resulting opening matters.
>
> **IOM lists it too — filter on `isNegativeObject`.** A negative plate gets its own
> `plates[]` entry with `isNegativeObject: true` (a structural plate reads `false`), and negative
> members appear in `beams[]` with the same field. Counting IOM entries without that filter counts
> cutting tools as material.

## negative-plate / `plateType:"negative"`

The same positionings and shapes as stiffening-plate, with three differences: it has no
`weld` and no `plateType` field, and the API does not check its function × location pairs
(send the pairs a stiffening plate allows — `field-matrix.md`). It is a CUTTING TOOL, not a
solid (see cuts.md — needs a follow-up `cut` with `plateOfOperation` + plateSubIndex 1;
dissects, keeps both sides). `plateType:"negative"` on a stiffening-plate behaves the
same.
