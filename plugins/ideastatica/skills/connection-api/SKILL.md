---
name: connection-api
description: >-
  Use when the user wants a script or agent that works with IDEA StatiCa Connection projects
  (.ideaCon) through the Connection REST API (IdeaStatiCa.ConnectionRestApi.exe, "Connection
  Rest API 5.0"), in Python, C# or any language: open or create a project, add members,
  plates, welds, bolts, anchors and cuts, set load effects and design parameters, run the
  CBFEM calculation, read check results, save PDF reports or the .ideaCon file. Covers the
  ClientId handshake, asynchronous calculation jobs (calculate-async / calculation-jobs
  polling and cancel), cross-section geometry, material names, the design
  code and its steel code edition (AISC LRFD/ASD, EN 1993-1-8 2005/2024, CSA S16), the typed
  operations CRUD (weld, cut, plate-cut, bolt-grid, anchor-grid, pin-grid, contact,
  contact-grid, negative-member, negative-plate, stiffening-member, stiffening-plate,
  work-plane), and a service that does not answer. Triggers on IDEA StatiCa Connection,
  .ideaCon, connection design or check automation, connect-client, or /api/5.
---

# IDEA StatiCa Connection REST API (condensed)

> **How to use this skill.** Read the WHOLE reference page for the area you are touching
> before you write the first request — `plates.md` before placing a plate, `welds.md`
> before authoring a weld, and so on. These pages are short and every line in them
> describes observed behaviour. Skimming for the field name and guessing the rest is how you
> lose an hour rediscovering something written here.
>
> **Swagger gives you the field NAMES; this skill tells you how the service reads them.**
> **Send the exact names from the swagger** — camelCase, except multipart form fields such as
> `ConnectionsToCreate`. Names bind case-insensitively, and a numeric string is read as a number
> in load-effect and typed-operation bodies. A misspelled field is ignored, so it takes its
> default: usually silently (`addedWithoutIssues: true`, a `sectionLoad` component stored as 0 —
> `io-shapes.md` § DTO: ConLoadEffectSectionLoad), sometimes as 400/422 or
> `addedWithoutIssues: false` when that default is invalid. On a PUT, what an omitted field does
> depends on the route (see its section). **Read every write back with its GET.** These are the
> places where a name or a convention is easily sent wrong:
>
> | what you might send | what the service reads | where |
> |---|---|---|
> | `name`, as a GET or POST response carries it | **`mprlName`**, as the create bodies declare it (`ConMprlCrossSection` `{mprlName, materialName}`, `ConMprlElement` `{mprlName}`) — build the body from the swagger, never post a GET result back to a create route | cross-section and every material POST |
> | one spelling of the frame axes | grid `coordinateSystem` takes **`xAxis`/`yAxis`/`zAxis`**, member `position` takes **`axisX`/`axisY`/`axisZ`** | grids vs `ConMemberPosition` |
> | one index base | `onMemberPlateIndex` (added member) is **0-based**, `plateOnMemberIndex` (plate) is **1-based** | `members.md` / `plates.md` |
> | one index base | `plateSubIndex` is **0** in a weld's member operand, **1** in a weld's operation operand (`0` also takes the first plate) and in a cut's `plateOfOperation` operand, read **0-based but never `0`** in a cut's `memberPlate` operand (the member's first wall cannot be selected — `cuts.md`), and differs by operand shape in grids | `field-matrix.md` |
> | `concreteBlockIndex` reads like an index | it is the **operation id** of the block | `plates.md` § `concreteBlock` |
>
> So: **never invent a field, an enum value, a units convention or a behaviour.** If neither
> the swagger nor this skill answers your question, TEST it against the running service and
> report the result — do not fill the gap with a plausible guess. Two failure modes to
> watch for in yourself:
> - *Silent field drops* (above). When a whole group of fields reads back empty, suspect your
>   request before the product.
> - *Unproven oracles.* Before concluding "feature X is broken", check your measure on a
>   case you KNOW works. A number that reads the same in both directions proves nothing.

Local HTTP service automating steel-connection design + CBFEM calculation (same engine
as the desktop Connection app). Provides the stable API plus **typed per-kind operations
CRUD** (13 kinds).

> **IDEA StatiCa calculates; you orchestrate.** Every check result, utilization and verdict
> you report comes from the service's responses: present it as IDEA StatiCa's result
> ("IDEA StatiCa reports …"). Never compute, estimate or extrapolate a check, a resistance or a
> utilization yourself, and never call a connection safe or failing from your own reasoning.
> A result that is missing or `Not calculated` is reported as such, not filled in. A change
> you suggest (a thicker plate, more bolts) is a proposal until IDEA StatiCa has recalculated
> it.

## Service version

> This skill applies to **service 26.1.1.2809** (as `GET /api/5/clients/idea-service-version`
> reports it).
>
> **This skill documents `/api/5`, the current version.** v4 is deprecated but still served; it
> lacks the routes marked **not on v4** in `endpoints.md`, answers the cross-section
> list/create pair in the IOM shape (`cross-sections.md`), and addresses an applied template by
> its library GUID instead of the int `templateId` (`io-shapes.md` § Template).
>
> Where this skill and the running service's swagger disagree, the swagger wins. Where a
> field-level detail in `io-shapes.md` or `field-matrix.md` disagrees with what the service
> does, trust the service and test the request.

| area | behaviour |
|---|---|
| parameter create + link semantics | the owner id is enforced, `String` drives member and operation targets (a cross-section, material or bolt-assembly owner links only `Expression`), a mismatched value is refused at link time with 422, and a `PUT` whose expression does not evaluate is stored at 200 — check `parameters[].validationStatus`; `valueType`, `isVisible` and `description` are written on create and update — `parameters.md` § Presentation |
| parameter that reads its own target | a link whose value does not settle (applying it changes a property its own expression reads) is 422 on `POST links`; a `PUT` that causes it is reported in `failedValidations[]` — `parameters.md` § Reading the model inside an expression |
| added-member placement | the host's direction and roll can move a `rib`, `doubler` or `widener` to another side of the host or turn it; read every `onMember` / `onPlate` added member back from IOM — `members.md` § Added members |
| typed operations availability | all 13 kinds available |
| `steelEdition` (code edition) | readable AND writable on project and connection; only `ecen`/`american`/`canada` have editions; LRFD vs ASD changes the results — `io-shapes.md` § `ConProjectData` |
| project settings | a project created with `POST /projects` or saved by the desktop carries the full set, and every key takes its GET value back — `io-shapes.md` § Settings |
| detailed result rows | every per-element row (`CheckResPlate`, `Weld`, `Bolt`, `Anchor`, `ConcreteBlock`) carries `loadCaseId` — `io-shapes.md` § ConnectionCheckRes |
| design-code conversion | any project converts to any other listed code, unless an operation uses a pin (422) or the project holds a reinforcement or headed-stud material (422 on `change-code`); `ecen` is never a target; `PUT /projects/{projectId}` refuses a different `countryCode` with 422 and points to `change-code` — `io-shapes.md` § Conversion, § PUT /api/5/projects/{projectId} |
| cross-section writes | `PUT .../cross-sections/library/{cssId}` replaces a library section in place, members follow — `cross-sections.md` |
| plate on a concrete block | a wrong `concreteBlockIndex`, a block of a later operation or a surface outside 1..6 is 422 listing what is valid — `plates.md` § `concreteBlock` |
| foundation blocks | `blockType` and `existingBlockOperationId` sit inside `foundationBlock`; an anchor grid requires `foundationBlock` — `grids.md` § anchor-grid specifics; a contact grid without it is a plate-to-plate contact — `grids.md` § "contact-grid / contact / pin-grid" |
| member placement | a `position` with `definedBy: "none"`, or without `definedBy`, is refused with 422, and so is an out-of-range member enum — `members.md` |
| stitched (intermittent) welds | accepted on the `weld` operation only; elsewhere an `intermittent` weld block is 422 unless its `type` is `noWeld` — `welds.md` § Stitched welds |
| required request properties | a body without a required property is 400 naming it — typed operations: `operations.md` § Rules that hold for every typed operation; parameter create: `parameters.md`; `apply-template`: `io-shapes.md` § Template; parametric cross-section `shapeType`: `cross-sections.md` |
| typed operation ids | a PUT or POST whose `id` holds an operation of another kind is 409; a POST with an `id` of the same kind replaces that operation — `operations.md` § Rules that hold for every typed operation |
| IOM import | give each welding material a name no steel material in the container uses, so the imported welds keep it; a new foundation block is at least 2 · embedment depth + 2 · base-plate thickness high; a non-Eurocode container with pins is 422 — `io-shapes.md` § POST /api/5/projects/import-iom-file |
| `export-iom` of a foundation block | `<Length>` / `<Width>` are the plan size along the host plate's local x / y, `<Height>` and `<Depth>` the block's height — `grids.md` § anchor-grid specifics |
| GET → PUT round-trip of operations | an unmodified typed GET re-creates the operation (layer `rows`, catalog ids, an added member's host, `shearLug` and a plate-to-plate contact-grid included); a grid driven by parameters is changed through its parameters — `operations.md` § Rules that hold for every typed operation; the plate editor's edits survive too — `plates.md` |
| fastener grid layers | two lists, `topLayers` and `leftLayers`, with both sides as signed groups — `grids.md` § Orthogonal layers |
| per-template routes | v5 addresses each applied template instance by its int `templateId` (an unknown one is 404), v4 by the library GUID — `io-shapes.md` § Template |
| stored results and reports | a write inside one connection empties that connection's stored results, a write to shared project data (materials, cross-sections, connection names, project, settings) empties every connection's, and so does a parameter that changes a project cross-section; a report reuses a `calculate` of the active load effects made after the last edit — `io-shapes.md` § POST /api/5/projects/{projectId}/connections/results, `endpoints.md` § Report |

These are the version-sensitive areas. If `GET /api/5/clients/idea-service-version` reports an
older service than the one above, check these rows against it before relying on them.

- Base URL `http://localhost:5000`, route prefix `/api/5`. Swagger UI `/index.html`,
  spec `/swagger/5.0/swagger.json` — **the running service's swagger is the source of
  truth**; never invent endpoints, fields, or enum values.
- The user may run the service on another port (`-port=NNNN`): use the address they give. If
  nothing answers, the service is not running — ask the user to start it, do not scan ports
  or guess (`diagnostics.md` § Nothing answers at the base URL). Never restart or stop a
  service the user started. A service holds a license seat while it runs, so if you started
  it yourself, which you do only with the user's consent, stop it when the work is done.
- Stateful and per-client: a project lives in service memory until `close`/disconnect.
- **Multi-project, with per-client project lists**: one ClientId can hold several open
  projects (`GET /api/5/projects` lists its own), and a second ClientId sees `[]` plus **404**
  on the first client's project id. Use one ClientId per process and close only the projects
  you opened (`io-shapes.md` § GET /api/5/projects/{projectId}/close).
- **One calculation per project at a time**; what waits for it and what answers at once:
  `endpoints.md` § Calculation.

## Canonical workflow

```
1. GET  /api/5/clients/connect-client                        -> ClientId (raw GUID string, text/plain)
2. POST /api/5/projects/open   (multipart, field "ideaConFile") -> { projectId, connections[] }
   or POST /api/5/projects     (JSON ConProjectData)            -> empty project (contains default empty CON1 id 1!)
      countryCode picks the design code and decides which library names resolve.
      It is `american` for AISC — NOT "aisc"; full enum in io-shapes.md (ConProjectData).
      `countryCode` picks the CODE; **`steelEdition` picks the edition/method within it**
      (AISC LRFD vs ASD changes the results) and defaults per code — io-shapes.md.
3. GET  .../projects/{projectId}/connections                 -> [ { id (int), name, ... } ]
4. author: cross-sections/materials -> members -> operations -> load effects
5. POST .../connections/calculate    body [connId,...]       -> [ ConResultSummary ]
6. POST .../connections/results      body [connId,...]       -> [ ConnectionCheckRes ] (READS the last calculation — see below)
7. GET  .../connections/{id}/reports/pdf                     -> report bytes
8. GET  .../projects/{projectId}/download                    -> updated .ideaCon bytes
9. GET  .../projects/{projectId}/close
```

**Single-connection and async variants of step 5** — the forms with the connection in the PATH
accept an optional `?loadEffectIds=` subset selector, the body-array forms do not:

```
POST .../connections/{connId}/calculate          -> ConResultSummary (one object, not an array)
POST .../connections/{connId}/rawresults-text    -> raw CBFEM results for that connection
POST .../connections/calculate-async             -> 202 ConCalculationJob   (body [connId,...])
POST .../connections/{connId}/calculate-async    -> 202 ConCalculationJob
GET  .../calculation-jobs/{jobId}                -> status/progress/results (poll until terminal)
DELETE .../calculation-jobs/{jobId}              -> 202, cancel (poll the job until terminal)
```

Job `status` ∈ `queued|running|finished|failed|cancelled`; **409** on start = a job is
already running for that project. What a cancel leaves in each connection and how to recover:
`endpoints.md` § CalculationJobs. Use async for
long/multi-connection runs — it shows progress, can be cancelled and holds no request open; the
synchronous path stays correct for a single quick check.

## Live view in the desktop application (optional)

The user can watch the model in an IDEA StatiCa Connection window that updates after each of
your runs. It applies only when you run commands on the user's Windows computer and the model is
what the user will look at: you build or change a project for them now. It does not apply when
the script is the product (a script to run later, batch reports, reading results). When it
applies, run `python "<this skill's folder>/scripts/live_view.py" status` before the first run
that changes the model. When its `"window"` is not `"open"`, follow the remembered `"mode"`:

- `ask`: ask once per conversation whether to open it, side by side or in its own window, and
  whether to remember the answer;
- `always`: `start --auto` without asking;
- `never`: do not offer it.

While the live view is on, after every run that changed the model, save the `.ideaCon` and `show`
it. **`show` never opens a window. When the user has closed it (exit 3), say so once and do not
start it again until they ask.** The question, the user's later requests, the commands, the exit
codes and what happens to edits made in the window: `reference/live-view.md`.

## Iron rules (violating any of these is the top cause of failures)

1. **`ClientId` header on every request** (except connect-client and
   idea-service-version); its value is the raw GUID from connect-client. The header name is
   case-insensitive. A missing or misspelled header (e.g. `Client-Id`), and a value that is not
   a GUID, → 401 *"Missing ClientId"* (*"The 'ClientId' header is required. Call ConnectClient
   to obtain one."*); a GUID the service did not issue → 401 *"Unknown ClientId"*. No
   JWT/OAuth; local license needed to calculate. **The swagger does not
   declare the header** (no header parameter, no security scheme), so a client generated from it
   sends none — add it to every request yourself.
2. **An omitted `active` defaults to TRUE** — the POST wrapper and a re-GET both report
   `active: true`, for every kind; explicit `active: false` is honored. Still, **send
   `"active": true` explicitly on every operation POST**: it costs one field, it does not
   depend on the default, and an operation silently
   stored inactive looks exactly like a successful add (`addedWithoutIssues: true`, zero
   geometry).
3. **HTTP 200 ≠ success.** POST/PUT of operations return
   `{operation, issues[], addedWithoutIssues}` — check the wrapper. Invalid operations
   are still ADDED and persist through `/download`. And `addedWithoutIssues: true` still
   does not guarantee geometry: most bad inputs are reported — a bad reference (a member,
   material or bolt-assembly id that does not exist) is refused with 422, and geometry that
   cannot be built (zero-area plate, no pairable weld edge, parts too far apart) comes back
   200 with `addedWithoutIssues: false` and a message naming the cause — but a grid sent with
   an empty `userPositions` list is accepted as a clean success and builds no fasteners at
   all. Confirm every add with `GET .../export-iom-connection-data` and count what you
   expected.
   Mind which failure you are looking at: parts that cannot be paired report
   *"Cannot execute the operation." / "Nothing to connect"*, and that message says nothing
   about the positions — with the SAME `connectedParts`, dropping the positions stays a silent
   clean success.
4. **Verify materialization, don't trust responses.** One
   `GET .../export-iom-connection-data` returns counts+positions for plates, welds,
   boltGrids/anchorGrids, concreteBlocks; `GET .../presentations/text` gives the 3D
   scene (solids). Welds appear in both, but **`export-iom-connection-data` gives a weld as a
   bare `{"id": N}` — no type, no size, no parts.** For anything ABOUT a weld use
   `GET .../export-iom`, whose `<WeldData>` carries the whole weld (fields: `reference/welds.md`); the
   scene carries the drawn geometry as one group per weld (`selected.type.kind == "weld"`).
   Bolts appear in IOM (scene shows only holes); a foundation block a grid creates (`blockType:
   "new"`, contact-grid or anchor-grid alike) appears in the IOM export as a concrete-block entry;
   and **a contact rides in
   the weld collection** carrying the operation name — so it is countable everywhere but only
   identifiable in `export-iom`. There is no separate contact collection.
   A NEGATIVE volume is listed in IOM too (`plates[]` / `beams[]`) with `isNegativeObject:
   true` — filter on it before counting material (`plates.md`).
   **But IOM/scene is NOT a complete geometry channel — "nothing there" is NOT proof of a
   no-op.** Before calling something broken: try an ALTERNATE input path, and cross-check the
   GUI — the GUI is the ground truth, IOM is a lossy view of it. Also mind that grid-level
   `length` and per-anchor `anchoringLength` have different sources.
   **IOM is a DESIGN-INTENT model, not a solid one** — this is the root of most "IOM does not
   show it" surprises. In IOM's `ConnectionData` contract a member is a list
   of `PlateData` mid-surface outlines (no volume, no axis), and an operation is stored as its
   RECIPE, not its result — `CutBeamByBeamData` is `{Name, ModifiedObject, CuttingObject,
   Method, Offset, IsWeld}`. Outlines are recomputed after a cut, so counts move, but nothing
   records which fragments form one body. **For how a member was actually dissected, read the
   SCENE**: weld its duplicate vertices by position, take connected components per member
   group, and compare their BOUNDING BOXES — that shows a flange split in two with the gap
   where the tool passed. A component count alone does not (an uncut member already reads as
   one component per wall). `cuts.md` has the worked example.
   **`export-iom-connection-data` is content-negotiated**: the default (no `Accept`, or
   `*/*`, or `application/json`) is **JSON** with camelCase names (`connectionPoint`,
   `beams[]`, `anchorGrids[]`); sending `Accept: application/xml` returns the same data as
   XML with PascalCase element names (`<ConnectionData>`, `AnchorGrid`, `AnchoringLength`).
   Pick one and set `Accept` explicitly rather than relying on your HTTP library's default.
5. **Units are SI everywhere on input**: metres (weld `size: 0.005` = 5 mm), radians,
   newtons. Output: `/calculate` + `/results` pre-scale (MPa, percent);
   `rawresults-text` stays SI (Pa, m, 0..1 ratios) — see `reference/raw-results.md`.
6. **`calculate`/`results` body = bare JSON array of ints** (`[1]`, `[1,2]`) — never a
   single int or an object.
7. **Operation ORDER matters** — an operation cannot reference a later one ("Some
   required member is not specified correctly"). No reorder, **no per-operation DELETE**;
   `DELETE .../operations` wipes ALL operations, the applied templates AND the connection's parameters.
8. **Send ids that came from a live GET/POST.** A catalog id
   that does not exist in the project is **refused with 422**, naming the id and the
   `GET .../materials/...` route that lists the valid ones: `materialId: 999` →
   *"Steel material with id 999 was not found in the project."*, `boltAssemblyId: 999` →
   *"Bolt assembly with id 999 was not found in the project."* Omitting the field, or
   sending `0`, is the documented fallback and still succeeds. On a member PUT, take
   `crossSectionId` from `GET .../materials/cross-sections`: that PUT stores the id unchecked
   (`members.md`).
   A dangling **object** reference behaves differently, because only the engine can judge it:
   a `plateId` that resolves to nothing comes back 200 with `addedWithoutIssues: false` and
   *"Some required member is not specified correctly."* — so read the flag and the issues,
   not just the status.
9. **Author grids with `definedBy: "plate"` — `"coordinateSystem"` is the CAD/IOM import shape
   and is refused for authoring** (`grids.md` §"Grid frame" has the four gates). `plate`
   anchors the pattern to the host plate's own CSYS. Both frames round-trip once stored: the
   typed GET echoes `geometry.userPositions`, the catalog id (`boltAssemblyId` /
   `anchorAssemblyId`) and the frame, and a layer grid reads back its groups in `rows`, so
   GET → edit one field → PUT is safe for position grids and layer grids alike, except a grid
   driven by parameters (`parameters.md`).
   **A layer grid has two lists, `topLayers` and `leftLayers`; put both sides into them as
   signed groups.**
   **Before writing back, assert the body carries the layout the grid was built with** — a
   position grid whose body lost its `userPositions` is emptied. See `reference/grids.md`.
10. **A failed `calculate` returns 200 + `passed: false` + a DIAGNOSTIC `resultSummary`
    row — READ it, then look the message up in `reference/diagnostics.md`**, which maps each
    one to its likely cause and tells you when to fall back on bisection (toggle operations
    `active: false` until the summary comes back).
11. **A member's outer extent (bbox) is NOT an operation-success signal.** IDEA re-measures
    the modeled shell length from the LAST operation (free end re-extends 1.25 × section
    height past a cut face). Judge cuts by voids/cut faces, adds by new groups/IOM counts.
    And when probing placement/frame semantics, test OFF-AXIS (a test anchored to a randomly
    rotated reference) — a global-aligned test can't distinguish "field ignored" from
    "field acts in another frame", and a plane parallel to a member cuts as a silent no-op.
12. **Encodings:** `.contemp` template FILES are UTF-16 (LE, BOM) XML. `export-iom` returns
    UTF-8 bytes whose XML declaration says `utf-16` — decode as UTF-8, then re-encode to
    UTF-16 with BOM before posting to `import-iom-file` (field `containerXmlFile`),
    otherwise the import fails.

## Typed operations — wire contract

```
GET/POST/PUT .../connections/{connId}/operations/{kind}      GET .../operations/{kind}/{operationId}
```

`{kind}` ∈ `weld` `cut` `plate-cut` `bolt-grid` `anchor-grid` `pin-grid` `contact`
`contact-grid` `negative-member` `negative-plate` `stiffening-member` `stiffening-plate`
`work-plane`. PUT targets by body `id` (404 if absent). **An `id` holding an operation of another
kind → 409** on the GET by id, the PUT and a POST, naming both types (*"Operation 1 exists but is
of type 'StiffeningPlateOperation', not 'BoltGridOperation'."*) — retrying won't help; fix the
route, or drop the `id` from a POST. The id rules: `reference/operations.md` § Rules that hold
for every typed operation.
Desktop-authored composite assemblies (a base-plate or end-plate assembly, …) are invisible
to typed GETs and read-only — compose equivalents from primitives instead. DTO tables,
shared building blocks and wire gotchas: `reference/operations.md`.

## Reference routing

Keyed on the question you actually have, not on how the docs are organized.

| you need | read |
|---|---|
| **I am writing a script and need the session working** — connect, open an existing `.ideaCon`, calculate, read results, parameters, load effects, async jobs | **`examples/`** — one runnable Python file per scenario, each with a 1:1 C# mirror except `typed_operations.py`. Open the example BEFORE hand-rolling a session: the ClientId handshake, the `projects/open` path and its `ideaConFile` multipart field are spelled out there and none of them is guessable. The `reference/` pages are not the whole skill. All run as-is; `typed_operations.py` needs no `.ideaCon` — it builds its own model and saves the one the others read |
| **the enum value I am about to send changes which fields are read** (`anchorType`, `cuttingMethod`, `conPlatePositioningType`, `positioningType`, `definedBy`, `weld.type`, `shape`, `method`) — check BEFORE composing a body | `reference/field-matrix.md` |
| **something returned 200 but no geometry / singularity / an HTTP error — debug it** | `reference/diagnostics.md` |
| **the field name or spelling for creating a cross-section, steel, concrete, bolt assembly, pin** (it is `mprlName`, not `name`) | `reference/io-shapes.md` § Material |
| **does this positioning accept a `weld` at all** — plates and added members follow different rules | plates: `reference/plates.md` § "The integrated `weld` block works with only TWO positionings"; added members: `reference/members.md` |
| placing an added member (stiffening-member / negative-member): `length1`/`length2`, `mountType`, `onMember`/`onPlate` | `reference/members.md` |
| placing a joint member: angles, directionVector, mirror, connectedBy, eccentricity, align | `reference/members.md` |
| authoring a **`cut`** — and note `plate-cut` is a DIFFERENT operation with its own value set | `reference/cuts.md` |
| `work-plane`, negative volumes, hollow-section joints | `reference/cuts.md` |
| plate shape and positioning: width/width2, polygonData, negative plates | `reference/plates.md` |
| bolt/anchor/pin/contact grids, userPositions, layer semantics, blocks; **which channel holds which bolt datum** (IFC vs IOM) | `reference/grids.md` |
| welds: where one can exist, edge candidates, typology, verification; `contact` | `reference/welds.md` |
| load effects — forces in N / N·m, `memberLoadings`, which end a member accepts, what a GET echoes | `reference/io-shapes.md` § LoadEffect |
| **which code EDITION the project checks against** (AISC LRFD vs ASD, EN 2005 vs 2024, CSA S16-14 vs S16-19) — and that it changes the results | `reference/io-shapes.md` § `ConProjectData` → `steelEdition` |
| **what a request body or response CONTAINS** (field shapes, per endpoint) | `reference/io-shapes.md` |
| **which ROUTES exist** — paths, methods, parameters, status codes, async jobs | `reference/endpoints.md` |
| typed-operation DTO fields, shared blocks (ConConnectedItem, ConWeldData, positioning, grid geometry), wire gotchas | `reference/operations.md` |
| raw CBFEM results parsing + units | `reference/raw-results.md` |
| **I want to show results ON the geometry** — colour a model by utilisation, join a check result to the solid it belongs to | `reference/raw-results.md` § "Joining results back to the geometry" |
| **I want a parameter to drive a property** — create a parameter, find what is drivable, link it, change the model from one value; and the links that answer 200 and do nothing | `reference/parameters.md` (the per-`valueType` applies/refuses grid stays in `reference/field-matrix.md` § parameters) |
| **I need a cross-section** — its outline as arcs and lines, replacing a library section in place, or authoring one from dimensions (the 26 parametric shapes, the four dimension `$type`s) | `reference/cross-sections.md` |
| common enums (CountryCode, analysis types) | `reference/schemas.md` |
| **the user wants to watch the model in the desktop application** while you work, or closed that window | `reference/live-view.md` (helper `scripts/live_view.py`) |

## Frequently-needed shapes (stable API)

- **Cross-section**: `POST .../projects/{projectId}/materials/cross-sections`
  `{"mprlName": "HEB200", "materialName": "S 355"}` — the field is **`mprlName`, not `name`**;
  the path is PROJECT-SCOPED (unscoped `/api/5/materials/cross-sections` → 404). Note the SPACE
  in "S 355" (material names: below). Wrong mprlName → 422 *"Cross section ... was not found"*.
  **There is NO reuse — every POST adds an entry, even an exactly identical one**, and there is
  no `DELETE` on this route (405), so duplicates accumulate permanently. Keep the `id` the POST
  answers (`{id, name, definition}`), or change an existing section in place with
  `PUT .../cross-sections/library/{cssId}` — `reference/cross-sections.md`.
  **The other material POSTs (pin aside) answer the id of the OLDEST entry with that name**
  while adding a new one — take their ids from the list (`io-shapes.md` § Material).
  Spellings that resolve: `HEB200`, `IPE200`, `UPE200`, `U200`, `L100X50X8`,
  `CHS273.0/12.5` (format `CHS<D>/<t>`), `W12X30` (AISC). **Lookup is exact — case and spaces
  count**: `ipe300` and `CHS 273.0/12.5` are 422, as are a bolt assembly `m16 8.8` and a material
  `S355`. Don't normalise by hand — copy the string out of
  `GET .../materials/cross-sections/library`, which is the only authority.
  One profile can appear under several unrelated spellings there (`CHS273.0/12.5`,
  `CHS CF 219,1x8` and a bare `273.0x10.0` all coexist), so searching by prefix finds one
  family and misses the rest.
  **This POST returns NO geometry** — only id, name and definition. For the outline, read
  `GET /api/5/…/materials/cross-sections/{cssId}/geometry` — **not on v4** (404 there); see `reference/cross-sections.md`.
- **Cross-section from dimensions** (no library name) — **not on v4** (404 there):
  `GET .../parametric/shapes/{shapeType}` returns a template that already is the POST body; set
  `materialName`, edit the `value`s in `dimensions[]`, and
  `POST /api/5/projects/{projectId}/materials/cross-sections/parametric` it. Values go in
  `dimensions[].value` only — anything else (e.g. a `parameters` list) is ignored with 200. The
  response carries no outline; read `GET .../{cssId}/geometry`. `reference/cross-sections.md`.
- **Discovering valid MPRL names**: `GET .../materials/{materialType}/library` returns the
  names the project's design code accepts, for all nine types — `steel`, `concrete`,
  `bolt-grade`, `welding`, `headed-stud-grade`, `reinforcement`, `pin`, `cross-sections`
  (tens of thousands of names) and `bolt-assemblies` (133 on ECEN, 94 on `american`). Look the name up there rather than hardcoding
  it; the steel and bolt-assembly lists differ per design code. Note `GET .../materials/cross-sections` (no
  `/library`) is a different thing — it lists only what the project already contains. See
  `reference/endpoints.md`.
- **Unknown material name → 422 on every material type** — *"Material 'Steel - s 355' was not
  found in material database."* (a pin: *"Pin 'd16' was not found in the pin library…"*). Names match byte for byte: case and spaces count (`S 355`
  resolves; `s 355`, `S355` and `S 355 ` are 422). Copy the name from
  `.../materials/{type}/library`.
- **Member**: `POST .../connections/{id}/members`, body ConMember. First member added
  becomes the bearing member. Honored on add: `name`, `crossSectionId`, `isContinuous`,
  `connectedBy` (`"begin"`/`"end"` lowercase), `mirrorY/Z`, `model`, `position`
  (radians + metres). Geometry change = read member, mutate, `PUT .../members` (full
  object, `id` selects target). Details: `reference/members.md`.
- **Copy is a DEEP copy** (`POST .../connections/{id}/copy`, no body) — inherits ALL
  members/operations. To build separate joints in one project, `POST .../connections`
  `{name}` fresh instead.
- **Member DELETE exists**: `DELETE .../members/{memberId}` removes the member (gone
  from GET and from IOM `beams`; a nonexistent id → 404). No guard on the
  BEARING member: deleting it returns 200 and leaves the connection with no bearing
  member — avoid unless intended.
- **Templates**: two-step — `POST .../get-default-mapping` (field `template`) then
  `POST .../apply-template` (field `connectionTemplate` + the returned mapping; a body without
  either is 400 naming the field). `memberIds` is positional: `[bearingId, attachedId, ...]`.
  Full recipe + parameter-collision traps: `reference/io-shapes.md`.
- **Load effects**: `ConLoadEffect.memberLoadings[]` positions are PascalCase
  `"Begin"`/`"End"`; which end a member accepts is fixed by the first load effect that loads it — later load effects must use the same end(s), a member no load effect has loaded yet takes either, and `DELETE .../load-effects` clears the assignment (`io-shapes.md` § LoadEffect). Omitting a member is not an error; GET the load effect back to see the rows it stored
  (zero rows included). Validation is per member, so a member added after load effects
  already exist can be loaded straight away; a repeated member/position pair in one load
  effect is refused with 422. Author with `"isPercentage": false` and read with
  `?isPercentage=false` (forces N, moments N·m).
  Details: `reference/io-shapes.md` § LoadEffect.
- **Errors**: the ProblemDetails shape; parse by status code, not by media type
  (`reference/schemas.md` § Errors). 401 = ClientId; 404 = project closed / other
  client session; 409 = an operation id of another kind, or a `calculate-async` while a job
  runs; 422 = validation; 400 with an `errors` map = model binding — ignore
  the misleading top-level `"request": ["The request field is required."]` entry, the
  real cause is the OTHER key.

## Examples (`examples/`)

Each scenario exists in Python (`*.py`, `requests`) and a 1:1 C# mirror
(`csharp_*.cs`, `HttpClient`, .NET 5+), except `typed_operations.py` (Python only):

- `quickstart` — full session: connect → open → calculate → summary → PDF report →
  download → close.
- `typed_operations.py` — build one connection that uses all 13 typed operation kinds
  (column base with anchors on a concrete block, bolted end plate, stiffeners with contacts,
  doublers with a pin, a bracket, openings), read wall and plate orientation back from IOM,
  edit one operation with GET → PUT, calculate and save `typed_ops_demo.ideaCon` — the model
  the other examples run against.
- `detailed_results` — `POST .../results`: walk ConnectionCheckRes (must calculate
  first, same session).
- `parameters` — read IdeaParameters, create one and link it to a plate thickness (when the
  model has a plate operation), PUT updates by Key, evaluate-expression, recalculate.
- `load_effects` — members → post/update ConLoadEffect (n/vy/vz/mx/my/mz), settings,
  load extremes, calculate.
- `async_calculation` — asynchronous calculation with job polling
  (`calculate-async` → `calculation-jobs/{jobId}` → cancel), and the `?loadEffectIds=`
  subset selector on both the async and the synchronous single-connection endpoints.
- `batch_report_and_cost` — calculate all connections via an async job, ConProductionCost,
  multi-connection PDF/Word reports.
- `raw_results` — rawresults-text: parse the double-encoded JSON, convert raw SI to
  GUI units (Pa→MPa, m→mm, ratio→%).
