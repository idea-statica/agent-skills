# Parameters — drive a model from a named value

**Answers:** creating a design parameter · discovering which properties can be driven ·
linking a parameter to a property and unlinking · updating a value so the model changes ·
what a parameter cannot drive.

**Does NOT answer:** which fields an operation takes → the operation's own page ·
which property types exist per operation kind → `field-matrix.md` ·
the dimensions of a parametric cross-section → `cross-sections.md`, a different and
unrelated thing (sent as `dimensions`, never as a `parameters` list).

A parameter is a named value stored on the connection. Linked to a model property, it drives
that property: change the parameter, the model regenerates. This is how a connection built once
becomes reusable — the desktop's Design tab over HTTP.

```
POST   .../connections/{id}/parameters                    create
GET    .../connections/{id}/parameters                    read — see includeHidden below
PUT    .../connections/{id}/parameters                    update values (collection form)
DELETE .../connections/{id}/parameters                    delete ALL parameters and links
DELETE .../connections/{id}/parameters/{key}              delete one

GET    .../connections/{id}/parameters/linkable-properties          everything drivable
GET    .../connections/{id}/operations/{operationId}/linkable-properties
GET    .../connections/{id}/members/{memberId}/linkable-properties

GET    .../connections/{id}/parameters/links              list links
POST   .../connections/{id}/parameters/links              link
DELETE .../connections/{id}/parameters/links/{linkId}     unlink   -> 204
```

## Create

```json
POST .../parameters
{ "key": "w", "parameterType": "Float", "expression": "0.02", "valueType": "lengthComponent",
  "description": "plate width", "lowerBound": "0.01", "upperBound": "0.05", "isVisible": true }
```

`key`, `parameterType` and `expression` are required — omitted or `null` is 400 naming the
field, an empty `key` 422 *"A parameter identifier is required."* `parameterType` ∈ `Float` ·
`Bool` · `Int` · `String` · `Expression`. Bounds are themselves
expressions (strings), not numbers, set on create; a value outside them warns rather than blocks
the apply.

**Author every parameter as `Expression`** — it reaches every drivable target, including the six
types that cannot be created (`Material`, `Css`, `Bolt`, `Weld`, `Enum`, `Vector`, each 422
*"Parameter type 'X' is not supported yet"*). `String` reaches member and operation targets
only: against a member's Cross-section, `Expression 'HEA260'` and `String 'HEA260'` both move the
member's `crossSectionId` to the project entry that holds HEA260, but a `crossSection`,
`material` or `boltAssembly` owner links only `Expression` (`Float`, `Int`, `Bool` and `String`
are 422, §*What a 200 promises*). Prefer `Expression` because it reaches every target.

Which `parameterType` reaches which target: `field-matrix.md` § parameters. Read it before
choosing a target, not after.

The response is the evaluated parameter, so it tells you at once whether the expression worked:

```json
{ "key": "w", "expression": "0.02", "value": 0.02, "unit": "PlateOrWeldThickness",
  "valueType": "lengthComponent", "parameterType": "Float", "validationStatus": "Ok", "isVisible": true,
  "lowerBound": "0.01", "upperBound": "0.05",
  "parameterValidation": { "lowerBoundEvaluated": 0.01, "upperBoundEvaluated": 0.05,
                           "validationStatus": "Ok", "message": "" } }
```

Bounds and status appear twice — top level and nested — and carry the same values.

**On create, the expression is evaluated before the parameter is stored**, so a bad one is
refused with 422. **A `PUT` is not refused** — it stores the bad expression and answers 200
(§*What a 200 promises*):

```
"1+*2"            422  Expression '1+*2' of parameter 'bad' cannot be evaluated:
                       Error parsing the expression. Parameters available in expressions: [].
"nosuchparam*2"   422  … Parameter nosuchparam not defined. …
```

Two consequences of evaluate-before-store:

- **A dependent parameter must be created driver-first.** `b = a/2` fails while `a` does not exist.
- **A `String` expression needs quotes.** `"S 355"` is a parse error; `"'S 355'"` gives
  `value: "S 355"`. The expression language sees an unquoted word as an identifier.

### Presentation: `valueType`, `isVisible`, `description`

Create takes `key` · `parameterType` · `expression` · `description` · `lowerBound` ·
`upperBound` · `isVisible` · `valueType`. Update (`PUT`) takes `key` · `expression` ·
`description` · `isVisible` · `valueType` and **writes only the fields it names** — an
`expression`-only PUT keeps visibility, value type and label.

- **The parameter's `valueType` says what the number is** (`ConParameterValueType`: `lengthComponent`,
  `plateThickness`, `weldSize`, `angle`, `force`, `wholeNumber`, `boolean`, `text`, …), and the
  app shows the value in that quantity's unit. **The value itself stays SI** — `weldSize` with
  `0.006` is a 6 mm weld. Omitted, it is `generic` with unit `Nothing`; an explicit `generic`
  reads unit `Coeff`.
- **`unit` is read-only and follows `valueType`** (thickness, weld size and component length
  read `PlateOrWeldThickness`, an angle `Angle`, whole number / boolean / text `Nothing`); a sent
  `unit` is ignored.
- **The value type has to suit the parameter type**: `Float` takes `generic` and the decimal
  quantities, `Int` `generic` / `wholeNumber`, `Bool` `generic` / `boolean`, `String` `generic` /
  `text`, `Expression` any of them.
  A mismatch is 422 listing the value types that parameter can have; on create, so is a value
  that does not convert (*"evaluates to 'abc', which a parameter of value type 'wholeNumber'
  cannot hold"*). An unknown `valueType` value is 400. A PUT in which one entry's value type does
  not fit is 422 and writes nothing; **a PUT whose value does not convert, or does not evaluate,
  answers 200 and stores it** (§ What a 200 promises).
- **`isVisible: false` hides the parameter from the default listing** (§ below); a hidden
  parameter still evaluates, feeds other expressions and drives its links.
- **`description` is the label in the app's parameter table.** Keep it to a few words — the
  column is narrow — and leave the unit out of it: `valueType` carries the unit.

## The listing hides part of the model

**`GET .../parameters` returns the visible layer only; `?includeHidden=true` returns all of
them.** A model authored in the application keeps its derived arithmetic hidden and shows only
what a person sets, so reading one without the flag gives a table whose numbers cannot be
reproduced from what it shows. Hidden parameters are otherwise ordinary — readable by name
through `evaluate-expression`, drivable by `PUT`; only the listing is filtered.

**Hide what a person does not enter.** The shape worth copying is the application's: one
visible parameter per quantity a person sets, and the derived arithmetic in hidden parameters
(`isVisible: false`) or in the expressions of the linked ones.

## Writing the expression

Expressions are evaluated by NCalc, and four rules decide whether one parses at all:

| | |
|---|---|
| reference another parameter | **square brackets** — `[width]`, never the bare name |
| join text | **`ToString(a, b, …)`**, `Concat()`, `Join(sep, …)`, `Format(fmt, …)` — `+` does not concatenate |
| numbers | SI, decimal point; or state the unit — `Length(300,'mm')`, `Force(12,'kN')`, `Angle(45,'°')`, also `Area` `Stress` `Moment` `Time` `Temp` |
| literal text | single quotes — `'S 355'` |

Available beyond arithmetic: `Min` `Max` `Abs` `Sqrt` `Pow` `Round` `Ceiling` `Floor`
`Truncate` `Sign`, the trigonometric set, **`RoundWithOffset(value, step)`** (nearest multiple),
the conditionals `if(c,a,b)` / `ifs(c1,v1,…,default)` / `c ? a : b`, and `in(x, …)`.

Spelling is exact: the functions above are PascalCase, `if`, `ifs` and `in` lowercase (`sqrt`,
`max`, `If` fail). `Min` and `Max` take exactly two arguments — nest them for more
(`Max(a, Max(b, c))`). `Round(value, digits)` takes both arguments, and `RoundWithOffset` a step
greater than zero. A failing expression answers a diagnosis-free 500 on `evaluate-expression`;
to learn why, create it as a parameter and read the 422 (§ evaluate-expression).

Full function list: the product's own *Parameter Reference Guide* on the developer site.

### Reading the model inside an expression

Prefer reading a dimension over restating it — a parameter built this way follows the model
when the section changes, and there is one number instead of two that can disagree:

```
GetValue(<memberName>, 'CrossSection.Bounds.Height' | '.Width', <default>)
GetBeamPlateThickness(<memberName>, 'Flange' | 'Web')
GetCrossSectionFormCode(<memberName>)      -> 'I', 'U', 'L', 'Rectangle', 'Circle', …
GetBoltDiameter(<operationName>, <index>)
GetSettingValue(<setting path>)
GetLoadEffectEnvelope(<member>, <action>, <envelope>, <position>)
```

**`GetValue` takes a property PATH, and an unknown path is not an error** — the three-argument
form `GetValue(member, path, default)` returns the default, the two-argument form returns the
string `"Property '<path>' not found"`. That makes a wrong path look like a working one, so **check every path
you use for the first time against a section whose dimensions you know**, and check the
quantity as well as the magnitude: a path can track the model and still answer with a
different property than its name suggests. `evaluate-expression` is the quick way to try one
(note it answers 500 for anything it cannot evaluate — see below).

**A parameter may drive a property its own expression reads only if the value settles** —
applying it once leaves the value it reads unchanged. E.g.
`if(GetValue('COL', 'CrossSection.Bounds.Height', 0) > 0.2, 'HEA200', 'IPE220')` linked to
COL's cross-section (both sections in the project) flips it on every application. `POST links`
refuses such a link with 422 *"… cannot drive property … : The value does not settle: applying
the parameters changes a model property it is evaluated from."*; a `PUT` that makes an existing
link do it is reported like any value the property cannot take (§*What a 200 promises*), with
that message and `(parameter link N)`.

## Discover what can be driven

Never guess a `propertyId`. Ask the owner:

```
GET .../operations/{operationId}/linkable-properties
GET .../members/{memberId}/linkable-properties
GET .../parameters/linkable-properties          every owner at once, each row carrying `owner`
```

```json
{ "propertyId": "151", "name": "Thickness", "group": "Stiffening plate",
  "description": "Thickness of the plate. 0 means, that the thickness is taken from member.",
  "valueType": "Float", "currentValue": 0.01 }
```

The target's catalog `valueType` is the field to match when choosing what to link. Values include: `Float` `Bool` `Int`
`String` `Enum` `Material` `Css` `Vector` `NumberGroups` `Point` `Bolt` — **the set is not closed
and differs per model**, so read it from the catalog rather than from this list. `currentValue`
is absent on many rows, and its absence says nothing about whether the
property is drivable.

**A nonexistent owner answers 404** here (`Operation '9999' was not found in connection '2'.`),
which is what tells a bad id apart from an owner that genuinely offers nothing.

**Ids are per owner, not global, and not always numeric.** `propertyId 151` is Thickness on a
stiffening plate and means something else, or nothing, elsewhere. Real ids include `"IsActive"`,
`"105;Size"`, `"BeamCss"` and `"BoltAssemblySteel"` — treat the id as an opaque string and read
it from the catalog for the owner you are about to link.

## Link, drive, unlink

```json
POST .../parameters/links
{ "parameter": "t", "kind": "operation", "operationId": 2, "propertyId": "151" }
  -> 200 { "id": 1, "parameter": "t", "owner": {...}, "propertyId": "151" }
```

`kind` ∈ `operation` · `member` · `crossSection` · `material` · `boltAssembly` (a value outside
the enum is 400, naming `ConPropertyOwnerKind`). **Every kind takes its owner id** —
`operationId`, `memberId`, `crossSectionId`, `materialId`, `boltAssemblyId` — and it is required;
see below for what each one actually drives.

**Linking applies the value immediately** — no separate call. Then `PUT .../parameters` drives it:

```
POST link (parameter t = 0.02)   ->  IOM plate thickness 0.02
PUT  [{"key":"t","expression":"0.03"}]  ->  0.03
DELETE .../parameters/links/1    ->  204, thickness stays 0.03
PUT  t = 0.05 after unlinking    ->  still 0.03   (unlink leaves the last applied value)
```

`PUT` takes the **collection** form — a JSON array of `{key, expression, …}`. There is no
`PUT .../parameters/{key}`.

One parameter may drive many properties: link `w` to `B1 B2 H1 H2` on two plate operations and a
single `PUT` resizes both stiffeners in one call.

**Once a property is linked, the parameter OWNS it — write to the property directly and the
parameter wins.** Changing a driven property through its own endpoint (a `PUT` on the member,
the operation, whatever normally carries it) answers 200 and leaves the model as it was; the
value you wrote is discarded the moment the parametric model regenerates. E.g. with a
member's cross-section driven by a `Css` parameter, `PUT .../members` with a new
`crossSectionId` leaves `crossSectionId` unchanged and the geometry untouched, while a `PUT` of
the parameter moves both.

The failure this produces looks like a broken endpoint rather than a precedence rule — a
clean 200 with nothing to show for it — so when a write "does not take", **check whether a
parameter drives that property before blaming the route**. To change a driven property, change
its parameter; to take it back, delete the link first (the last applied value stays).

**A parameter with no link drives nothing** — it is a number in the table, and the model keeps
whatever the operation body said. Two habits follow, and both are about keeping ONE source per
quantity:

- **Keep intermediate arithmetic out of the visible table** — in the expression of the linked
  parameter, or in a helper parameter with `isVisible: false`. A visible helper reads as an input
  a person is meant to set.
- **Do not state the same geometry twice through two different inputs.** Where an operation
  accepts both an explicit list and a pattern (a grid's positions vs its rows/columns, say),
  authoring one and then driving the other does not move what you built: the driven input is a
  second, independent definition and the model ends up carrying both. Author with the input the
  parameter can drive, and read the result back to confirm the count did not grow.

  **For a fastener grid this decides how you author it.** The drivable properties are the
  grid's *Rows* and *Positions*; a grid built from an explicit position list does not answer to
  them — the link is accepted, the parameter stores and evaluates, and every later update
  leaves the fasteners exactly where they were. Build a grid whose layout must be parametric
  from the layer inputs instead, and confirm by moving a value and re-reading the positions
  from IOM.

  The value is a **signed coordinate from the grid origin**, not a spacing: `'0.09'` puts one
  line at +0.09. A grid offers `Rows (1)`, which drives the local y lines (`topLayers`), and
  `Positions (1)`, the local x lines (`leftLayers`); bolt-grid and anchor-grid behave the same.

  **The separator decides how a multi-value string is read.** A SPACE continues the chain, so
  each value is a pitch added to the one before; a SEMICOLON starts a new group back at the
  grid origin, so its value is absolute again. Lines on one axis:

  | value | lines |
  |---|---|
  | `'0.06'` | one, at +0.06 |
  | `'0.06; -0.06'` | two, at ±0.06 |
  | `'0.06 0.06'` | two, at 0.06 and 0.12 |
  | `'0.06; 0.06; 0.06'` | one — repeated groups land on the same coordinate |

  **Give each of the two its full signed list**, e.g. `'0.06; -0.06'` for lines on both sides.

  **Change a parameter-driven grid through its parameters.** A GET → PUT of the operation
  rewrites the grid from the typed body, and writing the parameter again does not always undo
  that.
  **Read the fastener count from IOM after any write**, not only after the link.

**The property id is the identity, not its name.** One operation can expose several properties
under the same display name — a plate operation carries a `Thickness` for the plate and another
for its integrated weld — so match on `propertyId` from the catalog. Matching by name silently
links the wrong one, and both answer 200.

Rejections name the problem; these three are decidable from the request:

```
unknown propertyId   422  Property '99999' does not exist on operation 2 in this connection.
unknown parameter    422  Parameter 'nope' does not exist in this connection. Existing parameters: [t2].
unknown owner        422  Property '151' does not exist on operation 9999 in this connection.
```

Note the third: an unknown **owner** on `POST links` is 422, not the 404 the catalog gives.

## What a 200 promises — and how to read the model back

**`POST links` type-checks the value against the target and refuses a mismatch with 422.**
Against a `Bool` target (`IsActive` on an operation):

```
Bool       true      create 200   link 200
Expression true      create 200   link 200
Float      1         create 200   link 422   "cannot drive property 'IsActive' … 1 is not"
Int        1         create 200   link 422   "cannot drive property 'IsActive' … 1 is not"
String     'true'    create 200   link 422   "cannot drive property 'IsActive' … 'true'"
```

On an operation or member target the check is on the **value**, not the declared
`parameterType` — `Expression true` passes because it evaluates to a boolean. **On a
`crossSection`, `material` or `boltAssembly` owner the declared `parameterType` decides
instead:** of the types the API creates only `Expression` links, and `Float`, `Int`, `Bool` and
`String` are 422 whatever their value — *"A String parameter cannot drive a cross-section
property: it is applied for an Expression parameter, which takes the same value. Create 'cs' as
an Expression, or link it to a member or an operation."* (`material` and `bolt-assembly` in
place of `cross-section` on the other two owners). Creating the parameter always answers 200;
the refusal comes at link time.

So a 200 on `POST links` says *the value is acceptable for this target*, still never *applied* —
**read the model back** through a channel that carries the field.

**The update path reports instead of refusing**, deliberately, because a `PUT` carries a set and
one bad value must not reject the rest: `PUT` a value the property cannot take → **200** with
`validationStatus: "Warning"`, `parameterValidation.message` naming the link, and
`failedValidations[]` keyed on the parameter. The model keeps its last valid value. The flag
and the message stay on the parameter — through later PUTs of other parameters and through
save+reopen — until a value the property can take is applied.

**An expression the `PUT` cannot evaluate, or whose value does not convert to the parameter's
`valueType`, is not refused either — and it is quieter.** 200, the expression is stored, and
the failure shows only on the parameter's row in `parameters[]`: `validationStatus: "Warning"`
with the evaluator's error in `parameterValidation.message` (`"Error"` and `setToModel: false`
on a parameter the application set to *Restricted* validation). **`failedValidations[]` does not
list it** — only a linked property that then refuses what it is given adds an entry there.
`expression` reads back the new text, `value` the last value that evaluated. Every later `PUT`
re-evaluates it and lists it in `parameters[]` with that status until it evaluates again; a
`GET` reads the same status. So **check `parameters[].validationStatus` after every `PUT`** — an
empty `failedValidations[]` does not mean every value took. Two cases are not reported even
there — the status reads `"Ok"`: on a `boolean` value type a value that is not already a boolean
(`5` and `'abc'` read back `value: true`), and on `wholeNumber` a fraction (`2.5` is stored as
`2`). Compare `value` with what you sent.

**Check `setToModel` after every `PUT`.** `false` means nothing in the model changed — not even
the parameters whose rows read `"Ok"`: a parameter with *Restricted* validation failed (its row
reads `"Error"`; it is listed in `failedValidations[]` when it is out of its bounds, not when it
does not evaluate). **Every later `PUT` stays unapplied until that parameter is given a value
that passes**, while `GET .../parameters` already shows the new expressions with `"Ok"`; the
first `PUT` that fixes it applies everything that was stored.

**Mind the response SHAPE: the `PUT` takes an array but answers with an OBJECT** —
`{setToModel, parameters[], failedValidations[]}`. The per-parameter rows are one level down,
under `parameters`. Reading the response as if it mirrored the request finds no
`validationStatus` anywhere and reads as "no complaints", which is how a refused value passes
for an accepted one.

**The check keys on the value, so a well-typed value that resolves to nothing still passes.**
Three ways a 200 changes nothing:

- **A name the project does not contain.** `Expression 'HEA200'` on a `Css` target, or a grade on
  a `Material` target, is a valid string for that target — so it is stored, answers 200, and
  changes nothing until the value exists in the project. `POST .../materials/*` it first.
- **A target with no consumer.** A foundation-block property on a connection with no block, or a
  cross-section entry no member points at, answers 200 and cannot move anything — that is the
  model, not a defect. Check the consumer exists before reading silence as a finding.
- **Targets that are genuinely inert.** A bolt/fastener `Material` target refuses an assembly
  name (422 *"Material M20 4.6 not found in material database"*) and accepts-then-drops a grade
  or steel name (200, link stored, `validationStatus: "Ok"`, grade unchanged). The grade IS
  reachable through the same grid's `Bolt`-typed rows.

So: **verify a link by reading the model back** — never from the status code. `200` means
"stored", not "applied".

**Pick the read channel that carries the field, or you will invent a silent failure.**
`export-iom-connection-data` returns welds and concrete blocks as bare `{"id": N}` — **no
material, no type, no geometry** — so anything about a weld read through it looks inert. The
channel that answers is `export-iom` (XML): the weld material is `<WeldData><Material><Id>`
(`0` = automatic; a cut's welds: `welds.md`), `<MatConcrete>` for the block,
`<MaterialBoltGrade>` for a grid's grade. Plate and cross-section materials do come through
connection-data, nested as `material.element.name` with `fy` beside it.

### `NumberGroups` is drivable — it restructures the grid

A bolt grid's `Rows`/`Positions` take the documented `"a1 a2*n"` form and change how many
fasteners there are, not just where they sit:

For example, on the `Rows` of a grid that started with 4 bolts (2 rows × 2 positions):

| parameter | expression | bolts (positions in metres — see below) |
|---|---|---|
| `Expression` | `'0.08 0.06*3 0.08'` | 4 → **10**, rows at 0.08 / 0.14 / 0.20 / 0.26 / 0.34 |
| `Expression` | `'0.3 0.3*1'` | 4 → 4, rows moved to 0.3 / 0.6 |
| `String` | `'0.08 0.06*3 0.08'` (quoted) | 4 → **10**, same as `Expression`; unquoted, the create is 422 |
| `Float` | `0.3` | 4 → **2**, one row at 0.3 |
| `Int` | `1` | 4 → **2**, one row at 1.0 |

**The value is taken verbatim — it is not rescaled, and the number you send is read in the
units the model stores, i.e. METRES.** A fastener coordinate of `0.0943` lands at 94.3 mm; the
same field given `94.3` lands at 94.3 **metres**, builds without complaint, and the model then
carries fasteners or a block hundreds of metres across. This holds for a foundation block's
`Offsets` and a grid's `Rows`/`Positions` alike.

The trap is that the app shows these fields in millimetres, so a value copied off the screen is
a thousand times too big. **Read the result back** — a grid's positions from IOM, a block's
outline from `export-iom` — rather than trusting either unit; the mistake is silent at the wire
and obvious in the geometry.

## `evaluate-expression` — 500 on an undefined name

`POST .../evaluate-expression` takes a bare JSON string and returns the evaluated result as a
string. It answers **500 for any expression it cannot evaluate** — an undefined name and a plain syntax
error alike:

```
"1+1"           200  "2"
"'abc'"         200  "abc"
"Width"         500  Internal server error          <- no parameter named Width
"2 * Width + 5" 500  Internal server error
"1+*2"          500  Internal server error          <- syntax error, no name involved
… after creating Width = 0.2 …
"2 * Width + 5" 200  "5.4"
```

So a 500 here carries no diagnosis — you cannot tell an undefined name from a typo, or either
from a real fault. `POST .../parameters` refuses the same expressions cleanly with **422** and
says which it was, so **create the parameter and read the 422 rather than probing with
evaluate-expression**.

## Two different things the word "cross-section" can mean here

Do not confuse them — one works, the other cannot be addressed at all.

**A `Css`-typed PROPERTY is drivable, and this is the useful case.** A member's *Cross-section*
property takes an `Expression` naming a section, and it moves the model:

Example, in a project where HEA200 is entry 2:

```
member 1 crossSectionId 1  ->  link Expression 'HEA200' to propertyId "1"  ->  crossSectionId 2
```

**The name must already exist in the project** — otherwise 200 and nothing changes; add it with
`POST .../materials/cross-sections` first (see §*What a 200 promises*). `field-matrix.md`
§ parameters lists the expression form for each drivable target `valueType`.

**A crossSection OWNER can be named too, and it does something different.** `kind` is a real enum
— `crossSection`, `material` and `boltAssembly` are accepted alongside `operation` and `member`
(an unknown value is 400 naming `ConPropertyOwnerKind`). These rows come from
`GET .../parameters/linkable-properties`, whose `owner` carries the id.

But understand what you are driving. A `crossSection` owner's `BeamCss` property **rewrites the
project's cross-section entry itself**, not a member's choice of section:

```
project sections   1: HEB200,  2: HEA260        members  1 -> css 1,  2 -> css 1
link Expression 'HEA260' to kind=crossSection, propertyId "BeamCss"   -> 200
project sections   1: HEA260,  2: HEA260        members  1 -> css 1,  2 -> css 1
```

Entry 1 stopped being HEB200. Every member pointing at it changed section without its
`crossSectionId` moving — which is why reading `members[].crossSectionId` shows nothing and looks
like the link did not work. To change **which** section a member uses, drive the member's own
`Cross-section` property instead (`kind: "member"`), as above.

**The owner id IS enforced.** `ConParameterLinkCreate` declares all five owner ids
(`operationId`, `memberId`, `crossSectionId`, `materialId`, `boltAssemblyId`) and an id the
project does not hold is refused by name:

```
crossSectionId 9999    link 422   "Property 'BeamCss' does not exist on cross-section 9999
                                   in this connection."
```

Linking the same property twice is refused too — 422 *"This property is already driven by
parameter 'cs'. Delete that link first."*

**A `material` OWNER is accepted and never satisfiable.** Its rows (`propertyId
"MaterialSteel"`, one per entry of the project's material table) answer 422 *"Material X not
found in material database"* for every name form — short name, full library name, one added
first, **including a name the project already holds**. To change a material, drive a plate/weld/block property on
an operation, or a `crossSection` owner, instead.

**Read the target's catalog `valueType` before you link.** A mismatched value is refused at link time with 422
(§*What a 200 promises*), so the catalog's `valueType` tells you in advance which values that
target will take.
