# Field matrix — which field applies in which configuration

**Come here before you send a body, with the enum value you are about to send in hand** —
`anchorType`, `cuttingMethod`, `conPlatePositioningType`, `positioningType`, `definedBy`,
`weld.type`, `shape`, `method` … Each one switches which of an operation's fields are read at
all, and the switch is not in the swagger.

**And come here when a request "succeeded" and the model is not what you asked for:** the
**S**, **W** and **F** cells are the answer to that, more often than anything else.

**Lookup, not prose.** Find the operation, find the value you are sending, read the row. Then
go to that operation's own reference page for the semantics — this page says *whether* a field
applies, never *what it means*.

**The tables, each with the value that switches it:**

| operation | switched by |
|---|---|
| `weld` | `placement`, `weld.type`, `weld.kind` — plus welds carried by *other* operations |
| `cut` | `member.kind`, `cutBy.kind`, cutting tool |
| `plate-cut` | — (one table) |
| `bolt-grid` · `anchor-grid` · `pin-grid` | the fastener, `anchorType`, `foundationBlock.blockType`, grid geometry style |
| `contact` | — |
| `contact-grid` | `foundationBlock` present or not, then `foundationBlock.blockType` |
| `stiffening-plate` · `negative-plate` | positioning type, `function` × `location`, `shape` |
| `stiffening-member` · `negative-member` | `positioningType` (`joint` / `onMember` / `onPlate`) |
| `members` | `position.definedBy`, `position.align`, `model.forcesIn` |
| `work-plane` | `method`, `relatedTo` |

Plus one table that is not an operation: **`parameters`**, switched by the target property's
`valueType` — last section on this page. Go there before linking a parameter: some targets link
and apply with 200 and drive nothing.

Cross-operation traps this page exists to expose, and which a per-operation page could not:
`plateSubIndex` is **base 0 in some operands and base 1 in others**; `remainingPart` means a
plate side on a `plate-cut` and `begin`/`end` on a `cut`; `onMemberPlateIndex` (added member)
is 0-based while `plateOnMemberIndex` (plate) is 1-based. Read the neighbouring tables, not
just yours.

Legend, one letter per cell:

| | |
|---|---|
| **Y** | applies in this configuration — send it |
| **R** | required here — the request is refused without it |
| **—** | does not apply here; leave it out |
| **F** | the value is determined for you; whatever you send is replaced |
| **S** | silently inert — accepted, changes nothing, no error raised |
| **W** | write-only — taken from the request, never echoed by `GET`; a GET→PUT cycle loses it |
| **X** | rejected (the response says why) |
| **I** | accepted, reported as an issue (`addedWithoutIssues: false`), and the part stays in the model |
| **?** | not documented — test against your service before relying on either answer |
| **ᵃ ᵇ** | same superscript in one table = mutually exclusive; send one of them, not both |

**S**, **W** and **F** are the cells to check first when a request "succeeds" and the model is
not what you asked for. **?** means not documented either way — unknown, not safe.

Extra columns, where a table carries them: **base** (`1`/`0` — an index field's first value;
the base is **not uniform** across the API and it is the most common single mistake), **unit**,
**values** (the accepted enum members), **default** (what you get by omitting the field).

## Rules that hold for every operation

- **`active` omitted means active.** Send `false` explicitly to add a dormant operation.
- **Object and operation ids are positive.** `0` and negatives are refused, not read as
  "unset" (catalog ids: next bullet).
- **A supplied catalog id must exist and be of the right type** — see SKILL.md rule 8. Omit the
  field, or send `0`, to accept the default instead.
- Operation-wide behaviour (`name` generation, all-or-nothing writes, GET→PUT safety):
  `operations.md`.

---

## weld

Three independent axes: `placement`, `weld.type`, `weld.kind`. Semantics: `welds.md`.

### by `placement`

| field | edgeToSurface | edgeToEdge | base | unit | notes |
|---|---|---|---|---|---|
| `firstMemberOrPlate` | R | R | — | — | `{memberId + plateSubIndex}` \| `{plateId}` \| `{operationId + plateSubIndex}` |
| `firstPlateEdgeIndex` (array<int>) | Y — send it | Y — send it | 1 | — | **S** if omitted, empty or `[0]` |
| `secondMemberOrPlate` | R | R | — | — | as above |
| `secondPlateEdgeIndex` (int) | S — any value, the weld is the same | R | 1 | — | on `edgeToEdge`: `0` or out of range → X |
| `weld.type` | Y | Y | — | — | six values, see below |
| `weld.size` | Y | Y | — | m | `0` designs it |

`plateSubIndex` in a member operand: base **0** — a member operand sent bare (`{memberId}`
alone) is not the same as index 0; qualify every member operand (`operations.md`). In an
operation operand: base **1**, and `0` also selects the operation's first plate.

Both edge indexes are positions in the list of edge pairs the engine found touching, not
polygon segments — how to pick and verify them: `welds.md`.

### by `weld.type`

| field | filletFront / filletRear / doubleFillet | cjp | pjp | noWeld |
|---|---|---|---|---|
| `weld.size` | Y — `0` designs it | Y — `0` designs it | Y — `0` designs it | S |

**`size: 0` is a request for the engine to CHOOSE a size, on every weld type; any non-zero
value is stored verbatim.** Zero is not "no weld" and not "leave it unset" — the engine
substitutes a size and that is what ends up in the model. What it picks depends on the type,
the plate, the design code's weld-size rounding, and whether the code states welds by leg or by
throat (a zero is replaced by a code-dependent default, rounded UP to the code's weld-size step,
and converted by √2 when the code states welds by leg). Do not try to
predict the value — read it back.

Consequences worth knowing:
- **The sizes you get from `0` differ between weld types on the same plate**, so a model built
  with zeros is not a controlled comparison between types.
- **The POST/PUT response cannot tell you what was chosen** — it echoes your `0`. Only
  `export-iom` shows the stored `<Thickness>`.
- Send an explicit size whenever the dimension matters to what you are measuring; send `0` when
  you deliberately want the engine's own design.

**The two vocabularies differ** — REST `cjp` is IOM **`Bevel`**, `pjp` is `PJP`, `doubleFillet`
is `DoubleFillet`. Do not match them by string.

The POST/PUT response only echoes what you sent, so a `cjp` read back from REST still says
`size: 0.0` — the substituted thickness appears in `export-iom` alone. Dialog labels and the
per-type check semantics: `welds.md`.

### by `weld.kind`

The desktop has three states where the API has two values; `partial` is composed, not named.
This table is the `weld` operation's; every other operation takes `continuous` only (next table).

| field | continuous | partial (`intermittent` + `length: 0`) | intermittent | unit |
|---|---|---|---|---|
| `weld.kind` | Y | Y — fillets and `pjp`; S on `cjp` | Y — fillets and `pjp`; S on `cjp` | — |
| `weld.beginOffset` | F → 0 | Y — S on `cjp` | Y — S on `cjp` | m |
| `weld.endOffset` | F → 0 | Y — S on `cjp` | Y — S on `cjp` | m |
| `weld.length` | F → 0 | Y — `0` | Y — S on `cjp` | m |
| `weld.gap` | F → 0 | — | Y — S on `cjp` | m |

### welds carried by other operations

A weld is not exclusive to the `weld` operation. **Stitches exist only on the `weld`
operation**; elsewhere `kind: "intermittent"` (partial included) is **X** unless `type` is
`noWeld` (`welds.md` § Stitched welds).

| operation | welds | field names | type / size | `materialId` | `kind` | length, gap, offsets |
|---|---|---|---|---|---|---|
| `weld` | 1 | `weld` | Y | Y | Y | Y — with `intermittent` |
| `cut` | 2 | `websWeld`, `flangesWeld` | Y | Y | `continuous` only | F → 0 |
| `plate-cut` | 1 | `weld` | Y | Y | `continuous` only | F → 0 |
| `stiffening-member` | 1 | `weld` | Y — `onMember` / `onPlate` only | Y | `continuous` only | F → 0 |
| `stiffening-plate` | 1 | `weld` | Y — see its positioning table | Y | `continuous` only | F → 0 |
| `anchor-grid` shear lug | 2 | `foundationBlock.shearLug.flangesWeld`, `websWeld` | Y | Y | `continuous` only | F → 0 |

How to give a weld a specific material: `welds.md` § Weld material.

A cut or plate-cut whose tool is a **negative volume or a work plane** carries no weld at all —
a cutting tool is not welded.

---

## cut

Two independent targets, each with its own `kind`: `member` (what gets cut) and `cutBy` (what
cuts it). Semantics: `cuts.md`.

### `member.kind` — what is being cut

| field | member | stiffeningMember | negativeVolumeMember | stubMember | values |
|---|---|---|---|---|---|
| `member.memberId` | R | — | — | — | — |
| `member.operationId` | — | R | R | R | — |
| `member.remainingPart` | S | Y | S | S | `begin`, `end` |

### `cutBy.kind` — what does the cutting

Eleven values. Which id fields you owe depends on the family. `plateSubIndex` is never `0`
here (422), and its base depends on the kind: **1** for `plateOfOperation`; for `memberPlate`
the value is read as a **0-based** wall index, so the member's first wall cannot be selected
(`cuts.md`). The same holds in a plate-cut's `cutBy` / `modifiedObject`.

| family | values | `memberId` | `plateId` | `operationId` | `plateSubIndex` |
|---|---|---|---|---|---|
| real member | `member` | R | — | — | — |
| real plate | `plate` | — | R | — | — |
| member's own plate | `memberPlate` | R | — | — | R |
| plate of an operation | `plateOfOperation` | — | — | R | R |
| added member | `stiffeningMember`, `negativeVolumeMember`, `stubMember` | — | — | R | — |
| added member's plate | `stiffeningMemberPlate`, `negativeVolumeMemberPlate`, `stubMemberPlate` | — | — | R | R |
| work plane | `workPlane` | — | — | R | — |

### by cutting tool

| field | a member | a plate | a work plane | values | unit |
|---|---|---|---|---|---|
| `cuttingMethod` | Y | Y | Y | `surface`, `boundingBox`, `surfaceAllAround`, `mitreCut` | — |
| `cuttingPlane` | Y | — | — | `closer`, `farther` | — |
| `direction` | Y | Y | Y | `parallel`, `perpendicular` | — |
| `extendMember` | Y | Y | Y | bool | — |
| `offset` | Y | Y | Y | — | m |
| `member.remainingPart` | Y | F — every piece survives | Y | `begin`, `end` | — |
| `websWeld`, `flangesWeld` | Y | Y (— for a negative volume) | — | — | — |

**`cuttingPlane`, `extendMember` and `cutBy.remainingPart` are gated by `cuttingMethod`, not by the tool family:**

| field | boundingBox | surface | surfaceAllAround | mitreCut |
|---|---|---|---|---|
| `cuttingPlane` | Y | S | S | S |
| `extendMember` | Y | Y | S | S |
| `cutBy.remainingPart` | S | S | S | Y — with `cutBy.kind: stiffeningMember` only; S for any other tool |

`mitreCut` is refused outright on a **continuous** member; which methods reach one: `members.md`.
What each cutting method does, and what a plate tool leaves behind: `cuts.md`.

---

## plate-cut

Cuts a plate instead of a member. Both operands use the same eleven `kind` values as a cut's
`cutBy`, with the same id rules and the same `plateSubIndex` rules — see the family table
above.

| field | cut by a member | cut by a plate | cut by a work plane | values | unit |
|---|---|---|---|---|---|
| `modifiedObject` | R | R | R | — | — |
| `cutBy` | R | R | R | — | — |
| `cuttingMethod` | Y | Y | Y | `surface`, `boundingBox` | — |
| `remainingPart` | — | F — every piece survives | Y | `lowerSide`, `upperSide`, `bothSides`, `center` | — |
| `offset` | Y | Y | Y | — | m |
| `weld` | Y | Y (— for a negative volume) | — | — | — |

`remainingPart` here is a plate side; the identically-named field on a `cut` takes
`begin`/`end` instead.

---

## bolt-grid · anchor-grid · pin-grid

One geometry object shared by three fasteners. Semantics: `grids.md`.

### what the fastener decides

| field | bolt-grid | anchor-grid | pin-grid | values |
|---|---|---|---|---|
| `connectedItems` | Y | Y | R — **≥ 3 distinct plates** | — |
| `boltAssemblyId` | Y | — | — | catalog id |
| `boltShearForceTransfer` | Y | — | — | `tensionShearInteraction`, `friction` |
| `anchorAssemblyId` + the anchor fields | — | Y | — | — |
| `pinOriginalId` | — | — | Y | catalog id |
| `foundationBlock` | — | R | — | see block table |
| `plateSide` | — | Y | — | `grids.md` § anchor-grid specifics |
| `slottedHoles` | Y | Y (— on headed stud / reinforcement) | — | — |
| `geometry.shearPlaneInThread` | Y | Y | — | bool |

`connectedItems[]` addresses each part one of four ways, and the `plateSubIndex` base differs
between them:

| item shape | `plateSubIndex` base | what it indexes |
|---|---|---|
| `{plateId}` | — | — |
| `{operationId, plateSubIndex}` | 1 | the operation's own plates |
| `{memberId, plateSubIndex}` | 0 | that member's plates FILTERED to the ones parallel to the grid's first connected item — not the absolute export order; derive it from the export (`grids.md`) |
| `{memberId}` | — | **I** in a bolt-grid and a pin-grid — not refused; the engine reports it and builds nothing. Give the `plateSubIndex` (`grids.md`) |

### anchor-grid — by `anchorType`

Six values. `anchorType` omitted is **F → `threadedRod`**, and every field belonging to another
type is then discarded — send it explicitly.

| field | threadedRod | generalAnchor | hookedAnchor | washerPlate | headedStud | reinforcement | unit / values |
|---|---|---|---|---|---|---|---|
| `anchorAssemblyId` | Y | Y | Y | Y | — | — | catalog id |
| `anchorDiameter` | — | — | — | — | Y — omitted → 0, no geometry | R — 0 or omitted **X** | m |
| `embedmentDepth` | Y | Y | Y | Y | Y | Y | m |
| `hookLength` | — | — | Y — below the code minimum **X** | — | — | Y — below the code minimum **X** | × ø on `hookedAnchor`; m on `reinforcement` |
| `washerPlateShape` | — | — | — | R | — | — | `circular`, `rectangular` |
| `washerPlateSize` | — | — | — | Y | — | — | m |
| `headDiameter` | — | — | — | — | Y | — | m |
| `headedStudMaterialId` | — | — | — | — | Y | — | catalog id |
| `reinforcementMaterialId` | — | — | — | — | — | Y | catalog id |
| `reinforcementShape` | — | — | — | — | — | Y — send `lShape` | `lShape`, `uShape` |
| `mandrelDiameter` | — | — | — | — | — | S | × ø |
| `hookRotations` | — | — | — | — | — | Y on a layer grid, S on a `userPositions` grid | rad, one per anchor |
| `geometry.userPositions[].hookRotation` | — | — | — | — | — | Y | rad |

The identifier changes with the type: the first four take an **assembly id**, `headedStud` and
`reinforcement` a bare **`anchorDiameter`**. `embedmentDepth` is the one embedment field for all
six.

### anchor-grid / contact-grid — by `foundationBlock.blockType`

Every row but the last is a field **inside** `foundationBlock`. A contact grid without
`foundationBlock` is the plate-to-plate column of the `contact-grid` table below.

| field | new | existing | values | unit |
|---|---|---|---|---|
| `foundationBlock.blockType` | Y | R | `new`, `existing`; omitted → `new` | — |
| `foundationBlock.existingBlockOperationId` | X | R — an earlier operation that created a block | operation id | — |
| `foundationBlock.height` | R — **> 0** | X (non-zero) | — | m |
| `foundationBlock.offsetTop/Bottom/Left/Right` | Y | X (non-zero) | — | m |
| `foundationBlock.shearForceTransfer` | Y | X (other than `friction`) | `friction`, `anchorBending`, `sliding`, `shearLug` | — |
| `foundationBlock.shearLug` | Y — needed with `shearLug` (without it 200 + issue), **X** with any other transfer | X | `{crossSectionId, length, positionX, positionY, rotation, flangesWeld, websWeld}` | m, rad |
| `foundationBlock.contactType` | Y | X (other than `direct`) | `direct`, `mortar`, `gap` | — |
| `foundationBlock.mortarThickness` | Y (with `mortar`) | X (non-zero) | — | m |
| `foundationBlock.concreteMaterialId` | Y | X (non-zero) | catalog id | — |
| `blockType`, `existingBlockOperationId` at the operation root | S — dropped; the grid then lacks `foundationBlock` | S | — | — |

### grid geometry — three input styles, never mixed

Sending explicit positions together with any layer or polar input is **X**, and so is a polar
grid with no `radii`.

| field | explicit positions | orthogonal layers | polar | values | unit |
|---|---|---|---|---|---|
| `geometry.userPositions` | Yᵃ | —ᵃ | —ᵃ | `{x, y, gridIndex?, slottedHoles?, hookRotation?}` | m |
| `geometry.topLayers`, `geometry.leftLayers` | —ᵃ | Yᵃ | —ᵃ | `{values, rows}` — signed cumulative coordinates | m |
| `geometry.bottomLayers`, `geometry.rightLayers` | S | S | S | not grid fields — ignored | m |
| `…Layers.rows` | —ᵃ | Yᵃ — one list per group; **X** when it contradicts `values` | —ᵃ | `[[{value, repeatCount?}]]`, `repeatCount` ≥ 1, omitted → 1 | m |
| `geometry.rowsGridLayout` | — | Y | — | `regular`, `firstShiftedFull`, `secondShiftedFull`, `firstShiftedShort`, `secondShiftedShort` | — |
| `geometry.polarInput` | —ᵃ | —ᵃ | Rᵃ | `byCount`, `byAngle` | — |
| `geometry.radii` | — | — | R | `{values, rows}`, as the layers — cumulative | m |
| `geometry.polarCounts` | — | — | Y (with `byCount`) | a plain int list `[4, 8]`, not `{values}` | — |
| `geometry.angles` | — | — | Y (with `byAngle`) | `{values, rows}`, as the layers | rad |
| `geometry.type` | S | Y | Y | `orthogonal`, `polar` | — |
| `isExploded` | Y — send `true` with positions | Y — send `false` or omit; **`true` builds no fasteners** | Y — send `false` or omit; **`true` builds no fasteners** | bool; omitted → `false`; stored as sent | — |
| `definedBy` | Y | Y (`plate` only) | Y (`plate` only) | `plate`, `coordinateSystem`; omitted → `plate` | — |
| `coordinateSystem` | F → dropped with `definedBy: plate`; **R** with `definedBy: coordinateSystem` | F → dropped | F → dropped | `{origin, xAxis, yAxis, zAxis}` | m |

**`definedBy: coordinateSystem` narrows this table to its first column** — it is the CAD/IOM
import shape, refused for authoring, and every layer or polar field above becomes a 422. The
four gates: `grids.md` §"Grid frame".

**The last three rows are on the operation ROOT, not under `geometry`**, despite sitting in
this geometry table; nested, they are dropped silently at 200. The layer fields, `radii` and
`angles` are `ConGridPositions` = `{"values": [...], "rows": [[...]]}`; only `polarCounts` is a
plain list. A bare array in place of that object is not bound: the request is refused with
HTTP 400 and nothing is stored.

**`isExploded` is a hazard on a layer or polar grid.** It is stored as sent, and on an exploded
grid the engine removes every fastener the layout generates — `true` with layers or polar input
is not refused and leaves the grid with no fasteners. Send it `true` only with `userPositions`.

There is **no origin field** in the geometry block: the pattern anchors to the frame
`definedBy` picks. A `GET` of a grid authored with `userPositions` returns `topLayers`, `leftLayers`, `radii`, `angles` and `polarCounts` as `null`.
Which style to author in, and how to read one back: `grids.md`.

---

## contact

**The weld `placement` table above applies unchanged, minus the two `weld.*` rows** — same
operands, same bases, same asymmetry. There is no `weld` block. For a contact against concrete,
use `contact-grid`.

---

## contact-grid

A plate against a concrete foundation block, or — without `foundationBlock` — a plate-to-plate
contact (`grids.md`). With a block, **the block table above applies unchanged.**

| field | on a block | plate-to-plate | values |
|---|---|---|---|
| `connectedItems` | R — ≥ 1 plate | R — **≥ 2 distinct plates** | as for the other grids |
| `foundationBlock` | R | — (its absence selects this column) | see the block table |
| `plateSide` | Y | X | `default`, `lowerSide`, `upperSide`, `bothSides`, `center` |
| `geometry`, `definedBy`, `coordinateSystem`, `isExploded` | — | — | the grid concepts do not reach this operation |

---

## stiffening-plate · negative-plate

One dialog, two operations. Three axes: `positioning.conPlatePositioningType`, `shape`, and —
on `stiffening-plate` — `plateType`. Semantics: `plates.md`.

### by positioning type

| field | joint | member | memberLcs | plateOnPlate | concreteBlock | coordinateSystem | base | unit / values |
|---|---|---|---|---|---|---|---|---|
| `offset` (x, y, z) | Y | — | Y | — | — | — | — | m |
| `rotation` | Y | — | Y — S with `byNormalVector` | — | — | — | — | rad |
| `onMemberId` | — | Rᵃ | Rᵃ | — | — | — | — | a real member of the joint |
| `onMemberOperationId` | — | Yᵃ | Yᵃ | — | — | — | — | a member another operation produced |
| `plateOnMemberIndex` | — | R | — | — | — | — | **1** | — |
| `plateIndex` | — | — | — | Y | — | — | **1** | — |
| `operationId` | — | — | — | Y | — | — | — | — |
| `function` | — | Y | — | Y | S | — | — | `rib`, `doubler`, `widener` |
| `location` | — | Y | — | Y | S | — | — | `leftSide`, `rightSide`, `bothSides`, `center` |
| `positionX` | S | Y | — | Y | Y | — | — | m |
| `positionY` | S | S | — | Y | Y | — | — | m |
| `rotationAngle` | S | Y | — | Y | Y | — | — | rad |
| `pitch` | — | Y | — | Y | — | — | — | rad |
| `plateEdgeIndex` | — | — | — | Y (widener only) | — | — | **0** (1 on screen) | — |
| `concreteBlockIndex` | — | — | — | — | R | — | — | the **operation id** that created the block |
| `concreteSurface` | — | — | — | — | R | — | **1** | 1..6, a face of the block |
| `inputMethod` | — | S | Y — `byAngles` reads `rotation`; any other value reads `normalVector` | S | S | — | — | `byAngles`, `byNormalVector`, `byIntersection`; omitted → `byAngles` |
| `normalVector` | — | — | Y with `byNormalVector` (member's local axes); S with `byAngles` | — | — | — | — | — |
| `coordinateSystem` | — | — | — | — | — | Y — omitted or `null` → the global origin and axes | — | `{origin, xAxis, yAxis, zAxis}` |
| `weld` | X | Y | X | Y | X | X | — | — |

`positioning` omitted is **F → `joint`**. A `weld` is accepted only where the positioning hands
the operation a host plate; elsewhere send `weld.type: "noWeld"` or omit the block.

### `function` × `location` — which pairs are accepted

| host | rib | doubler | widener |
|---|---|---|---|
| on a member | `leftSide`, `rightSide`, `bothSides` | `leftSide`, `rightSide`, `bothSides` | `leftSide`, `rightSide`, `bothSides`, `center` |
| on a plate | `leftSide`, `rightSide` | `leftSide`, `rightSide` | `leftSide`, `rightSide` |

On `stiffening-plate` an unlisted pair is **X**. Send the same pairs on `negative-plate`: the
API does not check them there, so an unlisted pair is stored, but the application cannot
produce or edit it. `bothSides` builds **two
plates**, one per side, from a single operation — count them rather than assuming one. The
API's `leftSide`/`rightSide` are the dialog's Front/Rear; what the two sides mean
geometrically: `plates.md`.

The `stiffening-member` table below differs on purpose: there a widener on a member does not
take `bothSides` (**I**).

### by `shape`

| field | rectangular | circle | polygon | unit |
|---|---|---|---|---|
| `width`, `height` | R — both non-zero | — | — | m |
| `width2`, `height2` | Y | — | — | m |
| `radius` | — | R | — | m |
| `polygonData` | — | — | R — SVG path string, e.g. `"M 0 0 L 0.1 0 L 0.1 0.15 Z"` | m |
| `thickness` | R | R | R | m |

### stiffening-plate vs negative-plate

| field | stiffening-plate | negative-plate | values |
|---|---|---|---|
| `materialId` | Y | Y | catalog id |
| `weld` | Y — see positioning | — | — |
| `plateType` | Y | — | `structural`, `negative` |
| `plateDataId` | ? | — | — |

`plateType: negative` carries no weld either, on any positioning. A negative plate is a cutting
tool: `cuts.md`.

GET → PUT keeps the plate editor's edits, which this DTO cannot express: `plates.md`.

---

## stiffening-member · negative-member

An added member placed relative to the joint, to a member, or to a plate. The negative variant
is the same geometry used as a cutting tool. Semantics: `members.md`.

| field | joint | onMember | onPlate | base | unit / values |
|---|---|---|---|---|---|
| `crossSectionId` | Y | Y | Y | — | catalog id |
| `length1`, `length2` | Y | Y | Y | — | m |
| `mirrorY`, `mirrorZ` | Y | Y | Y | — | bool |
| `angleAlpha`, `angleBeta`, `rotationRx` | Y (with `rotationsOfX`) | — | — | — | rad |
| `placementDefinition` | Y | — | — | — | `rotationsOfX`, `lcs` |
| `axisX`, `axisY`, `axisZ` | Y (with `lcs`); omitted → F → the identity frame | — | — | — | — |
| `insertPoint` | Y | — | — | — | m, GLOBAL |
| `eccentricity` | Y | `y`, `z`; `x` ≠ 0 **X** | `y`, `z`; `x` ≠ 0 **X** | — | m, LOCAL |
| `onMemberId` | — | R | — | — | — |
| `onMemberPlateIndex` | — | Y | — | **0** | — |
| `onPlateIndex` | — | — | Yᵃ | ? | — |
| `onPlateOperationId` | — | — | Yᵃ | — | — |
| `addedMemberPlateIndex` | — | Y | Y | **0** | — |
| `mountType` | — | Y | Y | — | `rib`, `doubler`, `widener` |
| `mountLocation` | — | Y | Y | — | `leftSide`, `rightSide`, `bothSides`, `center` |
| `positionX` | — | Y | Y | — | m |
| `positionY` | — | F → 0 | Y | — | m |
| `rotation` | — | Y — S on a `widener` | Y — S on a `widener` | — | rad |
| `pitch` | — | Y — does not turn a `rib`'s axis | Y — does not turn a `rib`'s axis | — | rad |
| `plateEdgeIndex` | — | — | Y (widener only) | **0** | — |
| `weld` | — | Y | Y | — | — |
| `materialId` | **S** (stiffening only) | **S** | **S** | — | catalog id |

`positioning` omitted or `null` is **F → `joint`**; `{}` without `positioningType` is **X**.

`mountType` × `mountLocation` — accepted pairs, on `stiffening-member`:

| host | rib | doubler | widener |
|---|---|---|---|
| on a member | `leftSide`, `rightSide`, `bothSides` | `leftSide`, `rightSide`, `bothSides` | `leftSide`, `rightSide`, `center`; `bothSides` **I** |
| on a plate | `leftSide`, `rightSide` | `leftSide`, `rightSide` | `leftSide`, `rightSide` |

Every other pair is **X**, with the allowed set named. **On `negative-member` the pairs are not
checked** — combinations a stiffening member refuses go through — and its `weld` and
`materialId` rows read `—` throughout: only cross-section and length shape the tool.

---

## members

A member of the joint itself, not an operation. Three axes: `position.definedBy` (how it is
oriented), `position.align` (whether it is aligned to another member's plate) and
`model.forcesIn` (where its forces act). Semantics: `members.md`.

### by `position.definedBy`

`definedBy` says which fields the ENGINE uses to orient the member; every position field is
stored whatever the mode, so an **S** cell is a field that is kept and then ignored.

| field | rotationsOfX | directionVector | lcs | unit / values |
|---|---|---|---|---|
| `position.definedBy` | R | R | R | `rotationsOfX`, `directionVector`, `lcs`; `none` or omitted → **X** |
| `position.betaDirection` | Y | S | S | rad |
| `position.gamaPitch` | Y | S | S | rad |
| `position.alphaRotation` | Y | Y | Y | rad — not nullable |
| `position.axisX` | S — all-zero → X | Y — any magnitude, normalised for you; all-zero → X | Y — all-zero → X | reads back normalised |
| `position.offsetEx/Ey/Ez` | Y | Y | Y | m, LOCAL |
| `position.origin`, `axisY`, `axisZ` | F — reported only | F | F | m / — |

With `directionVector` the two angles stop being reported, because the vector supersedes them.
Enum range checks: `members.md`.

### by `position.align`

| field | none | toMemberPlate | toMemberPlateRotateThenTranslate | shape |
|---|---|---|---|---|
| `position.align` | Y | Y | Y | `none`, `toMemberPlate`, `toMemberPlateRotateThenTranslate` |
| `position.alignedPlate` | S — dropped | Y | Y | `{memberId, partType, plateSide}` |
| `position.relatedPlate` | S — dropped | Y | Y | `{memberId, partType, plateSide}` |

`partType` takes 25 values (`topFlange`, `bottomFlange`, `web`, `basePlate`, …); `plateSide`
takes `default`, `lowerSide`, `upperSide`, `bothSides`, `center`. A part type the member lacks
is **X** (`members.md` § `position.align`).

### by `model.forcesIn`

| field | node | position | bolts | selectedMemberFace | unit / values |
|---|---|---|---|---|---|
| `model.forcesIn` | Y | Y | Y | Y | `node`, `position`, `bolts`, `selectedMemberFace` |
| `model.x` | S | Y | S | S | m |
| `model.connectedMemberId` | S | S | S | Y | — |
| `model.modelTypeEnum` | Y | Y | Y | Y | `loadedInXYZ`, `loadedInXZ`, `loadedInXY`, `loadedInXYZ_NoBending` |

### member-level fields

| field | POST | PUT | values | default |
|---|---|---|---|---|
| `crossSectionId` | Y — unknown id → X | Y — not checked (`members.md`) | catalog id | the project's first cross-section |
| `isContinuous` | Y | Y | bool | model-dependent — no fixed default |
| `connectedBy` | Y — non-continuous only; F → `begin` when continuous | ← | `begin`, `end` | `begin` |
| `mirrorY`, `mirrorZ` | Y | Y | bool | `false` |
| `isBearing` | F — the first member added | F — move it with `PUT .../members/{memberId}/set-bearing-member` | bool | — |
| `active` | F | F | bool | true |
| `stiffnessAnalysis.theoreticalLengthY` | Y — either may be sent alone | ← | — | derived from the geometry |
| `stiffnessAnalysis.theoreticalLengthZ` | Y — either may be sent alone | ← | — | derived from the geometry |

`stiffnessAnalysis` is reported back only on a stiffness-analysis connection: `members.md`.

---

## work-plane

An auxiliary plane, invisible in the scene, used as the cutting tool of a `cut` or `plate-cut`.
Two axes: how the plane is defined, and what it is defined relative to. Semantics: `cuts.md`.

### by `method`

| field | byNormalVector | byAngles | byIntersection | unit | default |
|---|---|---|---|---|---|
| `origin` | Y | Y | — | m | the global origin |
| `normalVector` | Y | ? | — | — | the vertical axis |
| `rotationX`, `rotationY`, `rotationZ` | ? | Y | ? | rad | `0.0` each |
| `memberId` | — | — | R | — | — |
| `relatedMemberId` | — | — | R | — | — |
| `offsetX` | X (non-zero) | X (non-zero) | Y | m | 0 |
| `nearIntersection` | X (`true`) | X (`true`) | Y | bool | false |
| `isFatigue` | Y | Y | Y | bool | `false` |

`byAngles` rotates from the global vertical; a rotation that leaves the plane parallel to the
member is **X**.

### by `relatedTo`

| field | joint | member | plate | default |
|---|---|---|---|---|
| `relatedTo` | Y | Y | Y | `joint` |
| `memberId` | — | R | — | — |
| `plateOperationId` | — | — | R | — |
| `plateId` | X | X | X | — |

`plateId` is refused wherever it appears — anchor to the operation that produces the plate.
`relatedTo` changes the FRAME that `origin` and `normalVector` are read in, not the field list:
`cuts.md`.

---

## parameters — by the target property's `valueType`

`GET .../parameters/linkable-properties` gives every target a `valueType`. That value decides
what you must send, and **two targets answer 200 and drive nothing** — with no error at any step.

**Author every parameter as `parameterType: "Expression"`** — it reaches every drivable target.

| `parameterType` | create | drives the model |
|---|---|---|
| `Expression` | Y | Y |
| `Float` · `Bool` · `Int` | Y | Y on a member or operation target of that type; **X** 422 on a `crossSection`, `material` or `boltAssembly` owner |
| `String` | Y | Y on a member or operation target that takes a string (`Css`, `Material`); **X** 422 on a `crossSection`, `material` or `boltAssembly` owner |
| `Material` · `Css` · `Bolt` · `Weld` · `Enum` · `Vector` | **X** 422 *"not supported yet"* | — |

| target `valueType` | expression to send | drives the model? |
|---|---|---|
| `Float` | a number, SI units | Y |
| `Bool` | `true` / `false` | Y |
| `Css` | the library name **quoted**: `'HEA300'` | Y |
| `Material` | the grade name **quoted**: `'S 355'` — note the space | Y on a plate or weld target; **S** on a bolt grid's `Material` (`parameters.md`) |
| operation weld `propId;Size` | a number | Y |
| operation weld `propId;WeldType` | quoted enum name: `'DoubleFillet'`, `'Bevel'` | Y |
| member `Vector` (*Axis X/Y/Z*) | `'X Y Z'`, quoted | Y on a member defined by `lcs`; **S** on one defined by angles |
| member *Model type* (`Enum`) | quoted, the wire value or the app's label: `'loadedInXZ'`, `'N-Vz-My'` | Y; anything else **X** 422 at link, listing the accepted labels |
| cross-section weld (`Top/Bottom flange-web`) | — | **S** |

**Quote every string literal** (`'S 355'`, not `S 355`): the `expression` field is always
evaluated as an expression, so a bare word is 422 *"Error parsing the expression"*. Single and
double quotes both work.

**`validationStatus: "Ok"` does NOT mean the value applied.** A mismatched type IS refused at
link time (422), but a name the project does not hold and a target with no consumer both answer
200 and change nothing. **Read the model back** through a channel that carries the field:
`parameters.md` § *What a 200 promises*.

Read a member target back from `GET .../members/{id}` (`position.axisX/Y/Z`,
`model.modelTypeEnum`). Set every axis an `lcs` member needs: while two linked axes coincide the
GET returns the frame empty. The cross-section weld target does not drive the model.

**The `propId;Sub` sub-path (`;Size`, `;WeldType`, `;Material`) exists only on operations** —
hence **F** on the cross-section weld row.
