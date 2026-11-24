# Welds

Welds are readable from three channels, and **only one of them carries a weld's detail**:

| channel | what you get |
|---|---|
| `GET .../export-iom` (XML) | **the whole weld**: `<WeldData>` with `Name`, `WeldType`, `Thickness`, `Material` (`<Id>` = weld material, `0` = automatic), `IsIntermittent`, `ConnectedParts`, `Start`/`End`. A cut's welds are `WebWeld` / `FlangeWeld` inside `CutBeamByBeamData` instead, each with a `<WeldMaterial>` when its weld block names a welding material. Use it for anything about a weld's properties. |
| `GET .../export-iom-connection-data` | **counting only** — each entry is a bare `{"id": N}`, nothing else. Good for "how many welds", useless for "which kind". |
| `GET .../presentations/text` | the drawn geometry, one group per weld, tagged `selected: {id, type: {kind: "weld"}}`; the `id` matches the other two. |

**`ConnectedParts` is a list of `ReferenceElement` (`TypeName` + `Id`)**, e.g.
`{BeamData, 1}` + `{PlateData, 7}` — it is NOT a list of id strings; read `TypeName` + `Id` from each entry.

**This page owns TWO operations: `weld` and `contact`.** The GUI shows them as one dialog with
a `Type` dropdown; in the API they are unrelated endpoints (§"Contacts", below).

**Answers:** where a weld can exist at all (edge-on-surface) · the `edgeToEdge` recipe · edge
indexes · references &amp; placement (how to name the two sides) · base/transverse plate at a
member end · weld typology (the six wire values ↔ dialog labels) · **what `size` means per
type** (`0` on a `cjp` takes the plate thickness; `0` on a fillet makes the engine auto-design
it) · failure fingerprints · `contact`, including how it differs from `contact-grid`.

**Does NOT answer:** whether an *integrated* `weld` block inside a plate is accepted — that
gate is in `plates.md` §"The integrated `weld` block works with only TWO positionings"; for an
added member see `members.md` · which weld fields apply for a given `weld.type`/`kind`/`placement`
(the applies/required grid, not the meaning) → `field-matrix.md` · authoring a `contact-grid`
against a foundation block → `grids.md`.

## Read this before authoring any weld: the geometry decides, not the request

A weld is born where **an edge meets a surface**. Every `weld` block in the API is a
*request*; whether it materializes depends entirely on where the plate ended up. The two
integrated paths want OPPOSITE geometry, and getting this backwards is the single most
common way to spend an hour on "the API drops my welds":

| path | required geometry | typical use |
|---|---|---|
| `stiffening-plate` + `weld` | the plate edge lies **ON** the host surface — it must NOT penetrate and must not stand off | a simple rib on a flat face |
| `plate-cut` + `weld` | the plate **deliberately COLLIDES** with the host; the cut trims it and the weld is born on the cut edge | complex joints, skewed members — **the practical default** |

**The shortest recipe that produces a real weld or contact** (use it whenever you need one
to test against): a `member`-positioned rib already lands
its edge on the member's wall, so the geometry is right by construction.

```
member  COL, HEB200, position {definedBy:"rotationsOfX", gamaPitch:π/2, betaDirection:0, alphaRotation:0}
plate   stiffening-plate, thickness 0.01, width=width2=0.05, height 0.08,
        positioning {conPlatePositioningType:"member", onMemberId:COL, plateOnMemberIndex:1,
                     function:"rib", location:"leftSide", inputMethod:"byAngles", positionX:0}
join    weld (or contact): placement "edgeToSurface",
        first  {operationId:<the rib's>, plateSubIndex:1}   <- the PLATE
        second {memberId:COL, plateSubIndex:0}              <- the WALL it stands on
        firstPlateEdgeIndex [1], secondPlateEdgeIndex 1
```

**Operand order is not symmetric — the first operand is the part whose EDGE meets the second's
surface.** For a rib on a wall that is the rib (plate-then-wall succeeds, wall-then-plate is
refused with *"There is no parallel edge on the second plate which could welded to the selected
edge."*); for a wall butting onto a plate face it is the wall (§ Base/transverse plate). A
failure with that message may be operand order, not geometry.

- **A rib whose edge penetrates the surface makes no weld** — it comes back with the warning
  below instead. A zero `width2`/`height2` is the EASIEST way to put the edge exactly on the
  surface, not the only one: offset, size or rotation reach the same place. State the condition
  as "edge on the surface", never as "some dimension must be zero".
- **For anything non-trivial, prefer `plate-cut`.** Let the plate run into the member, then cut
  it — a plate that on its own makes no weld yields many once cut, one per resulting edge on a
  surface. This is also how the GUI builds real joints.
- An operation that requested a weld and produced none returns
  `addedWithoutIssues: false` with a `warning`: *"A weld was requested for the plate but
  no weld was created - the plate does not touch the welded part, or the contact is not a
  supported weld geometry (e.g. a flat plate against a curved wall). Review the plate position
  and the welded part."* The issue's `description` is the **operation's own name**, not a
  generic label, so it is the one place that says WHICH operation the warning is about — read
  `details` for the sentence and `description` for the target. It discriminates, but **only
  about the model as it stands at that call**, and it is **silent for two positionings and for
  negative plates**. Both limits bite in practice:
  - **It expires and nothing retracts it.** The check is a sweep over the FINISHED model, so
    a plate that nothing welds yet warns correctly at step N — and a later `plate-cut` that
    welds it clears the warning *in the rebuilt model*, but the response to that later
    operation is filtered to the later operation and says nothing about N. A client that
    stored `addedWithoutIssues: false` and never re-read is holding an expired verdict.
    **Re-read the operation before treating the warning as final.** This is the response-side
    view of "a plate that on its own makes no weld yields many once cut", above.
  - **No warning at all for `joint` or `coordinateSystem` plates, or for negative plates** —
    their weld request is not evaluated, so for those the *absence* of the warning means
    nothing. Verify in IOM `welds[]` instead. `memberLcs` and `concreteBlock` plates ARE
    evaluated; that matters for a model from the desktop, since the API refuses a weld block on
    them (next bullet).
- **An integrated `weld` block is only accepted for `member` and `plateOnPlate` positioning**
  (`memberLcs`, `joint`, `coordinateSystem`, `concreteBlock` → 422 before the model sees it).
  Full rule, the 422 text and the remedy: `plates.md` § "The integrated `weld` block works
  with only TWO positionings".
- **The standalone `weld` operation is the LAST resort** — it needs the edges to line up
  by itself and fails with "There is no parallel edge…" when they don't. See "References
  & placement" below.

## Contacts — the GUI's one dialog is TWO API endpoints, and they are unrelated

The desktop has a single *"General weld or contact"* panel whose `Type` drops down to
**Weld | Contact**, and a separate *"Fastener grid or Contact"* panel whose `Fastener`
drops down to **Bolts | Pin | Anchors | Contact**. In the API these are different things:

| GUI | API endpoint | what it joins |
|---|---|---|
| Weld or contact, `Type: Contact` | **`contact`** | an edge to an edge or a surface, exactly like `weld` |
| Fastener grid or Contact, `Fastener: Contact` | **`contact-grid`** | a plate face to a **concrete block**, or — without `foundationBlock` — a plate-to-plate contact |

The weld types you can author are `noWeld`, `filletFront`, `filletRear`, `doubleFillet`,
`cjp` and `pjp` — there is no `contact` value, so a contact cannot be made through `weld`:
`weld.type: "contact"` is HTTP 400 (*"Error converting value \"contact\" to type …"*). Use the
`contact` endpoint; its body is the weld body minus the `weld` block.

**A contact IS observable — in `export-iom` and nowhere else.** It rides in the weld
collection (there is no separate contact collection) as a `<WeldData>` whose **`WeldType` is
`Contact`** — IOM's own spelling, capitalised, like `Bevel` and `DoubleFillet`; not the
lowercase `contact` of a REST enum. Its `Thickness` is the **thinner of the two parts** it
joins, not a weld size you sent. A contact made in the desktop may carry another value there, and a
PUT replaces it with the thinner part's thickness; only the cost estimate reads it.

E.g. a `weld` and a `contact` on two ribs of the same column:

```
Id=3  Name='W1'  WeldType=DoubleFillet  Thickness=0.005   <- the weld, size as sent
Id=4  Name='C1'  WeldType=Contact       Thickness=0.01    <- the contact, = the thinner part (the 10 mm rib)
```

The other two channels cannot tell them apart: `export-iom-connection-data` gives each as a
bare `{"id": N}` (the swagger's `WeldData` there declares `id` and nothing else), and the 3D
scene tags both `kind: "weld"`. So count in either, but **identify only in `export-iom`**.

**A member wall works as either operand.** The GUI shows them as `C` and
`C | Bottom flange 1`, which hides that the first one also carries a sub-index. A
GUI-authored contact that DOES materialize stores this — note `secondPlateEdgeIndex` is
present even for `edgeToSurface`, where the GUI does not display the field:

```json
{ "placement": "edgeToSurface",
  "firstMemberOrPlate":  {"memberId": 2, "plateSubIndex": 1},
  "firstPlateEdgeIndex": [1],
  "secondMemberOrPlate": {"memberId": 1, "plateSubIndex": 1},
  "secondPlateEdgeIndex": 1 }
```

**But copying that shape is not enough — the geometry still decides** (same rule as for
welds, above). Replayed on two members with no prior cut it gives *"There is no parallel edge on the
second plate…"* and zero contacts; in a desktop model it works because a `cut` runs FIRST
and creates the abutting edges. Build the geometry, then the contact.

The issue string tells you which half is wrong (the full list: `operations.md` § Typical
`issues[].details`): *"No plate is selected."* is an empty first operand; *"There is no
parallel edge on the second plate…"* is a second operand that is empty, bare or out of range,
or a **geometry** that offers no pairable edge — check the operand first, then fix the model.

An operation that returns `addedWithoutIssues: true` with **zero** contacts in IOM is the
third outcome — reference resolved, engine attempted nothing, no complaint. Always count
from `welds[]`.

**`contact-grid` joins faces, `contact` joins an edge to an edge or a surface.** A
`contact-grid` with or without a concrete block: `grids.md` § "contact-grid / contact /
pin-grid". Use the `contact` operation for an edge bearing on a plate, as in the table above.

## Working `edgeToEdge` recipe

```json
{ "placement": "edgeToEdge",
  "firstMemberOrPlate":  {"operationId": A, "plateSubIndex": 1},
  "secondMemberOrPlate": {"operationId": B, "plateSubIndex": 1},
  "firstPlateEdgeIndex": [1], "secondPlateEdgeIndex": 1,
  "weld": {"kind": "continuous", "type": "cjp", "size": 0.0, "materialId": <weldMat>},
  "name": "W1", "active": true }
```

## Edge indexes — candidate edges, not polygon segments

- A background algorithm finds the connectable (touching/colinear) edge pairs itself;
  `firstPlateEdgeIndex`/`secondPlateEdgeIndex` are **1-based indexes into those found
  CANDIDATES** (GUI "Local edge index"). Two plates touching along a SINGLE straight
  segment have one candidate → value 1 on both sides; segmented/colinear contacts expose
  SEVERAL candidates (see below) where one or two combos give the real full-contact weld.
- Wire asymmetry (per swagger, intended): `firstPlateEdgeIndex` is an ARRAY of integers,
  `secondPlateEdgeIndex` a single integer — **sending an array for the second → HTTP 400**.
- **Edge-index outcomes split three ways — judge them by the IOM weld count, never by
  the success flag alone.** A valid pair welds. On `edgeToEdge` an out-of-range or zero
  `secondPlateEdgeIndex`, or omitting it, is refused with an error and no weld; on
  `edgeToSurface` the second index is not read (any value gives the same weld). Omitting
  `firstPlateEdgeIndex` (or sending it empty, or `[0]`) is accepted silently and welds
  nothing; an out-of-range value inside it is accepted with an `info` issue and welds
  nothing. Plates that do not actually touch are refused with "There is no parallel
  edge…" whatever the indexes. Explicit `null` → HTTP 400. Always read `welds[]` and
  check the spans.
- **Indexes NEVER select a subset of the contact**: every VALID combo welds the ENTIRE
  shared contact (e.g. a plate whose edge has two colinear segments), materializing one IOM weld per colinear
  segment from the single operation (2 welds covering [0,0.2]+[0.2,0.4]). The index
  pair only validates the candidate pairing.
- **Combos MISBEHAVE, the same way on axis-aligned and tilted geometry:** per geometry, one or two combos produce the REAL
  full-contact weld; some combos return `addedWithoutIssues: true` but
  materialize a **ZERO-LENGTH weld** (IOM `start == end`, a degenerate corner point
  that still enters the model and can silently kill calculate); the rest are
  refused (`addedWithoutIssues: false` with an issue). The trap is one-directional: `true` does NOT
  mean a valid weld.
- **IRON CHECK for every weld: read IOM `welds[]` and verify the spans —
  `Σ dist(start, end)` ≈ the intended contact length** — existence and type are not
  enough. Iterate index combos until the spans are right.

## Weld material

**Set `materialId` in the weld block** — a welding material of the project
(`.../materials/welding`). Every operation that carries a weld writes it (`weld`, `cut`,
`plate-cut`, `stiffening-member`, `stiffening-plate`, an anchor grid's shear lug), its typed GET returns it, and an unmodified
GET → PUT keeps it. To set all existing operations at once use `common-properties`
`weldMaterialId`. Confirm per weld in `export-iom`: `<WeldData><Material><Id>` (`0` = automatic),
or `<WeldMaterial>` under a cut's `WebWeld`/`FlangeWeld` (absent when the cut's weld material is
automatic); the id points into the `<MatWelding>` list.

## References & placement

- **Qualify every operand.** A MEMBER reference must carry `plateSubIndex` (0 is valid):
  `{"memberId": 1, "plateSubIndex": 0}`; what a bare one does: `operations.md` § ConConnectedItem.
  A plate-by-operation reference works either way: `{"operationId": N, "plateSubIndex": 1}`
  or just `{"operationId": N}`.
- A standalone weld requires the edges to genuinely line up — otherwise "There is no
  parallel edge on the second plate...". **Prefer the host operation's own `weld`
  field** (`stiffening-plate`, `stiffening-member`, `cut` websWeld/flangesWeld,
  `plate-cut`) — the integrated weld attaches without geometric edge matching and takes its
  material from the same block (§ Weld material).
- All-CHS joints have no plate edges: a standalone weld throws "Object reference not
  set..." — weld cut tube members via the cut's websWeld/flangesWeld.

## Base/transverse plate to a member end (foot of a column on a base plate)

Welding the walls of a member that BUTTS onto the face of a transverse plate (its end
sits flush on the plate, no penetration) — e.g. a base plate under a column, an end
plate.

**First get the plate onto the right side of the node, because "flush" is what makes the
welds possible.** A joint member occupies only ONE side of the node along its own axis, and
which side is not something to assume — it follows from `connectedBy` together with the sign
of the pitch, so the same angle can put the material either way. Derive it instead: project
the member's walls (IOM `beams[].plates`, `origin + u·axisX + v·axisY`) onto the member axis
and see which side of zero they occupy. The plate's mid-plane then belongs **half its own
thickness beyond the last section, on the empty side** — closer and it buries itself in the
member, further and there is nothing to weld to.

Getting this wrong is silent in every API channel: the operation reports success, the plate
is in IOM and in the scene, and `calculate` can still return `Analysis 100 %`. What does move
is the weld count — so **treat "the walls welded" as the test that the plate landed right**,
and read it back per wall.

**Size the plate against the section it sits on, not against a nominal outline.** A wall
welds only where the plate actually reaches under it, and the reach needed is to the wall's
MID-SURFACE (half a flange thickness inside the section's outer fibre), not to its outer face.
An undersized plate welds the walls it covers and silently skips the rest — a partial result
that looks like a per-wall failure rather than a plate that is too small.

To give each wall its own throat (flanges one size, web another), weld each wall
as a separate operation:
- Use **`edgeToSurface` with `firstPlateEdgeIndex:[1]`** — the wall edge onto the plate
  FACE. This needs NO colinear edge on the plate, so it works whatever the plate's size
  or in-plane rotation. Reference each wall by `{memberId, plateSubIndex}` (flanges and
  web are separate subIndexes), plate by `{operationId, plateSubIndex:1}`.
- **`edgeToSurface` WITHOUT `firstPlateEdgeIndex` is a silent no-op** (200, zero welds).
- **`edgeToEdge` is brittle here:** it only pairs when a wall edge happens to be colinear
  with a plate outline edge. The moment the plate is resized/rotated so the wall edge
  falls INSIDE the plate outline, it returns "There is no parallel edge…" and no weld.
  Prefer edgeToSurface+firstPlateEdgeIndex for butt-on-face welds.
- **A cut BY the plate welds only where the member end reaches INTO the plate** — put the
  plate's mid-plane at the member end. On a flush end, or a plate placed below the end with a
  gap, the cut adds no weld (with `extendMember: true` too) and still reports success; weld a
  flush end with `edgeToSurface` as above. Count the welds in the scene (SKILL.md rule 4).

## Weld typology (engineering semantics ↔ wire values)

The six wire values match the desktop's own list, and all six are available over the API under
every design code:

| wire value | dialog label |
|---|---|
| `filletFront` | Fillet A |
| `filletRear` | Fillet B |
| `doubleFillet` | Double fillet |
| `cjp` | Butt |
| `pjp` | PJP |
| `noWeld` | No weld |

**A `doubleFillet` is checked TWICE — once per leg — and that doubles its result rows.**

| type sent | rows per weld in `checkResWeld` *and* in detailed `welds` | stored in IOM as |
|---|---|---|
| `doubleFillet` | **2** | `doubleFillet` |
| `filletFront` / `filletRear` | 1 | `fillet` or `filletRear` — the engine picks the side per geometry |
| `cjp` | 1 | `bevel` |
| `pjp` | 1 | `pjp` or `pjpRear` |

The two rows of a double fillet share the **same weld id** — one carries the plate name, the
other `name: ""` — with slightly different `unityCheck` (typically a fraction of a percent apart). So a row count
from the results is not a weld count, and "the" utilisation of a weld is the max over its rows.
IOM `welds[]` stays one entry per weld either way; count there.

- `cjp` — complete-joint-penetration groove weld carrying base-material capacity, so
  **leaving `size: 0` is correct** and is never reported as a missing value. Zero asks the
  engine to design the size (see `field-matrix.md` § `weld.type` — this is true of every type,
  not just CJP); for a CJP it resolves to the plate thickness. A non-zero `size` is stored
  verbatim if you need to state a dimension explicitly. The GUI shows no dimension for a CJP
  either way. In `export-iom` it reads `<WeldType>Bevel</WeldType>` — IOM's capitalised
  vocabulary, not the REST spelling.
- `pjp` — partial-penetration groove weld. **`size` is carried through unchanged**: IOM
  `thickness` equals the value you sent, exactly as for a fillet — so the same `size` does not
  buy a different dimension by switching type. What differs is the assessment: a `pjp`
  utilisation is not a constant multiple of the fillet's at equal dimension, so `pjp` is
  checked by its own rules rather than as a rescaled fillet.
  **`pjp` is accepted and analysed under every design code the API offers**, including the
  ones whose desktop dialog does not list it: the analysis runs and the weld is checked,
  with a code-specific utilisation for identical geometry. Create the project with the
  `countryCode` you want; the steel library that comes back confirms which code is in
  force. Where the desktop does not offer PJP the engine still produces a check; the clause
  it applies is not documented, so confirm the number against that code's standard before
  relying on it.
- **Rear-side PJP cannot be requested, only observed.** `pjpRear` is not in the enum and
  sending it returns HTTP 400. On read the engine labels the two sides of one weld set
  separately — a `pjp` request comes back as `pjp` plus `pjpRear`, a `filletFront` request
  as `fillet` plus `filletRear` — but that label is the engine's own, not a value you
  chose. Match on the base name to group the two sides.
- `filletFront`/`filletRear` — single-sided fillet (side taken along the welded edge
  direction, GUI right/left); `doubleFillet` — both sides. Fillets are laid from the
  side of the plate; **GUI fillet size maps 1:1 to wire `size`** (10 mm → 0.01).
- **`size: 0` on a fillet weld = engine AUTO-DESIGNS the size** (e.g. a 0-size filletFront
  on a 10 mm plate → IOM thickness 0.01 on POST, calculates to 100 %). Only
  `type:"noWeld"` / omitting the block means no weld.
- **Plate flat on a member face: single-sided fillet only** — `doubleFillet` builds a
  floating far-side weld → model singularity (with the `passed:true` +
  `Analysis: Singularity` flag contradiction). Details: plates.md.
- In `export-iom`, `<WeldData><WeldType>` is a NAMED enum string (no raw integers), so
  name-based parsers are safe. The stitch character is a SEPARATE element,
  **`<IsIntermittent>`**, not folded into `<WeldType>`: a stitch weld reads e.g.
  `<WeldType>DoubleFillet</WeldType>` + `<IsIntermittent>true</IsIntermittent>`, a continuous one
  the same type with `false`. To detect stitch welds, read `<IsIntermittent>`, not
  `<WeldType>`.

## Stitched welds

- **Stitch a weld with a `weld` operation.** Only the `weld` operation lays a weld in stitches;
  a cut's, plate-cut's, plate's, added member's or shear lug's weld block with `kind: "intermittent"` (a
  partial weld included) is refused with 422 naming the block — *"WebsWeld: kind intermittent
  is available only on a weld operation. … Send kind continuous, or set type to noWeld here and
  add the stitches as a separate weld operation."* Which fields each `kind` reads:
  `field-matrix.md` § by `weld.kind`.
- **Stitch fillet and `pjp` welds; send a `cjp` as `kind: "continuous"`.** A `cjp` sent with
  `intermittent` is stored and echoed with its length and gap but built as the full continuous
  CJP (`export-iom`: `<WeldType>Bevel</WeldType>`, `<IsIntermittent>false</IsIntermittent>`).
- A partial weld is `intermittent` with `length: 0` and the two offsets. A `continuous` weld
  reads `length`, `gap` and the offsets back as 0.
- `export-iom` carries no stitch length or gap — its start and end are the whole edge. Read the
  stitches back from the typed GET.

## Failure fingerprints

- **Duplicate welds STACK silently** — posting the same weld twice → TWO overlapping
  welds (IOM count grows), double-counting weld strength in CBFEM. Deduplicate
  client-side; never re-post "to be sure".
- **GUI display caveat**: a REST-authored weld shows in the GUI dialog as CJP with no
  dimension even when the stored type is a fillet — typed GET and IOM read back
  correctly; trust those, not the dialog.
- A dangling/invalid weld is a known trigger of a calculate failure (200 + `passed: false`),
  as is a fan of many welds meeting in one shared vertex. Read the failure's `resultSummary`
  row and look it up in `diagnostics.md` — a generic message there points back at the welds,
  so bisect them first.
