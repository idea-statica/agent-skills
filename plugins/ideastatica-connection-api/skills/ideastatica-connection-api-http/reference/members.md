# Members & added members — placement semantics

**TWO different objects live here, with overlapping field names.** A joint member
(`ConMember`, `position`) and an added member (`stiffening-member` / `negative-member`,
`positioning`) each have their own Euler triple and their own `axisX` — the added member's
names are *shuffled* relative to `ConMember`'s. Finding a field under one heading is not an
answer about the other: check which object your heading belongs to before you use it.

**Answers:** added-member positioning in the `onMember` and `onPlate` modes ·
`length1`/`length2` · `mountType`/`mountLocation` · the added-member angle triple and `lcs` ·
`ConMember` angles, `directionVector`, `align` · eccentricities · `mirrorY`/`mirrorZ` ·
`connectedBy`/`isContinuous` · why member length is not yours to read · bearing /
cross-section / stiffness fields.

`positioningType: "joint"` is the third mode and the default when `positioning` is omitted: the
member floats free of any host face, so it takes no `weld` (weld bullet below). For its
field list see `field-matrix.md` §"stiffening-member · negative-member" (the `joint` column).

**Does NOT answer:** the plates' weld gate → `plates.md` §"The integrated `weld` block works
with only TWO positionings" (added members follow the rule on this page instead) · which
fields apply for the enum value you are sending → `field-matrix.md` · what a cut or negative
volume does → `cuts.md` · full load-effect and material request shapes → `io-shapes.md`.

## Added members — stiffening-member / negative-member (`ConAddedMemberPositioning`)

- **`insertPoint` is GLOBAL; `eccentricity` is LOCAL** (rotates with the member's own
  axes). Not interchangeable.
- `length1`/`length2` = extents from insertPoint along the axis in the two opposite
  directions (insertPoint is the split point; length2 grows the far side). Precisely, the
  member occupies `[−length1, +length2]` on its own axis, so a **negative value flips that
  end to the other side** rather than shortening in place: `0.4 / −0.1` gives a 0.3 m member
  lying entirely on the `−` side, never touching the insert point, and `−0.4 / +0.1` gives
  the same span on the `+` side. The only refused case is the two ends coinciding (`0 / 0`,
  `0.33 / −0.33`) → HTTP 200 with `addedWithoutIssues: false` and "Input data of Stiffening
  member (or Negative volume member) are not valid.", nothing added to the model. Both values
  round-trip on GET with their sign, so read them as coordinates, not as lengths.
- **An omitted `positioning` defaults to `joint`.** Leaving the block out, or sending `null`,
  answers 200 on `stiffening-member` and `negative-member` and the typed GET returns
  `positioningType: "joint"` — the same default the plate siblings apply. A block that is
  present but has no `positioningType` (`{}`) is **422** *"Positioning.PositioningType is
  required: set it to joint, onMember or onPlate…"*.
- Angle triple is a proper Euler set with names SHUFFLED vs ConMemberPosition:
  `angleAlpha` = azimuth (↔ betaDirection), `angleBeta` = pitch into +Z (↔ gamaPitch;
  90° → vertical), `rotationRx` = section roll (↔ alphaRotation). Compose independently.
- `placementDefinition:"lcs"` with explicit `axisX/Y/Z` is honored directly — the
  predictable alternative.
- `positioningType:"onMember"`: **place along the host with `positionX`**, measured from the node
  along the host's local +x — `connectedBy` does not flip it. **On a host connected by its `end`
  (body at x_local ∈ [−L, 0], § `connectedBy`) send a NEGATIVE `positionX`**: a positive one
  puts the added member beyond the host's end, outside the member, and still answers
  `addedWithoutIssues: true`. Check its position in IOM against the host's span;
  `eccentricity` takes `y` and `z`, and a non-zero `eccentricity.x` on `onMember` or `onPlate` is
  422 *"Positioning.Eccentricity.X is not used by the OnMember placement: set the position along
  the host with Positioning.PositionX …"*. `positionY` applies to `onPlate` only (on `onMember`
  it reads back 0). At `rotation` 0 a `rib` or `doubler` runs along the host's axis and a
  `widener` across it; `mountType` decides how its section sits on the face. Turn a `widener`
  with `pitch` — its `rotation` is stored but does not turn it (`onMember` and `onPlate`).
  **The host's direction and roll can move an added member to another side of the host or turn
  it** — the same `mountLocation`, `rotation` and `pitch` do not give the same placement on every
  host. A `widener` follows the host's direction and roll; whether a `rib` or `doubler` does
  depends on the host section and on `onMember` vs `onPlate`. Positions are recomputed when a
  file opens — read them from the opened project. **Read every `onMember` and `onPlate` added
  member's position back from IOM `beams[].plates[]` (world coordinates) and compare it with the
  host's axes before you build on it.** On `onMember` the member follows the host's eccentricity
  component normal to its host plate and not the in-plane ones; on `onPlate` it moves with its
  host plate.
  Host plate selected by **`onMemberPlateIndex`, 0-BASED** (IPE ONLY: 0 = bottom flange,
  1 = top flange, 2 = web — this order is section-specific, the same IOM wall order as a plate's
  `plateOnMemberIndex`, which counts from 1 (`plates.md`); probe per section; an index past the last wall is not silent: 200 with
  `addedWithoutIssues: false`, *"Input data of Stiffening member (or Negative volume member) are
  not valid."*, and nothing is built).
  NOTE: stiffening-PLATE's `plateOnMemberIndex` is 1-based — real API inconsistency
  between the two families.
  Index→plate mapping differs per host section type — probe the first joint of a new
  section; the `pitch` needed for a given orientation depends on the host (read it back as
  above; don't hardcode it across a batch).
  **On `mountType: rib`, `pitch` does not turn the member's axis** — the added member's world
  axis is unchanged across its whole range, while `rotation` over the same range does turn it.
  `GET` echoes the `pitch` you sent either way, so the round-trip proves nothing. Whether it
  turns the section roll instead is not documented — check against the GUI before relying on it.
- `mountType`: `rib` stands off perpendicular; `doubler` flush on the face; `widener`
  extends the flange. `mountLocation` **wire enum = `leftSide` | `rightSide` | `bothSides`
  | `center`** (the GUI terms front/rear map to `leftSide`/`rightSide`; sending the GUI
  string `"front"`/`"rear"` → HTTP 400 "Error converting value ... to type ConLocation").
  Pair the mount type with a location it allows — on a member host `rib` and `doubler` take
  `leftSide`, `rightSide` or `bothSides` and `widener` takes `leftSide`, `rightSide` or
  `center`; on a plate host all three take `leftSide` or `rightSide` (`field-matrix.md`). A
  disallowed pairing is refused with 422 naming the allowed set (e.g. `center` with `rib` →
  *"'Center' is not valid for 'Rib'"*). Avoid `widener` + `bothSides` specifically: it reports
  the issue "Input data of Stiffening member (or Negative volume member) are not valid." yet
  still leaves a member in the model — treat it as unsupported rather than as a clean refusal.
  Mount a widener on a member that is not the supporting one; on the supported edge it is
  refused. NOTE: enum acceptance ≠ meaningful geometry — the
  wrapper doesn't expose the built shape, so verify materialization (SKILL.md rule 4) rather
  than assuming an accepted value placed the part sensibly. (Same enum as a plate's
  `location`; the accepted pairs differ — `field-matrix.md`.)
- `positioningType:"onPlate"` — **mount an added member on a plate with
  `onPlateOperationId`**, naming the operation that produced the plate; author that plate
  operation first so its id exists. It answers 200, `addedWithoutIssues: true`, and the member
  materializes (IOM `beams` grows, the profile is right). Selecting the host by
  **`onPlateIndex`** instead is unreliable — the index space is not the plate order you sent,
  and a wrong value comes back as HTTP 200 with `addedWithoutIssues: false` and the issue
  "Input data of Stiffening member (or Negative volume member) are not valid.", so check those
  two fields rather than the status. Set one selector, not both — sending both is refused.
  The typed GET returns `onPlateOperationId` and `crossSectionId`, so an `onPlate` member's GET
  body PUT back unchanged keeps it on its host.
  **`addedMemberPlateIndex`** (0-based) selects a plate on the ADDED member itself, default 0.
- `weld` on stiffening-member applies only on a host face (`onMember` or `onPlate`). On a
  `joint`-positioned member it is not applied: 200, `addedWithoutIssues: false`, issue *"Weld: a member positioned at the joint is
  connected by the joint itself and has no weld of its own…"*.
- **An added member's weld takes its material from `weld.materialId`** (`welds.md` § Weld material).
- **negative-member alone removes nothing** — it's a cutting-tool definition. Follow with
  `cut` + `cutBy:{kind:"negativeVolumeMember", operationId}` for true boolean
  subtraction (see cuts.md). Its `crossSectionId` shapes the volume.

## ConMember position — `definedBy: "rotationsOfX"` (angles in RADIANS)

**Put `definedBy` — `rotationsOfX`, `directionVector` or `lcs` — into every `position` block
you send.** A member sent with no `position` at all gets `rotationsOfX`. A `position` without
`definedBy`, or with `none`, is 422 and nothing is written (*"position.definedBy must be one of
directionVector, rotationsOfX, lcs, but was 'none'. A position sent without definedBy reads as
none."*). Every member enum (`connectedBy`, `align`, the `alignedPlate` part and side,
`model.forcesIn`, `model.modelTypeEnum`) sent as an out-of-range integer is 422 naming the field
and the allowed values, as an unknown string 400. An all-zero `axisX` is 422.

- All zeros → member along **global +X**.
- `betaDirection` — in-plan direction from +X in the global XY plane (β=90° → +Y).
- `gamaPitch` — pitch; positive lifts toward +Z.
- `alphaRotation` — section roll about the member's own axis, right-hand rule about
  local +x (45° on IPE200 → top flange rotates toward local −y).

**A `position` block also rewrites `offsetEx/Ey/Ez` and `alphaRotation`.** They are taken
unconditionally and none of them is nullable, so a block that omits them writes zeros. Send the
whole block, never a fragment.

**Spell the angle fields exactly.** An invented field name is dropped without an error — there
is no `alphaZ`; the angles are `betaDirection`, `gamaPitch`, `alphaRotation` — so the member is
built with that angle at 0. Read the resolved `axisX`/`axisY` back after the POST. Example —
a vertical column: `{"definedBy":"rotationsOfX","gamaPitch":1.5708,"betaDirection":0,"alphaRotation":0}`;
a horizontal beam: the same block with `gamaPitch: 0`.

**`origin`, `axisY` and `axisZ` are reported, not set.** They come back as the member's
resolved local frame, for every member however it was placed — that is what you read to
interpret eccentricities and to lay out plates and grids against the section. Sending them
orients nothing; use `axisX` with `lcs`, or the angle triple. **With `lcs` the member is
oriented by `axisX` and `alphaRotation` only** — `betaDirection` and `gamaPitch` are stored and
echoed but turn nothing.

**`axisX` reads back normalised** — the same direction, unit length. A GET → PUT of the
unmodified member keeps its geometry under `rotationsOfX`, `directionVector` and `lcs`; a member
that reads back `definedBy: "none"` needs one of the three before its body PUTs back.

## `position.align` — aligning to another member's plate

`alignedPlate` and `relatedPlate` are stored and reported **only when `align` is not `none`** —
set the alignment, or the two blocks go nowhere.

`alignedPlate` names a plate of the member being placed, `relatedPlate` the plate of the other
member it is aligned to. Each is `{memberId, partType, plateSide}`: the member that owns the plate, which of its plates
(`topFlange`, `bottomFlange`, `web`, `basePlate`, … 25 values), and which side (`default`,
`lowerSide`, `upperSide`, `bothSides`, `center`). The plate is found **by its part type**, not by
an index.

**Name a part each member has.** Either block may be sent without the other, and each reads
back as sent; a part type the member does not carry is 422 *"Member with id '1' has no plate of
type 'BasePlate'."*

## `definedBy: "directionVector"`

- Direction goes in `position.axisX` `{x,y,z}` (any magnitude — server normalizes). Send the
  direction under exactly that name: any other field name (`direction`, `directionX`…) is
  dropped and the member is built along **global +X**, the same as omitting the direction
  entirely. So a member that reads back `axisX:(1,0,0)` while you asked for something else is
  the signal that your direction field was not read — it does NOT inherit the bearing member's
  direction.
- The response carries no `betaDirection` / `gamaPitch` in this mode — read the orientation
  from `axisX`/`axisY`/`axisZ` instead. `alphaRotation` still acts here: send it to roll the
  section about the member axis and it round-trips on GET.
- Derived CSYS is DETERMINISTIC: `axisY = normalize(globalZ × axisX)` (horizontal,
  axisY.z = 0), `axisZ = axisX × axisY` oriented so axisZ.z > 0. Degenerate when
  axisX ∥ globalZ. Example: `axisX=(0,.707,.707)` → `axisY=(−1,0,0)`, `axisZ=(0,−.707,.707)`.
- Eccentricities act in THIS local CSYS — an in-plane offset of a tilted member must be
  composed from offsetEy·axisY + offsetEz·axisZ.
- **Do NOT assume which global axes the profile HEIGHT vs WIDTH land in.** The derived
  CSYS fixes the section roll, so for a given axisX the profile depth and breadth map to
  specific global directions that are NOT obvious from the input — and they decide where a
  base/end plate's long side and any "behind the flange" / "across the width" fastener rows
  must go. Before sizing a plate or laying out a grid tied to the section outline, READ
  the member walls' real extents from IOM `beams[].plates[]` (or per-group extents in the
  presentation scene) and choose the plate/anchor axes from that. Verify a plate's overhang
  as (plate extent − member extent)/2 per axis from the scene — never from the numbers you
  sent. (Same "test, don't assume" discipline as SKILL.md rule 11.)
- **A direction alone does not orient a member against ANOTHER member — set the roll too.**
  The derived frame is built from global Z, so it knows nothing about the joint: give two
  members directions that are geometrically right and their sections still meet at whatever
  angle that construction happens to produce. Where a joint requires two sections to share a
  plane — webs in line, flanges facing — that is a second condition, and it is `alphaRotation`
  that satisfies it.

  It is solvable in closed form, with one probe and no searching. Post the member at
  `alphaRotation: 0`, read its derived frame back, then, with `bx` the member axis and `tgt`
  the direction its section must align to:

  ```
  t = normalize(tgt − bx·(tgt·bx))          project the target into the plane normal to bx
  alpha = atan2(t·axisZ₀, t·axisY₀)         its angle in the derived frame
  ```

  then `PUT` the member with that `alphaRotation`. The projection is the step that matters:
  the target generally has a component along the member axis, and skipping it gives an angle
  that happens to be right only when that component is zero — so code tried only on a
  near-aligned case fails off-axis.

  **Name the reference vectors from the section, not from a guess**: for an I profile the web
  lies in the local XZ plane, so the web NORMAL is local **axisY**, while the flanges are
  normal to axisZ. Getting that pair the wrong way round produces a member rolled by 90° with
  everything else correct.

  Misalignment here is not reported anywhere: the members are accepted, the plates and welds
  build on them, and the failure surfaces much later as a solver error with no geometric
  meaning. **Check it directly** — the dot product of the two members' relevant section axes
  should be ±1 (aligned) or 0 (perpendicular), to the precision of the read.

## Eccentricities `offsetEx/Ey/Ez` (metres) — LOCAL CSYS

- `offsetEy` → along local axisY; `offsetEz` → along local axisZ (don't expect global
  intuition: member along +Y has axisY = (−1,0,0)).
- `offsetEx` slides the member ALONG its own axis away from the node (gap/stub offset,
  not lateral) — e.g. `offsetEx` 0.08 shifts the member's span 0.08 m away from the node.

## `mirrorY` / `mirrorZ` — named by the axis the mirror PRESERVES

- `mirrorY: true` → mirror about local y: **z → −z** (up-leg points down).
- `mirrorZ: true` → mirror about local z: **y → −y**.
Easy to get backwards: mirrorY does NOT flip y.

## `connectedBy` + `isContinuous`

- `"begin"` (default): body extends from the node into +axisX (x_local ∈ [0, L]).
- `"end"`: body on the opposite side, far end at the node (x_local ∈ [−L, 0]).
- `isContinuous: true`: passes through, centered (x_local ∈ [−L, +L]). This is how you
  get a through/bearing member. To cut a continuous member use
  `cuttingMethod:"surfaceAllAround"` with a NON-ZERO `offset`, so the cut clears the
  supporting member — that combination removes material. The other methods are refused on a
  continuous member: `boundingBox` and `mitreCut` come back with the issue *"The continuous
  member cannot be cut."*, and `surface` either leaves the member uncut or is refused for
  interfering with the support. All of these are HTTP 200 — read `addedWithoutIssues` and `issues` to tell
  a refusal from a cut. (See cuts.md.)
- All persist on POST (echo == GET == sent), incl. mirrors and offsets.
- `connectedBy` is read **only for a non-continuous member**. A continuous one sits at its
  centre and always reads back `begin`, whatever you sent.
- Wire trap: `ConMember.connectedBy` is lowercase `"begin"/"end"`. Load-effect positions
  read back PascalCase `"Begin"/"End"`, but INPUT binding is case-INSENSITIVE (`"end"` →
  200, normalized to `"End"` on GET) — emit PascalCase for cleanliness, but a casing
  mismatch on input is not an error.

## Member length is NOT yours to read — the model prolongs it automatically

**A member is prolonged beyond the LAST operation that MODIFIES it**, so its free end sits far
enough from the FEM discontinuities the operations introduce. This is a modelling rule of the
application, not a property of any one operation or field.

- **Presence is not modification.** A plate merely crossing the member changes nothing — a
  bare member and member + crossing plate have identical extents. Weld that plate on,
  or cut the member with it, and that becomes the last modifying operation, so the prolongation
  follows it.
- **Consequence: extent / bbox / max-coordinate is NEVER an oracle for a cut.** Move a cut and
  the free end moves with it by a margin, whatever the cut did or did not do. Judge a cut by cut
  faces and part counts. The two readings this allowance invites are "the plane cuts" and "the
  plane extends the member" — both are the margin, not the cut.
- **Not to be confused with `extendMember`**, which is a real and separate effect on the cut
  side: it pulls the member out to the tool where it falls short of it. On a clean model the two
  are easy to tell apart — extend moves the CUT end while the free end stays put. See
  cuts.md.
- **Second-order effect worth knowing:** pushing a cut outward pushes the free end too, so a
  neighbouring member can fall out of reach — welds to it then simply stop existing. An
  entity-count drop in the export is not necessarily a lost cut.
- And do not read the WHOLE-model extent when you mean one member: in a two-member model the
  maximum moves for reasons unrelated to the member you are studying.

## Member-level fields — bearing, cross-section, stiffness

- `crossSectionId` names an existing cross-section of the project. Omitted on a POST, the
  project's first one is used; an unknown id on a POST is refused with 422. **On a PUT, take
  the id from `GET .../materials/cross-sections`** — the PUT stores it unchecked, and an id the
  project does not hold reads back as sent and makes `calculate` fail with *"Cannot execute the
  operation."* A valid id changes the member's section, and its IOM `mprlName` follows — unless
  a parameter drives the section (`parameters.md`).
- `isBearing` is read-only: the first member of a connection gets it. To move it,
  `PUT .../members/{memberId}/set-bearing-member`. On a `stiffness` or `horizontalTying`
  connection the bearing member is the member being analysed (the desktop labels it
  "Analysed member"): set it to the member whose stiffness or tie force you want.
- `active` is read-only on the members endpoint.
- **`stiffnessAnalysis` is reported only on a stiffness-analysis connection.** The values are
  stored whatever the connection's analysis type — values written under any analysis type are
  kept and appear once the connection is `stiffness` — but until then every response omits the
  block. So an absent `stiffnessAnalysis` means "not applicable to
  this analysis", not "your value was lost". Members start with theoretical lengths derived from
  the geometry, so you are overriding a value rather than filling a blank; either theoretical
  length may be sent alone.

## Not on this page

- **Creating a cross-section or a material** — the field is `mprlName`, not `name`:
  `SKILL.md` §"Frequently-needed shapes" for the recipe, `io-shapes.md` §Material for the full
  set of material types and their request shapes.
- **Load effects** — `io-shapes.md` §LoadEffect carries the whole contract: `ConLoadEffect` /
  `memberLoadings` / `sectionLoad` shapes, absolute values (`"isPercentage": false` on write,
  `?isPercentage=false` on read; forces in N, moments in N·m), the per-member validation rules,
  and what a GET does and does not echo back.
