# Cuts, work planes, negative volumes

`member` = what gets cut; `cutBy` = the tool. Judge every cut by VOIDS/CUT FACES in the
presentation scene (or part counts), never by bbox — the modeled shell length re-extends
1.25 × section height from the new cut face, so bboxes move for unrelated reasons.
**Test PRE/POST**: first model target + tool WITHOUT the cut and verify they actually
overlap (bbox screen + visual — an I-shaped tool can bbox-overlap while the target
passes between its flanges), then add the cut and diff.

**FOUR different operations live on this page**, and the first six headings below are named
after *fields of `cut`* — not after the operation you may be authoring:

| operation | starts at heading | note |
|---|---|---|
| `cut` (member cut) | `## cuttingMethod`, immediately below | the six field-named sections all describe THIS one: `cuttingMethod`, `direction` (`parallel`/`perpendicular`), `offset`, `extendMember`, `cutBy.kind`, `member.remainingPart` |
| `work-plane` | `## work-plane` | its `offsetX`, `origin`, `normalVector` are a different object's fields |
| `plate-cut` | `## plate-cut` | **has its own `cuttingMethod` with only 2 of the 4 values valid**, and its own `remainingPart` meaning (a plate side, not `begin`/`end`) |
| negative volumes | `## negative volumes` | `negative-plate` / `negative-member` need a follow-up `cut` to remove anything |

So if you are authoring a **plate-cut**, the values under `## cuttingMethod` are the wrong
set — go to `## plate-cut`, which is where the accepted set and its behaviour are stated (this
table only routes; `field-matrix.md` carries the same split as an applies/required grid).
Hollow sections (CHS/RHS) have their own consolidated path in the last section.

**Does NOT answer:** plate shape and positioning → `plates.md` · added-member geometry used as
a cutting tool → `members.md` · which fields apply per `cutBy.kind` → `field-matrix.md`.

## `cuttingMethod`

- `surface` — trims the member exactly to the tool's REAL surface (mm-exact to the
  facing flange; CHS-CHS produces the saddle). The workhorse.
- `boundingBox` — flat cut at the tool's bounding envelope. `cuttingPlane` works here
  (and ONLY here): `closer` cuts at the tool's near face, `farther` at its far face.
  Send `cuttingPlane` with `boundingBox` only; `surface` does not read it (the GUI does not
  offer it there either).
- `surfaceAllAround` — dissects the member at EVERY intersection with the tool's
  plates: pieces inside solid walls removed, pieces in interior voids SURVIVE as
  separate parts. The ONLY method that engages on a continuous/through member (punches the
  tool's cross-section through it).

  **Do not quote a piece count — derive it.** What the dissection leaves is a function of how
  deep the member has penetrated AND of the angle it meets the section at, so a piece count
  from one model does not transfer to another; the same joint passes through several distinct
  states from first contact to fully through, and different ones at different angles.

  **How to read it, in three channels of decreasing usefulness:**

  1. **Scene, by bounding box — the only one that shows the actual dissection.** Weld the
     duplicate vertices by position (the scene stores each triangle's corners separately),
     take connected components within a single `kind: "member"` group, and print each
     component's extents. An uncut member gives one component per wall, each spanning the full
     length; a dissected one shows fragments, e.g. a flange split into two strips with a gap
     exactly where the tool's web passed through. **The component COUNT alone proves nothing**
     — an untouched member already reads as one component per wall.
  2. **IOM `beams[].plates` for that member — a cheap "did it engage" signal.** The outline
     count moves when the cut bites (and the weld count moves one step earlier, when the
     members merely touch). But these are WALLS, not pieces: IOM is a design-intent model, and
     IOM's `ConnectionData` contract stores `CutBeamByBeamData` as
     `{Name, ModifiedObject, CuttingObject, Method, Offset, IsWeld}` — the cut's recipe, never
     its result.
  3. **IFC — solids, but not separable.** It does carry `IFCFACETEDBREP` + `IFCCLOSEDSHELL`,
     yet the member stays one `IFCBEAM` with one closed shell however deeply it is cut; only
     the file grows. Useless for counting, useful for telling a cutting tool from a body.

  **Sweeping a joint to find where behaviour changes** — how to make any of this
  measurable:
  - Slide the member along its own axis with `position.offsetEx`, and **start at the tangent
    position**, not at the member's origin: the middle of the travel is a wide plateau where
    nothing changes, and a sweep confined to it reads every step as identical.
  - **Find the tangent from IOM, remembering walls are MID-SURFACES**: the face a member first
    touches is `mid-surface ± thickness/2`. Anchoring on the mid-surface starts you half a
    flange thickness already inside it.
  - For a member at an angle, `offsetEx` runs along ITS axis, so crossing a section of depth
    `d` needs `d / cos α` of travel, plus the member's own profile depth projected onto the
    path. Budget roughly `(d + profile depth · cos α) / cos α` and confirm both ends with a
    no-contact reading.
  - At the tangent the cut is a no-op that still answers `addedWithoutIssues: true` — a clean
    success with the member untouched, so read geometry, not the wrapper.

  **`cuttingPlane` and `extendMember` are stored but do not change the RESULT here.**
  The GUI panel for this method offers neither. Both are stored on the operation regardless of
  method and the typed GET echoes them back, but every combination of `closer`/`farther` ×
  `true`/`false` yields identical geometry with this method. A stored, echoed value is not proof
  that it acts — only a geometry diff decides.
- `mitreCut` — cuts a CORNER joint of two ENDED (non-continuous) members on the mitre plane, and
  **one cut trims both** `member` and `cutBy`. Three rules decide the result:
  1. **Pairing.** Between two ADDED members set each one's `remainingPart` to the END that meets
     the corner — the value names the end that is cut off (`## member.remainingPart`): `end` on the
     member whose `length2` tip meets the corner, `begin` on the one whose `length1` tip meets it. Example — A runs into the corner, B
     leaves it: `member: {kind: stiffeningMember, operationId: A, remainingPart: end}`,
     `cutBy: {kind: stiffeningMember, operationId: B, remainingPart: begin}`. A closed ring of N
     pieces takes N cuts, piece i by piece i+1. This pairing holds for any section, orientation and
     angle; **any other pairing is accepted and builds the wrong part** (the mislabelled member
     keeps only the fragment past the plane, the other is trimmed short), so check both labels
     before the POST.
  2. **Reach.** Each member must reach back from the corner further than `(h/2) / tan(θ/2)` — `h`
     the section's depth in the plane of the corner, `θ` the angle between the two members (a
     114 mm tube at θ = 10° needs 0.65 m, an HEB200 standing in that plane at θ = 30° needs
     0.37 m). Below it the mitre plane would run along the member, and the cut is refused with
     HTTP 200, `addedWithoutIssues: false` and *"Cutting along a beam is not allowed."* —
     lengthen the member. The same message also answers a wrong pairing on a nearly straight
     joint.
  3. **Plane.** The mitre plane bisects the two member axes and passes through their
     intersection — so place the axes to meet where the mitre should be: shifting one member
     within the corner plane moves the cut with the intersection. A member shifted across the
     corner plane, so that the axes pass each other, is cut by the plane of their projection —
     also when the two members do not touch at all, and without any warning.

  Confirm the result by the end faces in the scene. On a T-joint part of the beam crosses the
  column axis.

## `direction` — `parallel` vs `perpendicular`

Matters only when the tool/plane is NOT normal to the member (e.g. a 45° work-plane):
`parallel` cuts ALONG the plane (slanted end face), `perpendicular` cuts
normal to the member's axis at the first intersection. Normal plane → identical.

## `offset` (m)

- Positive = moves the cut face AWAY from the tool (clean gap). The offset follows the
  tool's REAL tessellated surface — on a profiled tool the face comes out stepped/jagged
  (GUI does the same). For a clean flat cut at a distance use work-plane + cut.offset,
  or boundingBox.
- **A negative offset with `surface` pushes the member INTO the tool only up to half the tool's
  thickness.** Past that the end face mirrors about the tool's mid-plane. E.g. on a column cut
  by a 30 mm base plate, −0.010 ends the column 10 mm into the plate, −0.050 ends it 20 mm ABOVE it
  with the welds bridging the gap, and at exactly −0.015 nothing is cut while the response still
  reports success. Keep a negative offset below half the tool's thickness.
- boundingBox offset works BOTH directions (negative pushes the member INTO the tool).

## `extendMember` (bool)

When `true`, the cut member is first EXTENDED to reach the cutting object before it is
trimmed (so a member that stops short of the tool is stretched to it, then cut). `false`
(default) cuts only where the member already reaches the tool. The field lives on the `cut`
operation body. Judge the result by cut faces/parts, not bbox (the extend changes length by
design).

**It works on a work-plane cut.** With a slanted plane the member is **pulled out to the plane
where it fell short of it** — the near fibre meets the plane before the far one, and extend
closes that gap instead of ending the member at the first material, so a clipped corner
becomes one slanted face. **Extend needs something to pull** — no gap between member and tool,
nothing to do.

**Do NOT confuse it with the automatic prolongation.** The far end (unchanged by the flag)
comes from the model prolonging a member past its last MODIFYING operation — see
*"Member length is NOT yours to read"* in members.md. Reading that end as extend's doing is
exactly the misreading to avoid.

## `cutBy.kind` coverage

- WORKING: `member`, `workPlane` (trims exactly at the plane — provided the plane actually
  intersects the member; see the work-plane section),
  `negativeVolumeMember` (true boolean subtraction — removes the segment inside the
  volume, keeps BOTH outer stubs), `stiffeningMember` — which keeps the side away from the
  joint, where member forces are applied, and differs from the other tools in two ways:
  `cuttingPlane:"closer"` acts at the tool's FARTHER face (inverted/ignored for this
  tool kind), and the member does NOT re-extend by the modeled shell length after
  this cut (unlike every other cut).
- Plate-family `cutBy` kinds need **`plateSubIndex`**; omitting it or sending `0` is refused
  with HTTP 422 naming the field. **The base differs by kind:**
  - `plateOfOperation`: 1-based — send `1` for the operation's first sub-plate.
  - `memberPlate`: the value is read as a **0-based wall index**, so `1` selects the member's
    SECOND wall and **the first wall cannot be selected at all**. A member with n walls takes
    `1`..`n-1` (an I section: `1` = the second flange, `2` = the web, in IOM `beams[].plates`
    order; a box: `1`..`3`); `n` is the out-of-range case below. To cut by the first wall, cut
    by the whole `member` or by a work plane on that wall. `stiffeningMemberPlate`,
    `negativeVolumeMemberPlate` and `stubMemberPlate` are expected to follow the same rule —
    verify before relying on them.
  An index past the plate's last sub-plate returns 200 with an error issue ("Some
  required member is not specified correctly.") and **the cut is stored all the same**, so
  check `addedWithoutIssues` as well as the status, and correct it with a PUT on its `id` — a
  corrected POST without that `id` adds a second cut.
- Cut by a PLATE **dissects, it does not trim**: removes the slice inside the plate's
  thickness, keeps both outer pieces. For a trim, use a work-plane.
- `cutBy:{kind:"plate", plateId}` resolves an internal plate id and cuts when the id
  exists. An id that does not resolve returns HTTP 200 with `addedWithoutIssues:false`
  and an error issue ("Some required member is not specified correctly."), and the cut is
  stored all the same — read the issues, not just the status, and fix it with a PUT on its `id`.
- `cutBy:{kind:"stubMember"}` needs the `operationId` of an existing stub operation.
  Without it, or pointing at an operation that does not exist, the request is refused
  with HTTP 422 and a message naming the missing field or the unknown operation id.
- `negativeVolumeMemberPlate` does not resolve a negative-plate ("Some required member is
  not specified correctly").

## `member.remainingPart` (`begin`|`end`)

Acts only for `stiffeningMember` targets (an added member; `negativeVolumeMember` and
`stubMember` targets ignore it) cut by a PLANE — a work plane, or the mitre plane of a
`mitreCut`: on `{kind:"stiffeningMember",
operationId}` it selects which half survives (e.g. a stiffener spanning ±0.3 cut by a plane at
x=+0.1: `begin` keeps [0.1..0.3], `end` keeps [−0.3..0.1]). **Read the value as the end
that is CUT OFF**: `begin` cuts off the member's `length1` end and keeps the `length2` side, `end`
cuts off the `length2` end. The desktop shows the same stored value under its own label *Cut off
part*; only the API field name `remainingPart` reads the other way. **To keep the part between two
planes, give each cut the end on its own outer side**: `begin` at the plane nearer the `length1`
end, `end` at the plane nearer the `length2` end — that keeps the middle in either order of the
cuts. Any other pair of values gives a result that depends on which cut comes first; read the
survivor back. `mitreCut` also reads `cutBy.remainingPart`, with the same labels, for a
`stiffeningMember` tool (above). On a plain `{kind:"member"}` target
it has NO effect: the survivor is always the part **AWAY from the node** — that is the end
where forces and boundary conditions are applied, and it is also the end the model prolongs
for FEM-discontinuity clearance (members.md), so keeping the node side would contradict both.
- **`remainingPart` does not select a side for a PLATE tool.** Cutting an added member by
  a plate dissects it: the slice inside the plate's thickness is removed and every
  remaining piece survives as its own part. Cut a two-sided added member (length1 AND
  length2) at both ends by plates and you get three parts whatever you set
  `remainingPart` to. **To keep one side, cut by a work plane**, where `remainingPart`
  does choose the survivor. The begin/end labels track the ADDED member's own axis
  (`begin` cuts off the `length1` end); confirm the survivor by its end faces in the scene.

## work-plane

Auxiliary: invisible in the scene, listed in generic `/operations`
as a work-plane operation, consumed as `cutBy:{kind:"workPlane", operationId}` — which is also
the reliable way to TEST where a plane is (the member's end lands exactly at it).

**Before measuring anything through a work-plane cut, establish that the plane actually
INTERSECTS the body.** A plane that misses the member cannot trim it, so two positions that
both miss will agree with each other and prove nothing. Deactivate the cut, read the member's
own span, and place the plane inside it.
**And do not judge by the member's extent** — the model prolongs it past the last modifying
operation by design (members.md), so the free end moves with the plane by the same amount
whether or not the cut does what you meant. Judge a cut by cut faces/parts, never by bbox.

**Omitted, `origin` is the global origin and `normalVector` is the vertical axis** — so a plane
sent with neither is horizontal through the node. Send only the fields of the chosen method:
how `rotationX/Y/Z` under `byNormalVector` or `byIntersection`, and `normalVector` under
`byAngles`, are treated is not specified.

- `method:"byNormalVector"` — the reliable mode. `relatedTo:"joint"`: origin +
  normalVector GLOBAL; `relatedTo:"member"`: both in the referenced member's LOCAL CSYS.
  E.g. origin.x = 0.15 with normal +X trims a stub beam at x = 0.15.
  `relatedTo:"plate"` + **`plateOperationId`** (GUI Origin=Plate): origin + normal in
  the PLATE's CSYS; the plane FOLLOWS the plate (e.g. plate mid at 0.15 → cut at 0.15,
  moved to 0.30 → cut at 0.30; origin.z = plate normal direction shifts 1:1). Mind
  the frame: a normal like (1,0,0) is plate-local and may come out parallel to your
  member → silent no-op cut. **Use `plateOperationId` (a plate-creating op id — what the
  GUI stores for Origin=Plate).** The sibling field `plateId` (internal IOM plate id)
  is REJECTED on POST with HTTP 422 — use `plateOperationId`.
- `method:"byAngles"` — base normal before rotation is **global Z**. To cut, the
  rotation must lean the normal into the member's axis; a rotation leaving the plane
  parallel is correctly rejected ("The cutting plane is parallel to beam") — for a beam
  along +X only `rotationY` cuts; this is geometry, not a bug.
- `method:"byIntersection"` — **member × member ONLY** (GUI: Member + Related member +
  Offset X + Near intersection; no plate option exists). `memberId` +
  `relatedMemberId`: plane lands ⊥ on the member at the NEAR intersection of its axis
  with the related member's surface when `nearIntersection: true` (e.g. a beam against a
  column is cut exactly at the column's flange face); with `false` on a geometry whose far
  intersection lies outside the member body the plane falls back to the member origin.
  **Both member ids are required** — without `memberId` or `relatedMemberId` the POST is **422**
  naming the field (*"WorkPlane.MemberId is required (and > 0) when Method is
  ByIntersection…"*); a non-existent or non-positive id is 422 too.
  **`relatedTo:"plate"` and `plateOperationId` do not steer this mode** — they are
  accepted and echoed back, but the member-against-member intersection still governs the
  plane, exactly as without them. **To drive a plane from a plate, use `byNormalVector`
  with `relatedTo:"plate"` + `plateOperationId`.**
  **`offsetX` acts for byIntersection**: a positive value moves the plane toward the member
  origin (e.g. +0.05 moves it from 0.10 to 0.05).
- **`offsetX` acts ONLY for `byIntersection`; a nonzero value on `byAngles` or
  `byNormalVector` is REJECTED HTTP 422** (0.0 is accepted there; on byIntersection any value is
  accepted and round-trips). `relatedTo`
  (member/joint) does NOT change this — only `method` does. byIntersection offsetX is the GUI
  "Offset X" field (GUI shows it only for By Intersection). So keep `offsetX` at 0 on
  byAngles/byNormalVector and position via `origin`. The CUT's
  own `offset` composes ADDITIVELY with the plane position (e.g. plane x=0.15 + cut.offset 0.15 →
  cut at x=0.30).

## plate-cut

`modifiedObject` = the plate being cut (a plate-family target reference, `plateSubIndex: 1`
REQUIRED). Minimal working body:

```json
POST .../operations/plate-cut
{ "name": "PC", "active": true,
  "modifiedObject": { "kind": "plateOfOperation", "operationId": <plateOp>, "plateSubIndex": 1 },
  "cutBy": { "kind": "member", "memberId": 2 },
  "cuttingMethod": "surface" }
```

- cutBy a MEMBER passing through the plate's face → punches the member's profile
  outline through the plate (an opening; plate stays one piece → `remainingPart`
  irrelevant there).
- cutBy a workPlane that SPLITS the plate → `remainingPart` picks the surviving side
  (e.g. a horizontal plane at z=0.1 through a 0.4 plate + `"lowerSide"` → the survivor
  spans z ≤ 0.1).
- `weld` on the plate-cut is accepted. GUI-authored plate cuts ARE readable via the typed
  plate-cut GET.
- **`cuttingMethod` on a plate-cut: use `surface` or `boundingBox`** — the two the plate-cut
  dialog itself offers:
  - `surface` — trims the plate tight against the tool's face. **Needs a real intersection**:
    when plate and tool do not touch there is nothing to trim.
  - `boundingBox` — works off the tool's ENVELOPE, so it shortens the plate to the tool's
    envelope even when the two do not touch.
  Pick by what you want: follow the tool's real face, or cut back to its envelope.
- **Oracle warning for plate cuts** — IOM `region` cannot see a `surface` cut (it is the
  plate's outer OUTLINE, so a trim following another plate's face leaves it unchanged, the
  same blind spot as a hole), and `len(region)` shifts with float formatting alone. Read the
  named `IFCPLATE` in the IFC and follow it to its faceted brep; keep an UNCUT control plate
  in the model as the etalon. Compare COORDINATES, not counts: `boundingBox` shortens the
  plate so a box stays a box (same faces/vertices, moved), while `surface` keeps the extent
  and adds vertices.

## negative volumes

`negative-member` and `negative-plate` (and stiffening-plate `plateType:"negative"`)
are **cutting-tool definitions, not solids** — no body, no analysis effect. The
presentation scene draws them unconditionally (looks like a persistent solid; the GUI
draws them only while selected) — not a subtraction bug. To remove material: follow
with `cut` + `cutBy:{kind:"negativeVolumeMember"}` (member tool) or
`cutBy:{kind:"plateOfOperation", plateSubIndex:1}` (plate tool; dissects).

**IOM note — judge a cut by the exported solids (cut faces, part counts), not by the cut
records.** In the XML export a cut by a member or a plate (a negative plate included) is a
`<CutBeamByBeamData>` with its name, tool and method; a work-plane cut has none. The JSON export
lists only some cuts, as bare ids (`cutBeamByBeams`, `beams[].cuts`). IOM lists a negative volume in `plates[]`/`beams[]` with `isNegativeObject: true`;
filter on it before counting material.

## Hollow-section (CHS/RHS) joints — consolidated path

Tube-to-tube joints have NO plate edges, so the plate-based patterns don't apply:
- **Cut** the brace to the chord with `cuttingMethod:"surface"` (CHS-CHS yields the
  saddle; mm-exact to the facing wall).
  **Never `surfaceAllAround` for a cope** — it leaves sub-millimetre outline segments the
  cleanup tolerance misses, and the member then fails mesh generation. The trap is that
  nothing warns you: the operation answers 200 with `addedWithoutIssues: true` and no issues,
  and the scene even looks *richer* than the healthy one (the extra weld groups ARE the stray
  segments). **It only shows up at `calculate`**, as `Analysis` 0.0 with *"CBFEM analysis
  failed - the solver did not produce any results."* while the same joint cut with `surface`
  passes normally. If a cope produces that summary line, suspect the cutting method before the
  loads or the geometry.
- **Weld** ONLY via the cut's integrated `websWeld`/`flangesWeld` — a standalone
  `weld` op throws "Object reference not set to an instance of an object." (no plate
  edges to pair). Plate-EDGE welds are unavailable directly between tubes.
- Gusset plates for tube-to-tube force transfer still need an intermediate PLATE
  welded on, then weld/bolt to it.
- A bolt-grid CAN attach a plate (e.g. an end plate) to a tube WALL, though: reference
  the wall as a member plate `{memberId, plateSubIndex}` — the RHS walls parallel to
  the end plate are the subIndex candidates (see grids.md). This is the end-plate-to-
  column path, distinct from tube-to-tube bracing above.
