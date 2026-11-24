# Cross-sections — the outline geometry, and authoring a parametric shape

**Answers:** reading a cross-section's outline as line/arc segments · the 26 parametric shapes and
their dimension names · creating and updating a parametric section · replacing a library
section in place · which endpoint actually carries geometry.

**Does NOT answer:** browsing the library for a NAME
(`GET .../materials/{materialType}/library` with `materialType = cross-sections`, tens of
thousands of entries) → the route is in `endpoints.md`, the `mprlName` create body in `io-shapes.md` §Material ·
assigning a section to a member → `members.md`.

> ⚠️ **Every route on this page is `/api/5`.** The list/create pair
> (`GET`/`POST .../materials/cross-sections`) is on v4 too, where it answers in the older IOM
> shape (below; list shape: `io-shapes.md` § Material); the detail, the library PUT and the whole parametric family are v5 only and
> answer **404** on v4.

```
GET  /api/5/…/materials/cross-sections                        list: id, name, definition per section
POST /api/5/…/materials/cross-sections                        add a library section by mprlName
GET  /api/5/…/materials/cross-sections/{cssId}                detail: id, name, definition (no geometry)
GET  /api/5/…/materials/cross-sections/{cssId}/geometry       the outline on its own
PUT  /api/5/…/materials/cross-sections/library/{cssId}        replace a library section in place
GET  /api/5/…/materials/cross-sections/parametric/shapes      the shape names
GET  /api/5/…/materials/cross-sections/parametric/shapes/{t}  template: dimensions + defaults
POST /api/5/…/materials/cross-sections/parametric             create from dimensions
PUT  /api/5/…/materials/cross-sections/parametric/{cssId}     update dimensions
```

`GET .../parametric/shapes` is the cheapest liveness check for this family — 200 with the shape
list. **A 404 means you are on v4** (or on a service without v5); it does not mean the path is
wrong. Check the version before anything else: `GET /api/5/clients/idea-service-version`
answering while the `/api/4` one also answers tells you both versions are served.

## The one trap: no POST returns geometry

```
POST .../materials/cross-sections   {"mprlName": "HEB300", "materialName": "S 355"}
  -> 200, keys: id, name, definition                                      NO geometry
GET  .../materials/cross-sections/1
  -> 200, keys: id, name, definition                                      NO geometry
GET  .../materials/cross-sections/1/geometry
  -> 200, keys: components                                                the outline
```

Every write and the detail route answer `ConCrossSection` — `id`, `name` and the `definition`
that produced the section — and **no outline at all**. **Read the outline from the `/geometry`
sub-route**; the other responses carry none.

The library POST answers with the id of the entry it created. **Every POST creates a new
entry** — an identical `mprlName` + `materialName` gives a second section with the same name,
there is no find-or-create — and there is **no delete** (`DELETE .../cross-sections/{id}` is
405), so duplicates stay for the life of the project. Keep the id the POST returned, or replace
an existing section in place with the library PUT below.

On **v4** the same POST answers an IOM `CrossSectionParameter` (`crossSectionType`,
`parameters`, `material`, …) carrying the id of the **oldest** section with that `mprlName`;
take the id from the list there, matching name **and** material.

## Replacing a library section — `PUT .../cross-sections/library/{cssId}`

The body is the detail GET's `definition` (its `$type` may stay or be left out):

```json
{ "mprlName": "IPE300", "materialName": "S 355", "mirrorY": false, "mirrorZ": false }
```

- **The id stays, so every member using it follows.**
- **Send both mirror flags** — a flag left out is set to `false`. `mirrorY` flips the outline
  about the section's y axis (its z coordinates change sign), `mirrorZ` about z.
- **`materialName` must name a steel already in the project**, as `GET .../materials/steel`
  lists it or as the detail GET stores it (`S 355~<suffix>` for an edited grade). After
  `change-code` the stored name is still the source steel: set a steel the project now holds
  (`io-shapes.md` § POST /api/5/projects/{projectId}/change-code). A library-only
  grade is 422 *"Material 'S 450' was not found among the project's steel materials…"* —
  `POST .../materials/steel` it first.
- **`mprlName` is matched exactly**, case included: *"Cross-section 'IPE999' was not found in
  the MPRL library for design code ECEN. Use GET materials/cross-sections/library to list the
  available names."* Both `mprlName` and `materialName` are required (422 naming the field).
- **Wrong kind or id:** a parametric or custom section is **409** *"Cross-section '3' is a
  parametric section; this endpoint replaces only library sections."*; the parametric PUT on a
  library section answers the mirror-image 409. An unknown id is **404**. A rejected PUT changes
  nothing and adds nothing.
- A cross-section is shared by the connections, so the change empties the results of every connection (`io-shapes.md` §
  POST …/connections/results) — calculate again.

## Reading the outline

`geometry.components[]`, each `{outline, openings, materialName}`. A component is one closed
region: a welded I gives 3, a general section gives one per plate. `openings` is a list of
closed chains, so a hollow section is a ring rather than a disc.

**Segments, not points.** Every element of `outline` and of an opening is polymorphic on `$type`:

```json
{ "$type": "…ConCssLineSegment, IdeaStatiCa.Api",
  "start": {"y": -0.150, "z": 0.150}, "end": {"y": -0.150, "z": 0.131} }

{ "$type": "…ConCssArcSegment, IdeaStatiCa.Api",
  "start": {"y": -0.150, "z": 0.1311}, "mid": {"y": -0.14997, "z": 0.13103},
  "end":   {"y": -0.1499, "z": 0.1310} }
```

- An arc is **three-point** (`start`, `mid`, `end`), never centre+radius. It maps 1:1 onto
  RhinoCommon's `Arc(Point3d, Point3d, Point3d)`.
- Points are `{y, z}`: a section is a cut in the YZ plane. A consumer drawing in 2D maps y→X, z→Y.
- Coordinates are **absolute, with the origin at the centroid** — not the bounding-box centre.
  E.g. on `RolledLPar` at its template defaults (asymmetric in both axes) the bbox centre is
  (+18.361, +18.540) mm, not 0.
- **The chain is ordered, continuous and closed exactly**: the gap between one segment's `end` and
  the next one's `start`, and the closure of the loop, are both exactly zero. A consumer can walk
  the chain or join it without a tolerance. The order is part of the contract even though the
  schema cannot express it.

For calibration, at the template defaults: `SteelTubeShape` → 4 arcs / 0 lines, R = 50.000 mm
outline and 47.000 mm bore; `RolledRhsPar` → 5 lines + 4 arcs with an outer fillet of exactly
8.000 mm, which is its `InnRadius` 0.005 + `Thickness` 0.003 — the template has no `R` dimension.
A circle is 4 arcs, never a polygon.

## The parametric shapes

`GET .../parametric/shapes` → 26 names. `GET .../parametric/shapes/{shapeType}` → the template,
which **is already a valid POST body** once `materialName` is set:

```json
{ "shapeType": "CFC", "materialName": null,
  "dimensions": [
    {"$type": "…ConCssNumberDimension, IdeaStatiCa.Api", "id": 3, "name": "Width",   "value": 0.05},
    {"$type": "…ConCssSwitchDimension, IdeaStatiCa.Api", "id": 8, "name": "MirrorZ", "value": false} ] }
```

**The `$type` of each dimension says what its `value` holds** — the value is always in `value`:

| `$type` | `value` | example |
|---|---|---|
| `ConCssNumberDimension` | number: a length in metres, an angle in **radians** | `Iw.fT: 0.016`, `RolledIPar.fTaper: 0.0778` |
| `ConCssSwitchDimension` | bool | `Tw.MirrorY: false` |
| `ConCssCountDimension` | integer | `CFRegPolygon.Vertices: 8` |
| `ConCssChoiceDimension` | one of `options[].value` | `BoxDelta.wAlign: "Center"`, options `Center` / `Left` / `Right` |

**Every dimension carries a `name`** — address dimensions by name.

Author from the template: set `materialName`, change the `value`s you want, POST it:

```json
POST .../materials/cross-sections/parametric
{ "shapeType": "CFC", "materialName": "S 355",
  "dimensions": [ {"$type": "…ConCssNumberDimension, IdeaStatiCa.Api", "name": "Width", "value": 0.12}, … ] }
```

The body is the **definition itself**, not an envelope with a `name` — the service assigns the
name from the dimensions (CFC with Width 0.12 comes back as `CFC100x120`). **A dimension left
out is set to its default — on `PUT` too** — so send every dimension, not only the changed ones.
Values go in `dimensions[].value` only: a `parameters` list (`[{"name": "Width", "value": 0.12}]`)
is ignored — 200, section built at the defaults — so check the `value`s in the response.
`shapeType` and `materialName` are required, and `materialName` must name one of the
project's steel materials as `GET .../materials/steel` lists them (`POST .../materials/steel`
a library grade first). `shapeType` omitted or `null` is 400, the `errors` map naming it; the
rest are 422:

```
422  ShapeType is required. Pick one of the shapes that get-parametric-shapes lists.
422  MaterialName is required. Use one of the project's steel materials, as get-materials lists them.
422  Material 'S 450' was not found among the project's steel materials. List them with
     GET materials/steel or add one with POST materials/steel.
```

An unknown dimension name is refused and the message lists the real ones:

```
422  Dimension 'NoSuchDim' is not a dimension of shape 'CFC'.
     Dimensions: Width (3), Height (4), Lip (5), Thickness (6), InnRadius (7), MirrorZ (8, switch).
```

**Every number dimension is range-checked**: lengths, thicknesses and cold-formed radii and lips
1 mm – 20 m, rolled-section radii, box spacings and the `Distance` of `CF2Co` / `CF2Cpo` 0 or
more. **Angles are in radians**, each within its shape's own range: the flange taper `fTaper`
(`RolledIPar`, `RolledUPar`) 0 or more and below π/2 (π/2 itself is 422 *"Height of
cross-section is to small."*); `Lip2Angle` (`CFCp`, `CF2Cpo`) 0 to π/2 (90°), both ends
allowed; the `CFLgen` `Angle` 0 or more and below π (180°); the `SteelCircle` `Alfa` above 0 and
at most π/4 (45°) — a rounded `0.7854` is above it. These are the only angle dimensions; every
other number is a length. A value outside is 422 naming the shape and, except for
`SteelCircle` (*"Incorrect dimension !"*), the limit —
*"The engine rejected the 'Iw' dimensions: Minimal allowable dimension is … [mm]"*. **An angle's
limit is stated in degrees** (*"…from 0 to 180 °"*, *"Flange taper is greater than 90 °."*)
although the value is sent in radians.

`PUT .../parametric/{cssId}` takes the same body. Replaying a definition read from
`GET .../{cssId}` verbatim returns byte-identical geometry (after `change-code`, set its
`materialName` first - above).

## The three definition kinds

`definition.$type` names the kind: **`ConCrossSectionLibraryDefinition`** (`{$type, mprlName,
materialName, mirrorY, mirrorZ}` — what a section added by `mprlName` reads back as),
**`ConCrossSectionParametricDefinition`** (shape + dimensions, above) and
**`ConCrossSectionCustomDefinition`** (below). `POST`/`PUT .../parametric` build a parametric
section only. Send the body as the template comes: no top-level `$type`, a `$type` on every
dimension. A `$type` may stand anywhere among an object's properties. A dimension without
`$type`, or a top-level `$type` naming any kind but the parametric one, is **400** at
deserialisation, not the 422 the dimension errors give.

## The custom (general) definition

Custom sections (`ConCrossSectionCustomDefinition`) read back in the same segment form, one component per plate,
openings nested per component. They are **read-only**: `POST`/`PUT .../parametric` accept a
parametric definition only, and the builder rejects general sections outright. There is no custom
write path.

Their geometry is what the desktop editor stored, which is not always what you would draw. E.g.
where a plate is trimmed against a tube, the tube carries true arcs while
**the plate's trimmed end is short line segments** — the editor bakes a boolean trim into a
polygon when the section is authored. Arcs that were never stored cannot be returned; this is
stored geometry, not tessellation by the endpoint (a parametric shape returns arcs).
