# Connection REST API — request/response I/O shapes

Per-endpoint request and response structures, with **real DTO field names** (not the
OpenAPI `string`/`object` placeholders). Field names shown are the **camelCase JSON** form
emitted by the service.

> The **live `swagger.json` is the final source of truth** for what a type *contains*; this
> page is the source of truth for **what a field is actually called and read as** — e.g. a
> create body takes `mprlName` while the response carries `name`. Re-verify against the running
> service before depending on a field.

**This page is long — go straight to your section.** Every section, in file order:

| section | what you come here for |
|---|---|
| Serialization rules · Auth & errors | camelCase, `$type`, opaque ids, ProblemDetails |
| Client | `connect-client` handshake, service version |
| Project | open / create / download / close, `ConProjectData` |
| Connection | list, copy, topology, analysis type |
| Member | `ConMember` request/response, `set-bearing-member` |
| LoadEffect | `ConLoadEffect`, `memberLoadings`, `sectionLoad`, settings, extremes |
| Calculation | calculate / results / async jobs / raw results |
| Operation | the typed CRUD envelope, the `operations` collection |
| **Material** | **the field NAMES and spellings for creating a cross-section, steel, concrete, bolt assembly, bolt grade, pin, welding — `mprlName` lives here** |
| Parameter | read/write parameters, `evaluate-expression` |
| Template | `get-default-mapping` → `apply-template`, explode, defaults |
| ConnectionLibrary | design sets, templates, pictures |
| Conversion | converting a project to another design code: `get-default-mapping`, `change-code` |
| Export | `export-iom`, `export-iom-connection-data`, `export-ifc`, `export-dwg` |
| Report | html / word / pdf |
| Settings | connection and load settings |
| Presentation | scene and text presentations |

**This page vs `endpoints.md`:** this one is **field shapes** — what a body and a response
contain. `endpoints.md` is **paths and per-endpoint behaviour** — which routes exist, their
methods, parameters and status codes. Need a field name → here. Need a route → there.

**Does NOT answer:** what a field *means* geometrically → `members.md`, `plates.md`,
`cuts.md`, `grids.md`, `welds.md` · whether a field applies for the enum value you are sending
→ `field-matrix.md` · debugging a 200 that did nothing → `diagnostics.md`.

## Serialization rules (apply to every JSON response)
- JSON property names are **camelCase**.
- Enums serialize as **camelCase strings**.
- Polymorphic types carry a **`$type`** discriminator.
- Dictionaries keyed by an integer id serialize with **string keys**; those ids are
  **opaque solver ids** — they may not start at 1 and may have gaps. Never treat them as
  array indices.
- Cyclic references are dropped (not errored).

## Auth & errors (every endpoint)
- All endpoints except `connect-client` / `idea-service-version` require the
  **`ClientId`** header (raw GUID from `GET /api/5/clients/connect-client`). Missing → 401
  (SKILL.md rule 1).
- Error bodies follow the `ProblemDetails` shape (`status`, `title`, `detail`); the media type
  depends on the status, so parse by status code — `schemas.md` § Errors.

---


## Client

Client/session bootstrap endpoints. These are the only two endpoints in the API that do **not** require the `ClientId` header. `connect-client` is how you obtain the `ClientId` value that every other endpoint requires.


Both responses are plain serialized **strings**, not JSON objects — there is no DTO to resolve. on success the HTTP body is just the raw string value.

### GET /api/5/clients/connect-client

Connects a client to the service and returns a unique identifier (the `ClientId`).

- **ClientId / params needed:** None — this endpoint is anonymous. No query/path params, no request body.
- **Request body:** none.
- **Response (200):** `Content-Type: text/plain`. Body is a single `string` — a freshly issued client id in GUID string form. This is the raw GUID, e.g. `f5a3c2b1-9d4e-4a7c-8b21-0e6f9a2c1d33` (default .NET Guid "D" format: 32 hex digits in 8-4-4-4-12 groups, lowercase, no braces). Pass this value verbatim as the `ClientId` header on all subsequent requests.
- **DO NOT JSON-parse this response.** The GUID is emitted UNQUOTED as `text/plain; charset=utf-8` — sending `Accept: application/json` does not change it. `json.loads()` / `resp.json()` throws on the very first call of a hand-written client. Read the body as text and strip whitespace; if you must be tolerant, strip surrounding quotes too in case the content type is ever negotiated.
- **Errors:** `500` returns `ProblemDetails` (standard ASP.NET problem-details JSON).

### GET /api/5/clients/idea-service-version

Gets the service version (swagger summary: *"Gets the IdeaStatica API assembly version."*).

- **ClientId / params needed:** None — this endpoint is anonymous. No params, no request body.
- **Request body:** none.
- **Response (200):** `Content-Type: application/json`. Body is a `string` (a JSON-quoted string) holding the service version as `Major.Minor.Build.Revision`, with the revision zero-padded to 4 digits. Example: `"24.1.5.0042"`.
- **Errors:** `500` returns `ProblemDetails` when the version cannot be determined.

Note: V1/V2/V3 of both endpoints exist but are deprecated; the `/api/5/...` routes are current.


---

## Project

Endpoints for managing IDEA Connection projects (open/create/import from IOM, read, update metadata, download, close). Base path `http://localhost:5000/api/5`. Every endpoint requires the `ClientId` header (raw GUID from `GET /api/5/clients/connect-client`).

All JSON property names below are camelCase; enums serialize as camelCase strings.

### Shared response DTO: `ConProject`

Returned by `open`, `POST /projects` (create), `GET /projects/{projectId}`, `PUT /projects/{projectId}`, `import-iom-file`, `update-iom-file`; `GET /projects` returns an array of it.


| JSON field | Type | Notes |
|---|---|---|
| `projectId` | string (uuid) | Unique id of the opened project, assigned by the REST API on upload/create. Use it in subsequent `{projectId}` routes. |
| `projectInfo` | `ConProjectData` | Project metadata (see below). |
| `connections` | `array<ConConnection>` | Connections contained in the project. |

#### DTO: `ConProjectData`


| JSON field | Type | Notes |
|---|---|---|
| `name` | string | Project name. |
| `description` | string | Project description. |
| `projectNumber` | string | Project number. |
| `author` | string | Author name. |
| `countryCode` | `CountryCode` (enum) | Design code. Defaults to `ecen`. Serialized lowercase. Values: `none`, `ecen`, `india`, `sia`, `american`, `canada`, `australia`, `rus`, `chn`, `hkg` — `sia` is in the enum but refused (§ POST /projects). (Input binding is case-insensitive, but the RETURNED value is lowercase.) |
| `steelEdition` | `ConSteelCodeEditionEnum` (enum) | The edition/method WITHIN the design code — see below. Readable and writable. |
| `date` | string (date-time) | Project date. |

##### `steelEdition` — the code edition IS settable over REST

`countryCode` picks the design code; `steelEdition` picks the edition and (for AISC) the
design method within it. It is carried on **both** `ConProjectData` and `ConConnection`, and
is accepted by `PUT /projects/{projectId}` and `PUT .../connections/{connectionId}`. A
project-level PUT propagates the value to every connection in the response; a connection-level
PUT sets that one connection only. **Read it from `GET /projects/{projectId}`** (or the
connection routes) — the project list `GET /projects` reports `NotSpecified` on the project and
on every connection, whatever is set.

`ConSteelCodeEditionEnum` (11 values): `NotSpecified`, `AISC_360_10_LRFD`, `AISC_360_10_ASD`,
`AISC_360_16_LRFD`, `AISC_360_16_ASD`, `AISC_360_22_LRFD`, `AISC_360_22_ASD`, `CSA_S16_14`,
`CSA_S16_19`, `EN_1993_1_8_2005`, `EN_1993_1_8_2024`.

**Only three design codes carry an edition:**

| `countryCode` | default on create | editions accepted |
|---|---|---|
| `ecen` | `EN_1993_1_8_2005` | `EN_1993_1_8_2005`, `EN_1993_1_8_2024` |
| `american` | `AISC_360_16_LRFD` | all six AISC (360-10/16/22 × LRFD/ASD) |
| `canada` | `CSA_S16_14` | `CSA_S16_14`, `CSA_S16_19` |
| `australia` `rus` `chn` `india` `hkg` | `NotSpecified` | none — only `NotSpecified` |

Every other combination is **422** naming the edition, the connection and the code:
*"Steel code edition 'AISC_360_22_LRFD' is not valid for connection(s) 'CON1' (ECEN)."*
A value outside the enum is **400** (model binding), carrying the same misleading
`"projectData": ["The projectData field is required."]` entry documented under *Errors* —
read the `steelEdition` key instead.

**`NotSpecified` is not a reset.** On a code that has editions it is accepted with 200 and
keeps the edition that was already set (the response echoes it). It reads back on the
five codes that have no editions, and as the **project's** edition when its connections carry
different editions — read each connection's own value then. A connection added to such a
project gets the code's default; one added while all connections agree gets their edition.

**It changes the CALCULATION, not just the metadata** — so it is not a cosmetic field.
**LRFD vs ASD changes the results**: the bolt utilisation scales by about 1.5 (the φ/Ω step),
and the verdict can flip. Within one method the edition YEAR (AISC 360-10/16/22, EN 1993-1-8
2005/2024) can give identical numbers for a joint that uses no clause that changed between the
editions — so identical results on one joint do not show that the year has no effect.

#### DTO: `ConConnection`


| JSON field | Type | Notes |
|---|---|---|
| `id` | int | Connection id (opaque solver id). |
| `identifier` | string | Connection identifier. |
| `name` | string | Connection name. |
| `description` | string | Connection description. |
| `analysisType` | `ConAnalysisTypeEnum` (enum) | camelCase string. Values: `stress_Strain`, `stiffness`, `capacity_Design`, `fatigues`, `total_Design`, `horizontalTying`, `capacityLoadLevels`, `fireRestance`, `buckling`. **`buckling` is in the enum but refused on write** — 422 *"Buckling is not supported analysis type. To enable please set 'IncludeBuckling'"*; use the `includeBuckling` flag instead. `capacity_Design` and `horizontalTying` are accepted but calculate a dedicated load effect that only the desktop adds (`schemas.md`). |
| `includeBuckling` | bool | Whether buckling analysis is included. |
| `steelEdition` | `ConSteelCodeEditionEnum` (enum) | Per-connection code edition; same enum and same 422 gate as on `ConProjectData` above. Set per connection with `PUT .../connections/{connectionId}`, in the full body (§ PUT /api/5/projects/{projectId}/connections/{connectionId}). |

---

### POST /api/5/projects/open

Opens an existing `.ideaCon` project from an uploaded file.

- Consumes `multipart/form-data`. Single binary form field `ideaConFile` = the `.ideaCon` file bytes. Send the part with real `.ideaCon` bytes — a zero-length part is not accepted. Omit the part and the request is rejected with 400 ("The ideaConFile field is required."); send a JSON body instead of multipart and it is 415.
- Header: `ClientId` required.
- Response 200 `application/json`: `ConProject` (the project is uploaded into the service cache; `projectId` in the response identifies it for later calls).


### GET /api/5/projects

Lists the projects currently opened in the service by this client.

- Header: `ClientId` required. No params.
- Response 200 `application/json`: array of `ConProject`. Use it to find a project; its
  `steelEdition` and `analysisType` are placeholders (`NotSpecified`, `stress_Strain`) — read both
  from `GET /api/5/projects/{projectId}`.


### POST /api/5/projects

Creates a new IDEA Connection project. The project is NOT empty of connections — it comes
with a default empty connection `CON1` (id 1).

- Header: `ClientId` required.
- Request body `application/json`: `ConProjectData`. **The fields are all optional, but the
  body itself is REQUIRED** — you must send at least `{}` with `Content-Type: application/json`.
  A missing body → 400 "A non-empty request body is required." / "The projectData field is
  required."; no `Content-Type` at all → 415. (Empty `{}` succeeds and applies defaults.)
  `countryCode` selects the design code; defaults to `ecen` (wire value, lowercase) when
  omitted or `none`. **The enum is wider than the product**: the desktop offers eight codes —
  EN, AISC/ACI, CSA, AS, SP, GB, IS, HKG — i.e. the wire values `ecen`, `american`, `canada`,
  `australia`, `rus`, `chn`, `india`, `hkg`. All eight create a project and resolve their own
  material libraries; **`sia` is in the enum but not in the product and is refused with 422**
  — *"Design code 'SIA' is not supported by IDEA StatiCa Connection. Supported design codes
  are: ECEN, American, Canada, Australia, RUS, CHN, India, HKG."* Treat the eight as the
  usable set and do not read enum membership as support; that detail string is the
  authoritative runtime list. `none` is accepted and silently resolves to `ecen`. Any string
  outside the enum is rejected with 400 as an unconvertible value; a numeric value outside the
  supported set is rejected with 422 whose detail lists the valid codes.
- Response 200 `application/json`: `ConProject`, `connections` = `[{ id: 1, name: "CON1", … }]`.
  The response also carries `steelEdition` on both `projectInfo` and every connection, set to
  the code's default (`ecen` → `EN_1993_1_8_2005`, `american` → `AISC_360_16_LRFD`,
  `canada` → `CSA_S16_14`, the rest `NotSpecified`).


### GET /api/5/projects/{projectId}

Gets the data of an opened project.

- Path param `projectId` (Guid, the id returned when the project was opened/created).
- Header: `ClientId` required.
- Response 200 `application/json`: `ConProject`. 404 if the project is not in this client's cache.


### PUT /api/5/projects/{projectId}

Updates the project metadata (`ConProjectData`).

- Path param `projectId` (Guid). Header `ClientId` required. Project-locked during the update.
- Request body `application/json`: `ConProjectData`. Only the fields you send are applied: `date` (if set), `projectNumber`, `description`, `author`, `name` (if non-empty). A field left out keeps its stored value — `{"name": "x"}` renames the project and keeps its design code and date.
- **`countryCode` must be left out, `none`, or the project's own code.** Another supported code is **422** and nothing is applied (*"The design code of a project cannot be changed from 'ECEN' to 'American' by updating its data. …"*): convert with `POST .../change-code` (§ Conversion; `ecen` is not a target, so create a new EN project). An unsupported code (`sia`, a number outside the set) is 422 listing the supported codes.
- **`steelEdition` is applied here too**; an edition invalid for the project's code is **422** and refuses the whole PUT. The update propagates to every connection in the response. See `ConProjectData` § `steelEdition` for the per-code matrix.
- Response 200 `application/json`: `ConProject` (updated).


### GET /api/5/projects/{projectId}/download

Downloads the current project as a binary `.ideaCon` file, including all changes made by previous API calls.

- Path param `projectId` (Guid). Header `ClientId` required. Project-locked during download.
- Response 200: binary file stream, `Content-Type: application/octet-stream`, `Content-Disposition` filename `ConRestApi_<yyyyMMddHHmmss>.ideacon`. This is the raw IdeaCon project file, not JSON.


### GET /api/5/projects/{projectId}/close

Closes the project and releases its resources from the service cache.

- Path param `projectId` (Guid). Header `ClientId` required.
- Response: 204 No Content — on success AND when the project is not found (idempotent; a 2nd close or a random projectId also returns 204). Swagger declares a 404 for close but the runtime never emits it.
- **Close only the projects your client opened.** `close` answers 204 from any ClientId: a client can close a project another client opened, and the owning client then gets 404 on that project id and on its own project list (`GET /api/5/projects`) for the rest of its session; its other projects stay reachable by id. Use one ClientId per process.


### POST /api/5/projects/import-iom-file

Creates a new IDEA Connection project from an IOM (IdeaRS.OpenModel `OpenModelContainer`) supplied as an XML file.

- Consumes `multipart/form-data`. **Two flat, sibling form fields (no nested `options` wrapper)**:
  - `containerXmlFile` (binary): the `OpenModelContainer` serialized to XML. Omit the part and the request is rejected with 400 ("The containerXmlFile field is required."); send XML whose root element is neither `OpenModelContainer` nor `OpenModel` and it is rejected with 422 naming the element it found.
  - `ConnectionsToCreate` (`array<int32>`, PascalCase as the swagger declares it — send it so): list of connection-point ids to import.
- Header: `ClientId` required.
- **Give each welding material a name that no steel material in the container uses, then
  import.** An imported weld keeps the welding material its IOM names when that name differs
  from every steel material name in the container. When a welding material and a steel share a
  name (e.g. both `S 355`, as a desktop export often has), the imported welds reference the
  steel of that name instead (the typed GET's `weld.materialId` is the steel's id): a re-export
  carries `<Material><Id>0</Id>` on them, and the calculation takes most
  welds' strength from the connected plates (`governingMaterialSource: connectedPlates`). Check
  `governingMaterialSource` in `rawresults-text` after the import.
- **A NEW foundation block's height is raised to max(the height in the container, 2 · embedment
  depth + 2 · base-plate thickness)**, and the block is re-centred on the plate with its plan
  size kept. The typed GET `foundationBlock.height` and the `export-iom` `<Height>` / `<Depth>`
  carry the raised value. Opening a `.ideaCon` keeps the stored height.
- **Pins are Eurocode-only**: a container of any other design code that holds a pin grid is 422
  *"Pins are only available for the ECEN design code, so a model in design code 'Australia'
  cannot bring them into a project. Pins in the model: D24."* and no project is created.
  `update-iom-file` applies the same rule.
- **Load effects come from the container's results** (`OpenModelResult`, as `export-iom` writes it).
  Each loading is stored at the end the member is NOT connected by — `connectedBy: "begin"` →
  `End`, `"end"` → `Begin`; a continuous member gets a row at each end, the loaded end with its
  values and the other with zeros. A loading that changes end arrives with all six components
  negated, and the imported model calculates the same results as the exported one. A container
  without results gives a project with no load effects.
- Response 200 `application/json`: `ConProject`.


### POST /api/5/projects/{projectId}/update-iom-file

Updates an existing project from an `OpenModelContainer` (model and results) supplied as XML.

- Path param `projectId` (Guid). Header `ClientId` required. Project-locked.
- Consumes `multipart/form-data`. Form field `containerXmlFile` (binary): `OpenModelContainer` serialized to XML. Omit the part and the request is rejected with 400 ("The containerXmlFile field is required."). The XML is auto-upgraded to the current IOM version.
- **The XML's connection point id picks the connection.** The connection of that id is rebuilt
  from the XML; every other connection, the project data and the settings stay as they were. An id
  the project does not hold adds a new connection. `export-iom` writes the connection's own id, so
  its XML updates the connection it was exported from — for an exported copy, the copy.
- Scope of the update: the **geometry** of that connection — members, cross-sections and their names are taken from the XML; the rebuilt connection is renamed after its members. **The load effects come from the XML's results when it carries them**, mapped to the member ends as on `import-iom-file` (§ POST /api/5/projects/import-iom-file); an XML without results leaves the connection's load effects as they were. Kept either way: per-member settings (bearing member, model type, forces-in) and the steel code edition; a new connection takes the edition the existing ones share (the code default when they differ).
- The rebuilt connection gets new material entries and new cross-section entries where no earlier import left a matching one (the XML's ids are local to it); entries it used before stay in the project unused. It empties the stored results of every connection (§ POST /api/5/projects/{projectId}/connections/results) — calculate again.
- **422**: an XML of another design code than the project's (*"The container is American but the project is ECEN…"* — import it as a new project), a non-Eurocode container with a pin grid (§ import-iom-file), a container without a model, or a model that cannot be imported; the project is unchanged.
- Response 200 `application/json`: `ConProject` (updated).



---

## Connection

Endpoints for managing the connections inside an opened project. All endpoints require the `ClientId` header (raw GUID from `GET /api/5/clients/connect-client`). `projectId` is a GUID path segment; `connectionId` is an integer (the opaque CBFEM/solver connection id, not necessarily 1-based). Responses are camelCase JSON; enums serialize as camelCase strings. Mutating endpoints (POST/PUT/DELETE) take a project lock.


### GET /api/5/projects/{projectId}/connections
Returns all connections in the project as `array<ConConnection>`. No body. (404 if project not found.)

### POST /api/5/projects/{projectId}/connections
Creates a new empty connection. Query param `name` (optional string); if empty, the name defaults to `CON{newId}`. The new connection inherits the project design code. Returns the created `ConConnection`. 422 if the name already exists in the project.

### GET /api/5/projects/{projectId}/connections/{connectionId}
Returns one `ConConnection`. 404 if the connection id is not in the project.

### DELETE /api/5/projects/{projectId}/connections/{connectionId}
Removes the connection and returns the remaining connections as `array<ConConnection>`.

### PUT /api/5/projects/{projectId}/connections/{connectionId}
Updates a connection. Request body is a `ConConnection`. **Send the full body from a GET with your change.** The PUT applies `name`, `description`, `analysisType`, `includeBuckling` and `steelEdition`; a field omitted from the body is reset — `name` and `description` become null, `analysisType` becomes `stress_Strain`, `includeBuckling` becomes false — except `steelEdition`, which is kept. `id` and `identifier` from the body are ignored. (The project PUT keeps omitted fields — § PUT /api/5/projects/{projectId}.) The calculation state is not a connection field: read it from `POST .../connections/results`. Returns the updated `ConConnection`. It empties this connection's stored results, and a rename those of every connection (§ POST /api/5/projects/{projectId}/connections/results), so set name, analysis type and buckling before you calculate. **`includeBuckling: true` is accepted only with `stress_Strain`, `capacity_Design` and `fireRestance`**; with any other analysis type the PUT is 422 *"Buckling analysis is not supported for analysis type 'Stiffness'. It can be included only with 'Stress_Strain', 'Capacity_Design', 'FireRestance'; set 'IncludeBuckling' to false."* and nothing is written.

### POST /api/5/projects/{projectId}/connections/{connectionId}/copy
Copies an existing connection. Query param `name` (optional string); if empty, a unique name is derived from the source name (incrementing trailing digits). The copy gets a new id and a new internal GUID. Returns the new `ConConnection`. 422 if the supplied name already exists; 404 if the source connection is missing.

### GET /api/5/projects/{projectId}/connections/{connectionId}/production-cost
Returns `ConProductionCost`.

### GET /api/5/projects/{projectId}/connections/{connectionId}/get-topology
Returns `text/plain` — an indented JSON string of a topology object. Parse the string as JSON; the shape is documented below. **Property names are camelCase**, as everywhere else — note the misspelled key `lcsRotatiton` (sic).

---

### DTO: ConConnection

Fields: the `ConConnection` table under § `ConProjectData` above (it includes `steelEdition`).

`ConAnalysisTypeEnum` values (camelCase in JSON): `stress_Strain`, `stiffness`, `capacity_Design`, `fatigues`, `total_Design`, `horizontalTying`, `capacityLoadLevels`, `fireRestance`, `buckling`.

### DTO: ConProductionCost

| Field | Type | Notes |
|---|---|---|
| totalEstimatedCost | double | |

### get-topology payload

| Field | Type | Notes |
|---|---|---|
| `bearingMember` | object | The main bearing member (fields below) |
| `connectedMembers` | array<object> | Members supported by the bearing member (fields below) |
| `typologyCode` | string | e.g. "X+;Y+" |
| `typologyCode_V2` | string | e.g. "C;EX+;EY+" |

`bearingMember`: `operationId` (int), `order` (int), `inclination` (double, radians, rounded to nearest 10 deg), `continuityType` (enum: `ended`, `continuous`), `cssMetaData` (object, below), `rigidity` (enum, e.g. `notSpecified`), `staticBehaviour` (int).

Each `connectedMembers` entry: `operationId` (int), `typologicalSectorCode` (int), `order` (int), `lcsRotatiton` (double, note spelling), `continuityType` (enum), `cssMetaData` (object), `rigidity` (enum), `dirRelatedToBearing` (enum, e.g. `primaryAxis`), `staticBehaviour` (int).

`cssMetaData`: `arcSegmentCount` (int), `cssClass` (enum, e.g. `rectangle`), `cssSize` (`{width, height}`), `integralityType` (enum, e.g. `one`), `label` (string, e.g. "HEA200"), `mainSegmentCount` (int), `shape` (enum: `open`/`closed`), `type` (string, e.g. `RolledI`, CHS, RHS), `formCode` (enum, the manufactured shape, e.g. `i`).


---

## Member

Endpoints for inspecting and editing the structural members (beams/columns) that meet at a connection. All endpoints require the `ClientId` header. `projectId` is a GUID string, `connectionId` and `memberId` are integers. The `connectionId` and `memberId` values are opaque CBFEM/solver ids (may not start at 1, may have gaps) — get them from the `GET .../members` listing rather than assuming sequential numbering.

All five endpoints exchange the same `ConMember` DTO (see the shared DTO block below). Responses are camelCase; enums serialize as camelCase strings.

### GET /api/5/projects/{projectId}/connections/{connectionId}/members
Gets all members in the connection.
- Params: `projectId` (path, GUID string), `connectionId` (path, int).
- Request body: none.
- Response 200: `array<ConMember>`. The server populates `position`, `model`, and (only when the connection's analysis type is `stiffness`) `stiffnessAnalysis` on each item. Members that fail to read are silently skipped.
- Errors: 401, 404, 500.

### POST /api/5/projects/{projectId}/connections/{connectionId}/members
Adds a new member to the connection.
- Params: `projectId` (path), `connectionId` (path).
- Request body: `ConMember`. Only a subset of fields is honored on add: `name` (defaults to `M{newId}` if empty), `crossSectionId` (must be an existing cross-section id in the project, otherwise 422; defaults to the first available cross-section if omitted), `isContinuous` (the member runs through the node, centred on it), `connectedBy` (`begin`/`end`), `mirrorY`, `mirrorZ`, and optionally `model` and/or `position` (applied exactly as on PUT — `members.md`). `id` and `isBearing` are ignored on add — the server assigns the next id (`max(existing)+1`, or 1 for the first) and marks the first member added as bearing.
- Response 200: `ConMember` (the newly created member, with server-resolved `position` and `model`).
- Errors: 401, 404, 400 (an unknown enum string), 422 (no cross-section in project, bad `crossSectionId`, a `position` without a usable `definedBy`, an out-of-range enum, an all-zero `axisX` — `members.md`), 500. Endpoint takes a project lock.

### PUT /api/5/projects/{projectId}/connections/{connectionId}/members
Updates the member identified by the `id` field in the request body.
- Params: `projectId` (path), `connectionId` (path).
- Request body: `ConMember` — `id` selects which member to update; `name`, `crossSectionId`, `isContinuous`, `connectedBy`, `mirrorY`, `mirrorZ`, `model` and `position` are applied (`crossSectionId` unchecked here — `members.md` § Member-level fields). A refused PUT writes nothing, the name included.
- Response 200: `ConMember` (the updated member, with resolved `position`, `model`, and `stiffnessAnalysis` when analysis type is stiffness).
- Errors: 401, 404, 400 (an unknown enum string), 422, 500. Takes a project lock.

### GET /api/5/projects/{projectId}/connections/{connectionId}/members/{memberId}
Gets one member.
- Params: `projectId` (path), `connectionId` (path), `memberId` (path, int).
- Request body: none.
- Response 200: `ConMember` (with `position`, `model`, and `stiffnessAnalysis` when applicable).
- Errors: 401, 404 (member id not found in the connection), 500.

### PUT /api/5/projects/{projectId}/connections/{connectionId}/members/{memberId}/set-bearing-member
Makes `memberId` the bearing member (and clears the bearing flag on all others).
- Params: `projectId` (path), `connectionId` (path), `memberId` (path, int). No request body.
- Response 200: `ConMember` (the now-bearing member). Note: this response does NOT carry the extra `position`/`model`/`stiffnessAnalysis` detail that the other member endpoints return — re-GET the member if you need it.
- Errors: 401, 404 (member id not present), 422, 500. Takes a project lock.

### DTO: ConMember

Inherited from `ConItem`:
| JSON field | Type | Notes |
|---|---|---|
| id | int | Member id. Auto-generated on POST; selects the target on PUT (body). |
| name | string | User-defined member name. |
| active | bool | True if active. |

Own fields:
| JSON field | Type | Notes |
|---|---|---|
| isContinuous | bool | If true, member runs continuously through the joint (insert point Center). |
| crossSectionId | int, nullable | Id of an existing project cross-section. Nullable. |
| connectedBy | ConMemberConnectedByEnum (string enum) | One of: `begin`, `end`. Which end of the member's reference line sits in the node. Send it on non-continuous members, where `begin` and `end` are both stored and select which end sits in the node — both `POST` and `PUT .../members` honor and persist it (a member POSTed with `connectedBy:"end"` reads back `"end"` immediately, no PUT needed). For a member with `isContinuous:true` both ends meet at the node, so `connectedBy` is not needed: whichever value you send, the placement is the same, the loadings act the same (§ LoadEffect) and the member is stored as `connectedBy:"begin"`. |
| mirrorY | bool, nullable | Mirror cross-section about Y. Nullable. |
| mirrorZ | bool, nullable | Mirror cross-section about Z. Nullable. |
| isBearing | bool | Read-only; change it with `set-bearing-member`. True for the bearing member. |
| position | ConMemberPosition | Placement of the member. See block below. |
| model | ConMemberModel | Analysis-model settings. See block below. |
| stiffnessAnalysis | ConStiffnessAnalysis | Only meaningful/populated for stiffness analysis. See block below. |

### DTO: ConMemberPosition
| JSON field | Type | Notes |
|---|---|---|
| definedBy | ConMemberPlacementDefinitionTypeEnum (string enum) | Send `directionVector`, `rotationsOfX` or `lcs`. `none` (also what a position without `definedBy` reads as) is refused with 422 — `members.md`. A member already stored with `none` (for example from a desktop file) reads back `none`; give it one of the three before you PUT its body back. |
| origin | Vector3D | Server-resolved LCS origin (global frame). Omitted when null. |
| axisX | Vector3D | Resolved local X axis (reference-line dir, begin→end). Omitted when null. |
| axisY | Vector3D | Resolved local Y axis (cross-section rotation about X). Omitted when null. |
| axisZ | Vector3D | Resolved local Z axis. Omitted when null. |
| betaDirection | double, nullable | Original placement param "alpha", in **radians**. Omitted when null. |
| gamaPitch | double, nullable | Original placement param "beta", in **radians**. This is the member's pitch out of the global XY plane (`members.md`) — to set N degrees send `radians(N)` (e.g. 30° = 0.5235987…). Omitted when null. |
| alphaRotation | double | Rotation ("rot"), in **radians**. |
| offsetEx | double | Offset along local X. |
| offsetEy | double | Offset along local Y. |
| offsetEz | double | Offset along local Z. |
| align | ConMemberAlignmentTypeEnum (string enum) | One of: `none`, `toMemberPlate`, `toMemberPlateRotateThenTranslate`. |
| alignedPlate | ConAlignedPlate | Omitted when null. |
| relatedPlate | ConAlignedPlate | Omitted when null. |

### DTO: ConMemberModel
| JSON field | Type | Notes |
|---|---|---|
| modelTypeEnum | ConMemberModelTypeEnum (string enum) | Field name is `modelTypeEnum` (NOT `modelType`). One of: `loadedInXYZ`, `loadedInXZ`, `loadedInXY`, `loadedInXYZ_NoBending`. |
| forcesIn | ConMemberForcesInEnum (string enum) | One of: `position`, `node`, `bolts`, `selectedMemberFace`. |
| x | double, nullable | X position. Omitted when null. |
| connectedMemberId | int, nullable | Id of the member whose face this is connected to. Omitted when null. |

### DTO: ConStiffnessAnalysis
| JSON field | Type | Notes |
|---|---|---|
| theoreticalLengthZ | double, nullable | Omitted when null. |
| theoreticalLengthY | double, nullable | Omitted when null. |

### DTO: ConAlignedPlate
A flat object.
| JSON field | Type | Notes |
|---|---|---|
| memberId | int | Id of the member the plate belongs to. |
| partType | ConMemberPlatePartTypeEnum (string enum) | Plate part type. Values include `notSpecified`, `topFlange`, `bottomFlange`, `web`, `basePlate`, `endPlate`, `plateWidener`, `stiffener`, `rib`, `gussetPlate`, `finPlate`, `flange`, `cssArcSegment`, `isStub`, `splice`, `tonguePlate`, `lidPlate`, `generalPlate`, `doubler`, `endPlateOnFlanges`, `backingPlate`, `insertedPlate`, `isNegative`, `bothFlanges`, `allCssParts` (bitmask values). |
| plateSide | ConAlignedPlateSideCodeEnum (string enum) | One of: `default`, `lowerSide`, `upperSide`, `bothSides`, `center`. |

### DTO: Vector3D
| JSON field | Type | Notes |
|---|---|---|
| x | double | X direction component. |
| y | double | Y direction component. |
| z | double | Z direction component. |


---

## LoadEffect

Endpoints for reading and editing the load effects (load cases) of a connection, plus the connection's load settings and the Load Extremes (LEX) reduction. All endpoints require the `ClientId` header. `projectId` is the GUID returned when the project was opened; `connectionId` and `loadEffectId` are integer ids. Mutating endpoints (POST/PUT/DELETE/set-load-settings/calculate-load-extremes) take a per-project lock.


**Author load effects with `"isPercentage": false` and read them with `?isPercentage=false`:
forces in N, moments in N·m** (e.g. `n = 300000` for a 300 kN axial; divide by 1e3 for kN/kNm),
torsion `mx` absolute like the rest. A write with `isPercentage: true` stores converted values,
so it does not round-trip, and a read with `?isPercentage=true` returns absolute values too.
Only forces of active members are returned.

**What a GET does and does not echo.**
- **`POST` stores the loadings you send, plus a zero row for every `(memberId, position)` pair
  of the connection's FIRST (lowest-id) load effect that you did not send.** A member omitted
  from `memberLoadings` is not an error, and existing load effects are not changed. The POST
  response echoes only what you sent, so read the stored rows with `GET .../load-effects/{id}`.
- **`PUT` is a partial update per member.** A member omitted from the body keeps its stored
  loading; the members you send are replaced. The `PUT` response echoes only what you sent, so
  read the stored state with `GET .../load-effects/{id}`.

And a loading with no `sectionLoad` at all is rejected and stores nothing: send `sectionLoad: {}` if you deliberately want a zero-load effect, in which case `calculate` reports *"There are no loads on members"*.

**Which `position` a member accepts is stored in the connection, not derivable from the DTO.**
The first load effect that loads a member fixes the end(s) it may be loaded at: later load
effects must use the same end(s) (the other is 422 *"Defined member loading Member:N,
Position:X is not defined in connection M"*), a member no load effect has loaded yet takes
either end, and `DELETE .../load-effects` clears the assignment. Neither `isContinuous` nor
`connectedBy` predicts it, and a saved file keeps it — a desktop model typically holds one end
per member. **Reuse the `(memberId, position)` pairs of an existing load effect**; with none,
choose freely.

On an ended member the label does not matter to the result: its one loading acts on its one stub
whether it is filed under `Begin` or `End` (sign: below).

**The reliable source is the connection itself:** `GET .../load-effects` and read the
`(memberId, position)` pairs of a load effect it already has — a model imported from a container with results has one,
and a load effect created by a client carries the pairs it was sent plus the zero rows above. A wrong pair
is refused with 422 *"Defined member loading Member:N, Position:X is not defined in connection M"*,
so probing one pair at a time also works on a connection with no load effect yet.

**A loading is a vector in the member's LCS acting at the free end of a stub; its sign follows the
side of the node that stub lies on.** On the +x side a positive `n` is tension and a positive `my`
puts the +z side in tension; on the -x side the same numbers compress the stub and put the -z side
in tension. Which stub a loading acts on:
- **Ended member:** one stub, on +x for `connectedBy: begin` and on -x for `end` (the LCS is the
  same for both), whichever `position` the loading is filed under.
- **Continuous member:** the `Begin` loading acts on the -x stub, the `End` loading on the +x stub.
  The same numbers on either act on the joint as the same vector, so an action that passes
  through the node is the same six components negated on the other side - a tension `N` through
  the member is `Begin` `n = -N` and `End` `n = +N`.

**The six components live INSIDE `sectionLoad`, never flat on the loading.** `{n, vy, vz, mx, my, mz}` written flat on the `memberLoadings` entry are **not read**. The POST answers **HTTP 500** (`"An unexpected error occurred"`, naming no field). So a 500 from this endpoint means a missing `sectionLoad`, not a broken model. A loading carrying no `sectionLoad` key at all is rejected the same way — send `sectionLoad: {}` when a deliberate zero is wanted.

**Validation is PER MEMBER — there is no global slot count to plan around.** Sending fewer pairs than the connection has members, or none at all, is accepted; a member with no force yet can be given one **at any time**, including a member added *after* the load effects already exist. Post a new load effect naming it and it is accepted — you never need to delete existing load effects, nor to add every member before the first one.

### DTO: ConLoadEffect
The request and response body for most endpoints. Extends `ConItem` (fields `id`, `name`, `active`).

| JSON field | Type | Notes |
|---|---|---|
| `id` | int | Load effect id (CBFEM/solver id; from `ConItem`). On POST it is ignored — the server assigns the highest id in use + 1; a freed id below it is not reused. |
| `name` | string | User-defined name (from `ConItem`). |
| `active` | bool | Whether the load effect is active (from `ConItem`). **Settable on both POST and PUT** — `active:false` persists (both GETs read it, `calculate` skips the LE, and it survives a `download`→re-`open` round-trip). An inactive LE is not solved. `calculate-load-extremes` rewrites the flags too. See "Isolating one LE" in `raw-results.md`. |
| `isPercentage` | bool | Send `false` (§ LoadEffect above). |
| `memberLoadings` | array<ConLoadEffectMemberLoad> | Per-member internal forces; defaults to empty list. |

### DTO: ConLoadEffectMemberLoad

| JSON field | Type | Notes |
|---|---|---|
| `memberId` | int | Id of the member the load applies to. |
| `position` | ConLoadEffectPositionEnum | `"Begin"` or `"End"` — reads back PascalCase, but INPUT binding is case-INSENSITIVE (`"end"` accepted, normalized to `"End"`). Emit PascalCase for cleanliness. Which end a member accepts: § 'Which `position` a member accepts' above. |
| `sectionLoad` | ConLoadEffectSectionLoad | Internal forces at this member section. |

### DTO: ConLoadEffectSectionLoad

| JSON field | Type | Unit | Notes |
|---|---|---|---|
| `n` | double | **N** | Axial force along the member's local x. Positive = tension in a stub on the +x side of the node, compression on the -x side (§ LoadEffect above). (Wire unit is N, not kN; ÷1e3 for kN.) |
| `vy` | double | **N** | Shear in local Y. |
| `vz` | double | **N** | Shear in local Z. |
| `mx` | double | **N·m** | Torsional moment. |
| `my` | double | **N·m** | Bending about local Y. Positive = the +z side in tension in a stub on the +x side of the node, the -z side on the -x side (§ LoadEffect above). |
| `mz` | double | **N·m** | Bending about local Z. |

> **Send all six components on every POST and PUT, spelled exactly.** A misspelled or omitted key stores that component as 0, and a PUT replaces the whole `sectionLoad` of each loading it sends.

### Enum: ConLoadEffectPositionEnum

`End` = 0, `Begin` = 1. Which stub each one loads, and the sign: § LoadEffect above.

### DTO: ConLoadSettings

| JSON field | Type | Notes |
|---|---|---|
| `loadsInEquilibrium` | bool | Whether the forces you supply must balance each other. A new connection starts with `true`. |
| `loadsInPercentage` | bool | The connection's percentage-load setting; send `false` (§ LoadEffect above). |

**Send both flags on every `set-load-settings` call**: an omitted or misspelled flag is stored as
`false` (`{}` sets both `false`).

**`loadsInEquilibrium` decides how much of the joint you have to load, and it belongs to the
CONNECTION, not to a load effect.** Left on, the set of forces has to balance, so every member
needs its share. Turned off, a member that continues through the joint takes the reactions and
you load only the members that carry the applied forces — the usual case for a beam framing
into a through column, where inventing column forces just to balance the beam is both work and
a source of error.

Set it with `POST .../load-effects/set-load-settings` before authoring load effects; it is not
a field you can vary per load effect, and the one on `ConLoadEffect` does not override it.

---

### GET `/api/5/projects/{projectId}/connections/{connectionId}/load-effects`
Gets all load effects of a connection. Path params `projectId` (GUID), `connectionId` (int). Query `isPercentage`: send `false` (§ LoadEffect). Response 200: `array<ConLoadEffect>`. Member loadings only include forces of active members.

### POST `/api/5/projects/{projectId}/connections/{connectionId}/load-effects`
Adds a new load effect. Path params `projectId`, `connectionId`. Request body: `ConLoadEffect` (`name`, `active`, `isPercentage`, `memberLoadings`; `id` ignored). Response 200: the created `ConLoadEffect` (server-assigned `id`; `active` is honoured — POST with `active:false` creates an inactive LE). Returns 422 when a `memberId`/`position` pair is repeated in the same request ("The force for 2:End was already added.") or when the pair is not a slot the connection defines ("…is not defined in connection"). An unknown `memberId` returns 404. Beyond the connection's own slots there is no limit on how many loadings one load effect may carry. **Members omitted from `memberLoadings` are NOT an error**; which rows the load effect stores and what the response echoes: § LoadEffect, *What a GET does and does not echo*.

### PUT `/api/5/projects/{projectId}/connections/{connectionId}/load-effects`
Updates the load impulses, `name` and `active` flag of an existing load effect. Path params `projectId`, `connectionId`. Request body: `ConLoadEffect`; the `id` field selects which load effect to update. **This is the only update form — there is no `PUT .../load-effects/{id}` (it returns 405).** Response 200: the same `ConLoadEffect` that was sent (echoed back — NOT the full merged state). 404 if `id` not found. 422 if a sent member loading (`memberId`+`position`) is not among the load effect's existing internal forces.

> **A member omitted from the `PUT` body keeps its stored loading** — § LoadEffect, *What a GET
> does and does not echo*.

### GET `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/{loadEffectId}`
Gets the load impulses of one load effect. Path params `projectId`, `connectionId`, `loadEffectId` (int). Query `isPercentage`: send `false` (§ LoadEffect). Response 200: `ConLoadEffect`. 404 if `loadEffectId` not found in the connection.

### DELETE `/api/5/projects/{projectId}/connections/{connectionId}/load-effects`
**v5 only** (v4 answers 400 *unsupported API version*). Deletes every load effect of the connection together with their internal forces. Response 200: `array<integer>` — the deleted ids, `[]` when there were none. Load effects posted afterwards are numbered from 1 again.

### DELETE `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/{loadEffectId}`
Deletes a load effect and its internal forces. Path params `projectId`, `connectionId`, `loadEffectId`. Response 200: `integer` — the id of the deleted load effect (plain JSON number). 404 if `loadEffectId` not present.

### GET `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/get-load-settings`
Gets the connection's load settings. Path params `projectId`, `connectionId`. Response 200: `ConLoadSettings` (`loadsInEquilibrium`, `loadsInPercentage`).

### POST `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/set-load-settings`
Sets the connection's load settings. Path params `projectId`, `connectionId`. Request body: `ConLoadSettings` with both flags (§ DTO: ConLoadSettings). Response 200: the same `ConLoadSettings` echoed back.

### POST `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/calculate-load-extremes`
Runs the Load Extremes (LEX) algorithm using the project's load-extreme limits (N/Vy/Vz/Mx/My/Mz), then sets `active=true` only on the load effects that produce an extreme and `active=false` on the rest. Path params `projectId`, `connectionId`. No request body. Response 200: `array<ConLoadEffect>` — all load effects of the connection with their updated `active` flags (same shape as the GET-all endpoint). Not on v1–v3. 404 if the connection is not found in the project.


---

## Calculation

CBFEM analysis endpoints. `calculate`, `rawresults-text` and `results` take the same request body — a JSON array of integer connection IDs to calculate, as does the plural `calculate-async` (`endpoints.md` § CalculationJobs) — `calculate` and `rawresults-text` run the calculation server-side before returning, `results` reads the last one. Each requires the `ClientId` header and a `projectId` path GUID. One calculation runs per project at a time (`endpoints.md` § Calculation). Calculation runs sequentially per connection; if a *valid* connection's calculation fails at runtime, the others still return (that failed one comes back with empty/placeholder data, see per-endpoint notes).

**An id that does not exist in the project is handled differently per endpoint:**
- `calculate` and `calculate-async` — strict: an unknown id, alone or among valid ones, answers 404 *"Connection '<id>' was not found in project '<projectId>'."* and nothing is calculated.
- `rawresults-text` — 200, one array element per requested id; the unknown id's element is a failure sentence instead of JSON (see that endpoint's notes).
- `results` — strict: a single unknown id fails the whole request with `404 ProblemDetails` ("Connection 999 was not found in project") and returns nothing for the valid ids.

So send only ids you have confirmed in the project to `calculate`, `calculate-async` and `results`, and check per-element status on `rawresults-text`.

Common request body:

| Body | Type | Notes |
|---|---|---|
| (root) | `array<integer>` | List of connection IDs (the int keys from the project's connections) to calculate. |


### POST /api/5/projects/{projectId}/connections/calculate

Runs CBFEM and returns a per-connection pass/fail summary. Response: `array<ConResultSummary>`.

`ConResultSummary`:

| Property (JSON) | Type | Meaning |
|---|---|---|
| `id` | int | Connection ID that was calculated. |
| `passed` | bool | Overall success of the CBFEM calculation for this connection. |
| `resultSummary` | `array<CheckResSummary>` | Per-check summary rows (one per check category / load case). See "DTO: CheckResSummary". |

If a connection's calculation fails, it still appears in the list with `passed=false`, and `resultSummary` carries a DIAGNOSTIC row. Read that row's message and look it up in `diagnostics.md`.

### DTO: CheckResSummary
Used by both `calculate` (inside `ConResultSummary`) and `results` (inside `ConnectionCheckRes.CheckResSummary`).

| Property (JSON) | Type | Meaning |
|---|---|---|
| `checkValue` | double | Check value, but **NOT a uniform unit** — it is a **percent** for Analysis/Welds/Bolts/Anchors (e.g. `85.35` = 85.35 %) and a **small ratio** for Plates (strain). Do **not** assume 0..1 and do **not** ×100. For display, prefer `unityCheckMessage` (already GUI-formatted). (Raw `rawresults-text` is uniform 0..1 instead — see `raw-results.md`.) |
| `checkStatus` | bool | true = passed. |
| `loadCaseId` | int | Load case (load effect) ID this row belongs to. |
| `name` | string | Check category name. |
| `unityCheckMessage` | string | Human-readable, GUI-matching detail of the overall check — the safe thing to display. |
| `skipped` | bool | true = check was not calculated; `checkValue` should be ignored. |

### POST /api/5/projects/{projectId}/connections/results

Returns detailed, structured check results per connection. Response: `array<ConnectionCheckRes>`.

**It READS results, it does not produce them — `calculate` must have run in the same session.**
Without it you still get **HTTP 200**, with every `checkRes*` array **empty** — no error, no
message saying why. An empty `checkResPlate` therefore means *"nobody calculated"* just as often
as *"nothing to report"*, and nothing in the response separates the two. Call `calculate` and
read its `passed`/`resultSummary` first; treat empty arrays here as "not calculated" until you
have.

**A write empties the stored results of the connection it changes; a write to shared project
data empties every connection's.** `/results` then answers empty arrays for those connections
until you calculate them again.
- **That connection only:** any write inside it — an operation, member or load-effect POST, PUT
  or DELETE (an unmodified PUT included), `DELETE .../operations`, `apply-template`,
  `weld-sizing`, `set-load-settings`, `calculate-load-extremes`, a parameter POST or PUT (also one
  that answers 200 with a `Warning`; one that changes a project cross-section: next item), and a
  connection PUT that does not rename it.
- **Every connection, from inside one:** a parameter link or PUT that changes a project
  cross-section through a `crossSection` owner (`parameters.md`) — the section changes in every
  connection that uses it, and so do their results; a PUT that leaves the section as it was
  empties its own connection only.
- **Every connection:** a material or cross-section POST or PUT, a connection rename, a project
  PUT, a settings PUT, `update-iom-file`.
- **Refused requests:** an operation POST/PUT or a parameter POST refused with 404, 409 or 422
  changes nothing but still empties its own connection's results; a 400 keeps them, and so does
  a parameter, load-effect, settings or connection PUT refused with 422.
- **Reads keep them:** every GET, `results`, `rawresults-text`, `evaluate-expression`, the exports.

So the empty answer is also the normal state mid-edit, not a fault: finish all edits, then
calculate.

`ConnectionCheckRes`:

| Property (JSON) | Type | Meaning |
|---|---|---|
| `checkResSummary` | `array<CheckResSummary>` | Summary rows (see DTO: CheckResSummary). |
| `checkResPlate` | `array<CheckResPlate>` | Per-plate results. |
| `checkResWeld` | `array<CheckResWeld>` | Per-weld results. |
| `checkResBolt` | `array<CheckResBolt>` | Per-bolt results. |
| `checkResAnchor` | `array<CheckResAnchor>` | Per-anchor results. |
| `checkResConcreteBlock` | `array<CheckResConcreteBlock>` | Per concrete-block results. |
| `bucklingResults` | `array<BucklingRes>` | Buckling analysis results. |
| `name` | string | Connection name. |
| `connectionID` | string (uuid) | Connection GUID. **Reads as the all-zero GUID (`00000000-0000-0000-0000-000000000000`) for an API-created (non-.ideaCon-backed) connection**, even though the connection has a real internal identifier elsewhere (`ConConnection.identifier`) — don't rely on this field being populated for API-built projects. |
| `id` | int | Connection integer ID (set to the requested id). |
| `messages` | `OpenMessages` | Validation / calculation errors and warnings. |

Failed connections appear with `passed=false` and a `resultSummary` DIAGNOSTIC row — message meanings are in `diagnostics.md`.

**"No loads on members" is reported as a message, not an HTTP error**: calculating/
requesting results for a connection whose load effects are all inactive or deleted returns HTTP
200 in both `calculate` (`passed:false`) and `results` (all `checkRes*` arrays empty).

Two details to know:

- **`resultSummary` is NOT empty** — it carries exactly one `Analysis` row whose
  `unityCheckMessage` ENDS with `There are no loads on members`, with any other complaint
  concatenated in front of it (`"Plate clash warning Weld clash warning There are no loads on
  members"`). Test with a substring, never for an empty list.
- In `results`, `messages.messages[]` carries the same text split into `ErrorMessage` entries,
  each numbered **`errOperation`** — one shared number, not a load-specific one, so the number
  does not identify this case; match on the description.

A connection with **no members at all** is a different case that looks similar: the `Analysis`
row reads `CBFEM analysis failed - the solver did not produce any results.` and `messages` comes
back **empty**. Nothing there mentions loads.

> **No base-plate-shear here.** `ConnectionCheckRes` has no `checkResBasePlateShear`
> field — base-plate shear (and richer concrete-block detail) is only available via the
> raw `rawresults-text` endpoint (`basePlateShear`, `concreteBlocks` groups — see
> `raw-results.md`). Don't look for it in `/results`.
>
> **Units in the nested types below:** `unityCheck` on weld/bolt/anchor is **already a
> percent** (e.g. `85.35` = 85.35 %) — do not ×100. Plate `maxStress` is **MPa**, plate
> `maxStrain` is on a **ratio×10000** scale (ε_Pl % = `maxStrain` / 100). This matches the
> simplified `checkValue` convention above; the raw endpoint uses 0..1 ratios instead.

Nested list element types:

- `CheckResPlate`: `name` (string), `checkStatus` (bool), `loadCaseId` (int), `maxStrain` (double — plastic strain on a **ratio×10000** scale in this simplified endpoint, so ε_Pl % = `maxStrain` / 100), `maxStress` (double — von Mises stress in **MPa** here), `items` (`array<int>` — sub-item ids for uncoiled/grouped plates). (Note: the raw `rawresults-text` endpoint reports these as SI/ratio instead — see `raw-results.md`.)
- `CheckResWeld`: `name` (string), `id` (int), `unityCheck` (double — the string `"NaN"` when `isFullStrength` is `true`), `checkStatus` (bool), `loadCaseId` (int), `items` (`array<int>`), `isFullStrength` (bool — `true` when the check does not rate the weld by a stress utilisation, so `unityCheck` is `"NaN"` and `checkStatus` is `true`: a `cjp` weld taken as strong as the parent metal, and any weld with `placement: "edgeToEdge"`, fillets included — so the flag does not say that the weld develops the capacity of the plates; read it before comparing `unityCheck` across welds).
- `CheckResBolt`: `name` (string, e.g. "B15" — numeric suffix is an opaque CBFEM solver id, not necessarily starting at 1 or sequential), `unityCheck` (double), `checkStatus` (bool), `loadCaseId` (int).
- `CheckResAnchor`: `name` (string), `unityCheck` (double), `checkStatus` (bool), `loadCaseId` (int).
- `CheckResConcreteBlock`: `name` (string), `unityCheck` (double), `checkStatus` (bool), `loadCaseId` (int).

- `BucklingRes`: `loadCaseId` (int), `shape` (int — buckling shape index from solver), `factor` (double — buckling factor).
- `OpenMessages`: `messages` (array). Each message (polymorphic — its `$type` names `ErrorMessage`, `WarningMessage` or `InformationMessage`) carries `number` (`MessageNumber`, an enum string such as `errOperation`), `description` (string), `propertyName` (string), plus type-specific fields. Only `messages` appears in the JSON.

`loadCaseId` on each per-element row (`CheckResPlate`, `CheckResWeld`, `CheckResBolt`, `CheckResAnchor`, `CheckResConcreteBlock`) is the load effect governing that element, so one response mixes load effects (`raw-results.md` § Multiple load effects). For one load effect: `POST .../connections/{connectionId}/calculate?loadEffectIds=<id>`, then `results`.

### POST /api/5/projects/{projectId}/connections/rawresults-text

Runs CBFEM and returns, for each requested connection, a JSON **string** (so the response is `array<string>` where each element is itself a serialized JSON document — the raw CBFEM results object). Serialization is camelCase with `$type` discriminators for polymorphic types. See `raw-results.md` for how to parse and interpret it. An element for a connection whose results could not be produced is a plain sentence of the form `Results for connection {id} failed: {reason}` rather than JSON — for instance an id absent from the project, or a connection with no loads. Parse each element defensively and treat a parse failure as that connection's error message. A connection that calculates but does not pass (a singularity, say) still returns full parseable JSON, so a failed check is not the same thing as a failed element.

`CheckResultsData` (raw CBFEM results, one level deep). Almost every group is an object keyed by element id (string keys; opaque solver ids that may not start at 1 and may have gaps), each value one result entry:

| Property (JSON) | Type | Meaning |
|---|---|---|
| `codeType` | enum string | Design code used. |
| `platesDeformation` | object (id → entry) | Per-plate local deformation. |
| `plates` | object (id → entry) | Per-plate check results. |
| `platesInfo` | object (id → entry) | Per-plate metadata. |
| `bolts` | object (id → entry) | Per-bolt check results. |
| `boltsInfo` | object (id → entry) | Per-bolt metadata. |
| `boltsAnchor` | object (id → entry) | Anchor (tension) check results. |
| `boltsAnchorCompression` | object (id → entry) | Anchor compression check results. |
| `boltsAnchorInfo` | object (id → entry) | Anchor metadata. |
| `preBolts` | object (id → entry) | Preloaded-bolt check results. |
| `preBoltsInfo` | object (id → entry) | Preloaded-bolt metadata. |
| `boltCheckResDataTimbers` | object (id → entry) | Timber bolt results; each carries `forcesAllLoadCases` keyed by load-effect id (string) — layout: `raw-results.md` § Multiple load effects. |
| `pins` | object (id → entry) | Per-pin results. |
| `welds` | object (id → entry) | Per-weld results. |
| `weldsInfo` | object (id → entry) | Per-weld metadata. |
| `fatigueChecks` | object (id → entry) | Fatigue checks. |
| `fatigueSectionsChecks` | object (id → entry) | Fatigue section checks. |
| `fatigueBoltChecks` | object (id → entry) | Fatigue bolt checks. |
| `fatigueAnchorChecks` | object (id → entry) | Fatigue anchor checks. |
| `fatigueWelds` | object (id → entry) | Fatigue weld checks. |
| `concreteBlocks` | object (id → entry) | Concrete block results. |
| `summary` | object (id → entry) | Overall summary rows. |
| `projectItem` | object (id → entry) | Project-level check data. |
| `analysis` | object (id → entry) | Analysis (solver) results. |
| `totalCapacity` | object (id → entry) | Total-capacity analysis results. |
| `basePlateShear` | object (id → entry) | Base-plate shear results. |
| `stiffnesess` | object (id → entry) | Rotational stiffness results. |
| `stiffnesessAxial` | object (id → entry) | Axial stiffness results. |
| `bucklings` | object (id → entry) | Buckling results. |
| `nonconformity` | array | Nonconformity issues. |
| `costEstimationResults` | object | Cost estimation (fields: `raw-results.md`). |
| `prequalifiedConnectionResults` | object | Prequalified-connection results; may be absent from the JSON. |
| `weldsDataLoadLevels` | object (id → entry) | Per-weld load-level data. |

Each `summary` entry: `checkValue` (double), `checkResult`, `checkContext` (camelCase check name — `analysis`, `plate`, `bolt`, `weld`, `anchor`, `concreteBlock`, `pin`, `buckling`, `basePlateShear`, …), `msgContext` (enum string), `limit` (double), `txtMessage` (string), `tooltip`, `tooltipTitle`, `severity` (int), plus the common entry fields (`raw-results.md` § Structure of the results object). The other groups' entries are not fully expanded here (see `raw-results.md` for the most-used ones).

> **Not expanded in this doc:** the fields of each group's entries beyond those in `raw-results.md`; the members of the `codeType` enum.


---

## Operation

Endpoints for listing, clearing, and bulk-editing the manufacturing operations of a connection, plus automatic weld pre-design. All endpoints require the `ClientId` header. `projectId` is a GUID (path), `connectionId` is an int (path).

The service ALSO exposes strongly-typed per-kind CRUD (`GET/POST/PUT .../operations/{kind}` + `GET .../operations/{kind}/{operationId}` for weld, cut, plate-cut, bolt-grid, anchor-grid, pin-grid, contact, contact-grid, negative-member, negative-plate, stiffening-member, stiffening-plate, work-plane). Those are documented separately in **`reference/operations.md`** (DTOs, wrapper response, gotchas). The thin generic view below still exists and is the only view that shows legacy GUI-authored operation types.

### GET /api/5/projects/{projectId}/connections/{connectionId}/operations

Returns every manufacturing operation in the connection as a `ConOperation`, keyed by the opaque operation `id`.

- Params: `projectId` (path, GUID), `connectionId` (path, int).
- Request body: none.
- Response 200: `application/json`, `array<ConOperation>`.

`ConOperation` is a thin/base view of an operation. It is NOT the full weld/cut/plate operation payload — it only exposes the identity, active flag, import flag and a string operation-type discriminator. The full typed DTOs (`ConWorkPlaneOperation`, `ConBoltGridOperation`, …) are readable/writable through the `operations/{kind}` endpoints — see `reference/operations.md`. Operations created that way read back here with `operationType` values such as `CutBeamData`, `GeneralWeldData`, `GeneralPlateData`, `ConnectorGridData` — treat these as opaque labels, not as a name to match on.

### DTO: ConOperation

| Field (JSON) | Type | Notes |
|---|---|---|
| id | int | From `ConItem`. CBFEM operation id (opaque, may have gaps). |
| name | string | From `ConItem`. User-defined operation name. |
| active | bool | From `ConItem`. True if the operation is active. |
| isImported | bool | True if the operation was imported. |
| operationType | string | Type of the manufacturing operation (e.g. weld/cut/plate kind), as a plain string. |

### DELETE /api/5/projects/{projectId}/connections/{connectionId}/operations

Deletes ALL operations for the connection, and the applied templates and the connection's parameters (with their links) go with them. Treat it as a reset of the connection's manufacturing content rather than a targeted operations-only delete, and re-apply afterwards any template you still need.

- Params: `projectId` (path, GUID), `connectionId` (path, int).
- Request body: none.
- Response: 204 No Content (no response body).

### PUT /api/5/projects/{projectId}/connections/{connectionId}/operations/common-properties

Applies common material/assembly properties to every operation in the connection. Each non-null id is applied to all operations; null fields are left unchanged.

- Params: `projectId` (path, GUID), `connectionId` (path, int).
- Request body: `application/json`, `ConOperationCommonProperties` (see shared DTO below). An id the project does not hold is 422 naming it (*"Plate material 999 was not found in project data."*).
- Response: 204 No Content (no body).

### GET /api/5/projects/{projectId}/connections/{connectionId}/operations/common-properties

Returns the common properties shared across the connection's operations (aggregated from all operations).

- Params: `projectId` (path, GUID), `connectionId` (path, int).
- Request body: none.
- Response 200: `application/json`, `ConOperationCommonProperties` (see shared DTO below).

### DTO: ConOperationCommonProperties

| Field (JSON) | Type | Notes |
|---|---|---|
| weldMaterialId | int, nullable | Id of the weld material to apply to all operations (null = leave unchanged). |
| plateMaterialId | int, nullable | Id of the plate material to apply to all operations. |
| boltAssemblyId | int, nullable | Id of the bolt assembly to apply to all operations. |

### POST /api/5/projects/{projectId}/connections/{connectionId}/operations/weld-sizing

Pre-designs (auto-sizes) the welds in the connection using the selected sizing method, then persists the change.

- Params: `projectId` (path, GUID), `connectionId` (path, int), `designType` (query, enum `ConWeldSizingMethodEnum`, default `fullStrength`; the value is case-insensitive).
- Request body: none.
- Response 200: `application/json`, a plain JSON `string` (a status message). On success it has the form: `Connection {connectionId} welds were set {preDesignType}.` where `{preDesignType}` names the method applied (e.g. `PredesignWeldsToFullStrength`).

Behavior / error notes:
- `designType=capacityEstimation` is refused with **501** Not Implemented, *"Capacity estimation is not supported yet."* (ProblemDetails).
- `designType=minimumDuctility` is allowed only when the project country code is Eurocode (ECEN); otherwise 422 Unprocessable Entity ("Weld option ... is supported only for ECEN").
- The name that comes back in the message per method: `fullStrength` -> PredesignWeldsToFullStrength; `minimumDuctility` -> PredesignWeldsToMinDuctility; `overStrengthFactor` -> PredesignWeldsToFullStrengthWithOverstrengthFactor.

### Enum: ConWeldSizingMethodEnum

`fullStrength` (default) · `minimumDuctility` (Eurocode only, 422 elsewhere) ·
`overStrengthFactor` · `capacityEstimation` (501 on every code). Case-insensitive.

---

## Material


All endpoints require the `ClientId` header. `{projectId}` is the GUID returned when opening a project. The materials belong to the project, not to a connection.

Important shape note (applies to every endpoint here except `materials/cross-sections` on v5, which answers `ConCrossSection`): the request bodies are the tiny DTOs `ConMprlElement` / `ConMprlCrossSection` (basically just an MPRL library name). But the **GET responses and the POST responses are NOT those DTOs** — they are full IOM (IdeaRS.OpenModel) material objects. These IOM types are polymorphic, so each array element carries a `$type` discriminator and the concrete class depends on the design code of the project (EC/EN → `*Ec2`, plus AISC, CISC, AUS, and other code variants). The field tables below document the EC2/EN concrete variants plus their shared base; other code variants share the base and add a few code-specific fields not enumerated here. Swagger shows these responses only as generic objects.

**Units: every numeric material field is plain SI — Pa for
stresses/moduli, m for lengths/diameters, m² for areas — same convention as the rest of this API, NOT
the MPa/mm a GUI user would expect.** E.g. `S 355` steel → `fy: 355000000.0` (355 MPa), `fu:
490000000.0`; a `M20 10.9` bolt → `diameter: 0.02` (20 mm), `grossArea: 0.000314` (314 mm²); `C25/30`
concrete → `fck: 25000000.0` (25 MPa); an `S 450` electrode → `fu: 550000000.0`. Divide stresses by 1e6
for MPa, multiply lengths by 1000 for mm, multiply areas by 1e6 for mm².

### POST request body DTOs

`ConMprlElement`

| JSON field | Type | Notes |
|---|---|---|
| mprlName | string | Name of the material in the MPRL material library to add (e.g. "S 450", "10.9", "M20 10.9", "SD1"). |

`ConMprlCrossSection` (extends `ConMprlElement`)

| JSON field | Type | Notes |
|---|---|---|
| mprlName | string | (inherited) Cross-section name in the MPRL library (e.g. "IPE240"). |
| materialName | string | Name of the steel material to assign to the cross-section (e.g. "S 450"). |

### Shared IOM base: `Material`

Abstract base of all returned material objects. Derives from `OpenElementId` which adds `id` (int — opaque CBFEM/solver id).

| JSON field | Type | Notes |
|---|---|---|
| id | int | from `OpenElementId`; opaque solver id |
| name | string | material name |
| loadFromLibrary | bool | |
| e | double | Young's modulus |
| g | double | shear modulus |
| poisson | double | Poisson's ratio |
| unitMass | double | |
| specificHeat | double | |
| thermalExpansion | double | |
| thermalConductivity | double | |
| isDefaultMaterial | bool | |
| orderInCode | int | |
| stateOfThermalExpansion | enum string | None/Code/User |
| stateOfThermalConductivity | enum string | None/Code/User |
| stateOfThermalSpecificHeat | enum string | None/Code/User |
| stateOfThermalStressStrain | enum string | None/Code/User |
| stateOfThermalStrain | enum string | None/Code/User |
| userThermalSpecificHeatCurvature | Polygon2D | nullable |
| userThermalConductivityCurvature | Polygon2D | nullable |
| userThermalExpansionCurvature | Polygon2D | nullable |
| userThermalStrainCurvature | Polygon2D | nullable |
| userThermalStressStrainCurvature | array<TemperatureCurve2D> | nullable |

---

### GET /api/5/projects/{projectId}/materials

Lists the project's materials — the catalog shared by all its connections, including entries no connection uses (a material stays listed after the connection that used it is deleted). Returns `200` with a JSON **array of polymorphic IOM material objects** (steel + concrete + bolt-grade + welding + headed-stud-grade mixed together). `GET .../materials` lists every kind; each `materials/{kind}` GET below lists only that kind.

Each element is one of: `MatSteelEc2`, `MatConcreteEc2`, `MatWeldingEc2`, `MaterialBoltGrade(Ec2)`, `MaterialHeadedStudGrade(Ec2)` (or the corresponding code-specific subclass), distinguished by `$type`.

### GET /api/5/projects/{projectId}/materials/steel
### POST /api/5/projects/{projectId}/materials/steel

GET returns `array<MatSteelEc2>` (or code variant). POST body is `ConMprlElement` (looks up `mprlName` in the steel MPRL library, adds it, answers one `MatSteelEc2` as `object`). **Every POST adds an entry and answers the id of the OLDEST entry with that name** — which may be one the project already held (a new project already has a `S 355` welding entry) — so take the id from `GET .../materials/{kind}`, not from the POST. Every material POST answers this way — concrete, welding, bolt-grade, headed-stud-grade, reinforcement, bolt-assembly — except pin, which answers the new id.

`MatSteelEc2` adds, on top of the shared `Material` base:

| JSON field | Type | Notes |
|---|---|---|
| fy | double | yield strength, thickness <= 40mm |
| fu | double | ultimate strength, thickness <= 40mm |
| fy40 | double | yield strength, 40mm < t <= 100mm |
| fu40 | double | ultimate strength, 40mm < t <= 100mm |
| diagramType | enum string | `bilinear` / `definedByUser` |
| userDiagram | Polygon2D | nullable |
| materialStrength | MaterialStrengthProperty | per-thickness strength table (see below) |

`MaterialStrengthProperty`: `{ list: array<MaterialStrength> }`.
`MaterialStrength`: `{ maxThickness: double, fy: double, fu: double, f: double }`.

### GET /api/5/projects/{projectId}/materials/concrete
### POST /api/5/projects/{projectId}/materials/concrete

GET returns `array<MatConcreteEc2>` (or code variant). POST body `ConMprlElement`, returns a `MatConcreteEc2` (the oldest of that name — § steel).

`MatConcreteEc2` adds, on top of `Material`:

| JSON field | Type | Notes |
|---|---|---|
| calculateDependentValues | bool | |
| fck | double | characteristic cylinder strength |
| ecm | double | secant modulus |
| epsc1, epsc2, epsc3 | double | compressive strains |
| epscu1, epscu2, epscu3 | double | ultimate compressive strains |
| fctm | double | mean tensile strength |
| fctk_0_05 | double | tensile strength 5% quantile |
| fctk_0_95 | double | tensile strength 95% quantile |
| nFactor | double | |
| fcm | double | mean compressive strength |
| stoneDiameter | double | |
| cementClass | enum string | `s` / `r` / `n` |
| aggregateType | enum string | `quartzite` / `limestone` / `sandstone` / `basalt` |
| diagramType | enum string | `bilinear` / `parabolic` / `definedByUser` |
| silicaFume | bool | |
| plainConcreteDiagram | bool | |
| userDiagram | Polygon2D | nullable |

### GET /api/5/projects/{projectId}/materials/bolt-grade
### POST /api/5/projects/{projectId}/materials/bolt-grade

GET returns `array<MaterialBoltGrade>` — on an ECEN project the `$type` is `MaterialBoltGrade` with no Ec2 variant (unlike steel / concrete / welding, which serialize as `MatSteelEc2` / `MatConcreteEc2` / `MatWeldingEc2`). POST body `ConMprlElement`, returns a bolt grade (the oldest of that name — § steel).

`MaterialBoltGrade` adds, on top of `Material`:

| JSON field | Type | Notes |
|---|---|---|
| fub | double | ultimate tensile strength |
| fyb | double | yield strength |
| elongation | double | e.g. 0.2 = 20% |
| code | enum string | `CountryCode` design code |
| mprlElementID | string (uuid) | present in the JSON |
| mprlTableID | string (uuid) | present in the JSON |


### GET /api/5/projects/{projectId}/materials/welding
### POST /api/5/projects/{projectId}/materials/welding

GET returns `array<MatWeldingEc2>` (or code variant). POST body `ConMprlElement`, returns a `MatWeldingEc2` (the oldest of that name — § steel).

`MatWeldingEc2` adds, on top of `Material`:

| JSON field | Type | Notes |
|---|---|---|
| fu | double | ultimate strength |
| betaW | double | correlation factor βw |

### GET /api/5/projects/{projectId}/materials/headed-stud-grade
### POST /api/5/projects/{projectId}/materials/headed-stud-grade

GET returns `array<MaterialHeadedStudGrade>` — on ECEN the `$type` is the BASE class `MaterialHeadedStudGrade`, NOT an `Ec2` variant (same as bolt-grade). POST body `ConMprlElement`, returns a headed-stud grade (e.g. `mprlName="SD1"`; the oldest of that name — § steel).

`MaterialHeadedStudGrade` has the same added fields as `MaterialBoltGrade`:

| JSON field | Type | Notes |
|---|---|---|
| fub | double | ultimate tensile strength |
| fyb | double | yield strength |
| elongation | double | |
| code | enum string | design code |
| mprlElementID | string (uuid) | |
| mprlTableID | string (uuid) | |

### GET /api/5/projects/{projectId}/materials/cross-sections
### POST /api/5/projects/{projectId}/materials/cross-sections

On v5, GET returns an array of `ConCrossSection` (`id`, `name`, `definition`) and POST returns the one `ConCrossSection` it created — `cross-sections.md` § The one trap. The IOM shape below is what **v4** answers: GET returns `200` with `array<CrossSection>` (IOM, polymorphic). Concrete subclass for added/parametric sections is `CrossSectionParameter`; other `$type`s are `CrossSectionComponent`, `CrossSectionGeneralColdFormed` and `GeneralCrossSection`.

POST body is `ConMprlCrossSection` (`mprlName` + `materialName`). It looks up the section by `mprlName` and assigns material `materialName`; on v4 it returns an IOM cross section as `object`.

Fields every v4 cross section carries:

| JSON field | Type | Notes |
|---|---|---|
| id | int | from `OpenElementId`; opaque solver id |
| name | string | cross-section name |
| crossSectionRotation | double | |
| isInPrincipal | bool | |

`CrossSectionParameter` adds:

| JSON field | Type | Notes |
|---|---|---|
| crossSectionType | enum string | `CrossSectionType` (very large enum: e.g. `rolledI`, `rolledCHS`, `rolledRHS`, `iw`, `o`, `rect`, …) |
| parameters | array<Parameter> | polymorphic; each item has `name` + a `value` (see below) |
| material | ReferenceElement | reference to the assigned material |

`parameters` — each array item is one of: `ParameterDouble` `{ name, value:double }`, `ParameterInt` `{ name, value:int }`, `ParameterBool` `{ name, value:bool }`, `ParameterString` `{ name, value:string }`, `ParameterReferenceElement` `{ name, value:ReferenceElement }`, distinguished by `$type`.

`ReferenceElement` serializes as: `{ typeName: string, id: int }`; the resolved referenced element (e.g. the material) is available under `material.element`.

### GET /api/5/projects/{projectId}/materials/bolt-assemblies
### POST /api/5/projects/{projectId}/materials/bolt-assemblies

GET returns `array<BoltAssembly>` (IOM). POST body `ConMprlElement` (`mprlName`, e.g. "M20 10.9"), returns one `BoltAssembly` (the oldest of that name — § steel).

`BoltAssembly`:

| JSON field | Type | Notes |
|---|---|---|
| id | int | from `OpenElementId`; opaque solver id |
| name | string | e.g. "M16 8.8" |
| boltGrade | ReferenceElement | reference to the bolt-grade material (`.element` resolves to a `MaterialBoltGrade`) |
| diameter | double | bolt diameter |
| borehole | double | bore-hole size |
| headDiameter | double | |
| diagonalHeadDiameter | double | |
| headHeight | double | head thickness |
| grossArea | double | |
| tensileStressArea | double | |
| nutThickness | double | |
| washerThickness | double | |
| washerAtHead | bool | |
| washerAtNut | bool | |
| loadFromLibrary | bool | |

### Notes / behavior

- Writes to one project are serialized. POST endpoints may return `422 Unprocessable Entity`; all endpoints can return `401`, `404`, `500`.
- POST returns a **single** element, not the whole list: the first entry with that name, which for a repeated name is not the one just added (§ steel).
- `Polygon2D` (`points: array<Point2D{x,y}>`) and `TemperatureCurve2D` are referenced from the `Material` base but only populated when user-defined thermal/diagram curves exist (otherwise null/empty); not expanded here.

> **Not expanded in this doc** (consult the live spec if needed): Polygon2D / Point2D and TemperatureCurve2D field details (referenced by Material base; not expanded — only used for user-defined thermal/stress-strain curves); CountryCode enum members (used by code field on bolt-grade/headed-stud-grade); CrossSectionType full enum value list (over 100 members; sampled only); Concrete-specific code variant fields for non-EC2 codes (MatConcreteACI/CAN/AUS/RUS/IND/HKG/CHN/SIA) — only the EC2/base shape documented; Steel/welding/bolt-grade non-EC code-variant extra fields (AISC/CISC/AUS/RUS/CHN/IND/HKG) — base shape documented only


---

## Parameter

Endpoints for reading, updating, and deleting connection parameters, and for evaluating parameter expressions. All endpoints require the `ClientId` header. The connection must already be opened in a project (see project/connection endpoints). Parameters are keyed by a string identifier (the `key` field), not by the opaque CBFEM ids.


### GET /api/5/projects/{projectId}/connections/{connectionId}/parameters

Returns all parameters defined for the connection.

- `projectId` (path, GUID) — opened project id.
- `connectionId` (path, int) — connection id.
- `includeHidden` (query, bool, default `false`) — when `false`, only parameters with `isVisible: true` are returned; when `true`, hidden parameters are included too.

Response 200: `application/json` — `array<IdeaParameter>` (see `### DTO: IdeaParameter`). 

### PUT /api/5/projects/{projectId}/connections/{connectionId}/parameters

Updates parameters of the connection. Each item in the body targets an existing parameter by `key` and supplies the fields to change (expression, label, visibility, value type — `parameters.md` § Presentation). If any supplied `key` does not match an existing parameter identifier in the connection, the call fails validation (HTTP 422) and the error lists the missing keys plus the available identifiers. Each supplied expression is stored, evaluated and written back into the model. An expression that does not evaluate is stored anyway and the call still answers 200 — check `parameters[].validationStatus` in the response (`parameters.md` § What a 200 promises).

- `projectId` (path, GUID), `connectionId` (path, int).

Request body: `application/json` — `array<IdeaParameterUpdate>` (see `### DTO: IdeaParameterUpdate`).

Response 200: `application/json` — `ParameterUpdateResponse` (see `### DTO: ParameterUpdateResponse`).

Possible errors: 401, 404, 422 (validation), 500. Writes to one project are serialized.

> **A `Weld`-typed parameter cannot be created over REST**: `POST .../parameters` answers 422 *"Parameter type 'Weld' is not supported yet. Supported types: [Bool, Expression, Float, Int, String]"*. **To drive a weld, use an `Expression` parameter** against an operation's `propId;Size` / `propId;WeldType` sub-path — which property types a parameter can actually drive is in `field-matrix.md`.

### DELETE /api/5/projects/{projectId}/connections/{connectionId}/parameters

Deletes all parameters and all parameter-to-model links for the connection (clears the connection's parameters and the connection's parameter-model links).

- `projectId` (path, GUID), `connectionId` (path, int).

Response: 204 No Content on success. No response body. Writes to one project are serialized.
(Note: the deprecated V1-V3 variants instead return 200 with a JSON object `{ "message": "..." }`.)

### POST /api/5/projects/{projectId}/connections/{connectionId}/evaluate-expression

Evaluates a parameter expression against the connection's current parameters and model, returning the computed result.

- `projectId` (path, GUID), `connectionId` (path, int).

Request body: `application/json` — a single JSON `string` containing the expression to evaluate (e.g. `"2 * Width + 5"`). Supported syntax is documented at https://developer.ideastatica.com/docs/api/api_parameters_getting_started.html.

Response 200: `application/json` — a single JSON `string`: the evaluated result rendered to text. It is a plain string, not a serialized object. `"1+2*3"`→`"7"`, `"10/4"`→`"2.5"`, `"Sqrt(16)"`→`"4"`.

- **Spelling, arity and bad-expression behaviour: `parameters.md` § Writing the expression.**
  A bad expression returns 500 ProblemDetails here; treat 500 from THIS endpoint as "bad
  expression", not a server fault. Possible errors: 401, 404, 422, 500.
- **The expression language is the desktop's**, so the parametric functions a user writes in the
  GUI's parameter table work here too — including `GetValue('<memberName>','<property>')`, which
  is how you read a model property that has no endpoint of its own. The member is addressed by
  its **`name`**, not its id, and a material name comes back spelled per the project's design
  code (so the same model answers differently under `american` than under `ecen`).
- **An unknown property is a RESULT, not an error:** it returns 200 with the string
  `"Property '<name>' not found"` (with a third argument, that default instead —
  `parameters.md` § Reading the model inside an expression). A 200 therefore does not mean the
  property exists — compare the returned text.

### DTO: IdeaParameter

| Field | Type | Notes |
|---|---|---|
| key | string | Parameter identifier (the lookup key used on update). |
| expression | string | The parameter's expression. |
| default | string | Default expression/value. |
| value | any | Current value — a number, string or bool, whatever the expression evaluates to. |
| unit | string | Display unit, read-only — follows `valueType`. |
| valueType | `ConParameterValueType` | What the value is (`lengthComponent`, `weldSize`, `angle`, `wholeNumber`, …); `generic` when not set. |
| parameterType | string | Parameter type as text. |
| description | string | Human-readable description. |
| validationStatus | string | Current validation status as text. |
| isVisible | bool, nullable | Listed by `GET .../parameters` without `includeHidden` only when true. |
| lowerBound | string | Lower-bound expression. |
| upperBound | string | Upper-bound expression. |
| parameterValidation | IdeaParameterValidation | Nested validation details (see below). |

### DTO: IdeaParameterValidation

| Field | Type | Notes |
|---|---|---|
| validationExpression | string | Validation expression. |
| validationExpressionEvaluated | bool | Whether the validation expression was evaluated. |
| lowerBound | string | Lower-bound expression. |
| lowerBoundEvaluated | double | Evaluated lower bound. |
| upperBound | string | Upper-bound expression. |
| upperBoundEvaluated | double | Evaluated upper bound. |
| validationStatus | string | Status text. |
| message | string | Validation message. |

### DTO: IdeaParameterUpdate

| Field | Type | Notes |
|---|---|---|
| key | string | Identifier of the existing parameter to update. Must match the `key` of an existing parameter or the whole request fails (422). |
| expression | string | New expression/value to set. When non-empty, it is set as the parameter's value and evaluated. |
| description | string | New label; omitted keeps the old one. |
| isVisible | bool, nullable | New visibility; omitted keeps it. |
| valueType | `ConParameterValueType` | New value type; omitted keeps it. Must suit the parameter type (422 otherwise). |

A field left out keeps its stored value, so an item with only `key` + `expression` changes the value alone. There is no selector for a bound: set bounds on create; a PUT cannot change them. A field that is not in this DTO is ignored rather than reported — a typo such as `value` in place of `expression` is an item that changes nothing (200, the parameter as it was).

### DTO: ParameterUpdateResponse

| Field | Type | Notes |
|---|---|---|
| setToModel | bool | True if the validated values were written into the model. |
| parameters | array<IdeaParameter> | The resulting parameters (see `### DTO: IdeaParameter`). Defaults to empty list. |
| failedValidations | array<IdeaParameterValidationResponse> | Validation failures, if any. Defaults to empty list. |

### DTO: IdeaParameterValidationResponse

| Field | Type | Notes |
|---|---|---|
| key | string | Parameter identifier that failed. |
| message | string | Validation message (from `parameterValidation.message`). |
| validationStatus | string | Validation status text. |


---

## Template

Endpoints for working with connection templates: listing/reading applied templates, exporting a connection as a reusable template ("contemp" string), computing default conversion mappings, applying a template, exploding/deleting templates, and managing per-template common properties and parameter defaults.

All endpoints require the `ClientId` header (raw GUID from `GET /api/5/clients/connect-client`). All paths are under `http://localhost:5000/api/5`. JSON is camelCase; enums serialize as camelCase strings; polymorphic types carry a `$type` discriminator. Errors use `ProblemDetails` for 401/404/422/500.


---

### GET `/projects/{projectId}/connections/{connectionId}/templates`
List the templates currently applied in a connection.
- Path params: `projectId` (GUID string), `connectionId` (int).
- Response 200: `array<ConConnectionTemplate>` (see DTO block below). One entry per applied template instance; the array is empty if none are applied.

### GET `/projects/{projectId}/connections/{connectionId}/templates/{templateInstanceId}`
Get one applied template by its instance id.
- Path params: `projectId` (GUID string), `connectionId` (int), `templateInstanceId` (int — this is `ConConnectionTemplate.templateId`, the per-connection instance id, NOT the library GUID).
- Response 200: `ConConnectionTemplate`. Returns 404 if no applied template has that instance id.

> **Every v5 per-template route takes that int `templateId`** — GET by id, `explode`, `DELETE`,
> `common-properties` GET/PUT and `load-defaults` — and acts on that one instance, also when the
> same library template is applied twice (each instance has its own `templateId`). An id the
> connection does not hold is 404 *"Template with id '999' was not found in connection '4'"* on
> every one of them; a GUID there is 400. v4 takes the `libraryTemplateId` GUID instead.

### DELETE `/projects/{projectId}/connections/{connectionId}/templates`
Delete all templates in the connection. Removes each applied template together with its parameters, param-model links AND its operations (full delete).
- Path params: `projectId` (GUID string), `connectionId` (int).
- Response: 204 No Content. No body.

### GET `/projects/{projectId}/connections/{connectionId}/get-template`
Export the connection as a template string.
- Path params: `projectId` (GUID string), `connectionId` (int).
- Response 200: `text/plain` — a single serialized **"contemp" template string**. It is an opaque serialized template payload (captures operations/connection data, analysis info, loads, parameters, param-model links and section/clipping data); it is consumed back as the `template` / `connectionTemplate` string in `get-default-mapping` and `apply-template`. It is NOT a JSON object with documented fields — treat it as an opaque token.

### POST `/projects/{projectId}/connections/{connectionId}/templates/create-from-connection`
Create a reusable template from the connection, with structured metadata.
- Path params: `projectId` (GUID string), `connectionId` (int).
- Request body: none.
- Response 200: `ConTemplateCreateResult`. Its `template` field carries the same opaque contemp string as `get-template`; the rest is metadata inherited from the source connection.

| Field (camelCase) | Type | Notes |
|---|---|---|
| templateId | string (GUID) | Newly generated id for this exported template |
| name | string | From connection header, falls back to `CON-{connectionId}` |
| designCode | string | e.g. `ECEN`, `American`, `AUS` (enum name as text) |
| version | int | Data-contract version embedded in the template |
| manufacturingType | string | e.g. Welded/Bolted/Mixed (as text) |
| typologyCode | string | Classified member typology, e.g. `X+;Y+` |
| typologyCode_V2 | string | V2 typology form, e.g. `C;EX+;EY+` |
| operationCount | int | Number of operations captured |
| parameterCount | int | Number of parameters captured |
| paramModelLinkCount | int | Number of parameter-to-model links captured |
| template | string | The opaque "contemp" serialized template payload |

### POST `/projects/{projectId}/connections/{connectionId}/get-default-mapping`
Compute the default conversion mapping needed to apply a template to this connection. The returned mapping can be edited by the caller and then passed into `apply-template`.
- Path params: `projectId` (GUID string), `connectionId` (int).
- Request body: `ConTemplateMappingGetParam`.

| Field | Type | Notes |
|---|---|---|
| template | string | The contemp template string (from `get-template` / `create-from-connection`) |
| memberIds | array<int> | **Ordered list that positionally maps your connection's members onto the template's members, in template order.** The template's members have a fixed order — index 0 is the template's **bearing** member, index 1+ are its **attached** members. So `memberIds[0]` is mapped onto the template's bearing member, `memberIds[1]` onto the template's first attached member, etc. **Gotcha:** to apply a template (bearing + one attached member) to one attachment of your connection, you must pass **both** ids in order `[yourBearingId, yourAttachedId]`. Illustration (a joint with bearing member MAIN id 1 and two attached braces DIAG id 3, HOR id 4): `[1, 4]` maps template bearing→MAIN and the template's attached member→HOR; `[1, 3]` gives →DIAG. Passing a single id like `[4]` is wrong: that one id lands on the **bearing** slot, so the template's bearing member is remapped onto your attached member (the cut then goes the wrong way). With `[]`, mapping is by matching member **names** only — so a template attached member named "HOR" always maps onto your "HOR" and can never reach a differently-named member like "DIAG". To template two attachments on the same bearing member separately, call once per attachment with `[bearingId, attachedId]` and apply each mapping. |

- Response 200: `TemplateConversions` (see shared DTO block), always with a `conversions` list. The conversions cover **member** and **material/electrode** mappings only — there is no parameter conversion entry. Template parameters are created by the server on `apply-template`, not steered through the mapping (see the collision note on `apply-template`).

### POST `/projects/{projectId}/connections/{connectionId}/apply-template`
Apply a template to the connection using a (possibly edited) mapping.
- Path params: `projectId` (GUID string), `connectionId` (int).
- Request body: `ConTemplateApplyParam`.

| Field | Type | Notes |
|---|---|---|
| connectionTemplate | string | **Required.** The contemp template string to apply. **Field name gotcha: it is `connectionTemplate` here, NOT `template`.** `get-default-mapping`'s request body uses `template` (see above) — the two endpoints use different field names for the same contemp string. A body without `connectionTemplate` (for instance one that sends `template`) is 400, the `errors` map naming `connectionTemplate` (ignore its `applyTemplateParam` entry, the same cascade as `request` elsewhere). |
| mapping | `TemplateConversions` | **Required**, and so is its `conversions` list: omitted or null is 400 naming `mapping` (or `mapping.conversions`). A mapping with the wrong number of entries is 422 *"Mapping has 0 conversions but this connection/template pair expects 4. The mapping was not produced by get-default-mapping …"*. The canonical flow is two steps — call `get-default-mapping` with the same template string (`memberIds` may be empty), then pass its `TemplateConversions` response straight back in here (optionally edited). |

> **Parameter-key collisions are non-destructive.** A template can carry parameters. If the
> connection already carries a parameter with the same key as one the template creates,
> `apply-template` succeeds and the incoming one is added under a suffixed key (e.g. `D_2`) —
> nothing is overwritten and no key ends up duplicated. This holds whichever way the existing
> key got there: a parameter the project owned before, or one a *previous* `apply-template`
> created. Read the full set with `GET .../parameters?includeHidden=true` after applying.
>
> This suffixing is also the mechanism for independent parameters per attachment: apply the
> template for each member in turn, and each attachment ends up with its own copy of the
> parameter. There is no need to clear parameters beforehand.
>
> `PUT .../parameters` only updates existing keys; it cannot rename a key or add a new one
> (unknown key → 422 "Parameters not found in connection").

> **Template parameter visibility.** `apply-template` brings across **all** of the
> template's parameters, but a parameter is only listed by `GET .../parameters` if it is
> marked visible (`isVisible`, set when the template is authored; `PUT .../parameters` can
> change it afterwards). Parameters left not-visible are
> still applied to the model; they simply don't appear in the default listing. To see them,
> call `GET .../parameters?includeHidden=true`. So "the template's parameters disappeared
> after applying" almost always means they weren't marked visible in the template, not that
> they were lost.

- Response 200: `ConTemplateApplyResult`.

| Field (camelCase) | Type | Notes |
|---|---|---|
| appliedWithoutIssues | bool | True if there were no issues or only Info-severity issues |
| templateModel | `ConConnectionTemplate` | The resulting applied template (ids of created members/operations/parameters) |
| issues | array<`ConNonConformityIssue`> | Non-conformity issues raised during application |

`ConNonConformityIssue`:

| Field | Type | Notes |
|---|---|---|
| operationId | int | Id of the related object/operation (if applicable) |
| description | string | Issue title |
| details | string | Detailed description |
| severity | `ConNonConformityIssueSeverity` enum string | `info`, `warning`, `error`, `terminatedError` — camelCase in JSON |

### POST `/projects/{projectId}/connections/{connectionId}/templates/explode`
Explode all templates: removes each template's parameters and param-model links but KEEPS its operations (operations are detached from the template).
- Path params: `projectId` (GUID string), `connectionId` (int).
- Response: 204 No Content. No body.

### POST `/projects/{projectId}/connections/{connectionId}/templates/{templateId}/explode`
Explode one specific template (delete its parameters + links, keep operations).
- Path params: `projectId` (GUID string), `connectionId` (int), `templateId` (int — `ConConnectionTemplate.templateId`, the per-connection instance id that `GET .../templates` lists). Returns 404 if not found.
- Response: 204 No Content. No body.

### DELETE `/projects/{projectId}/connections/{connectionId}/templates/{templateId}`
Delete one specific template (removes parameters, links AND operations).
- Path params: `projectId` (GUID string), `connectionId` (int), `templateId` (int instance id, as for explode). Returns 404 if not found.
- Response: 204 No Content. No body.

### GET `/projects/{projectId}/connections/{connectionId}/templates/{templateId}/common-properties`
Get the common material/bolt properties shared across the template's operations.
- Path params: `projectId` (GUID string), `connectionId` (int), `templateId` (int instance id, as for explode). Returns 404 if not found.
- Response 200: `ConOperationCommonProperties`.

| Field | Type | Notes |
|---|---|---|
| weldMaterialId | int, nullable | Common weld (electrode) material id, null if not uniform |
| plateMaterialId | int, nullable | Common plate material id, null if not uniform |
| boltAssemblyId | int, nullable | Common bolt assembly id, null if not uniform |

### PUT `/projects/{projectId}/connections/{connectionId}/templates/{templateId}/common-properties`
Set the common properties for all operations in the template. Null fields are left unchanged.
- Path params: `projectId` (GUID string), `connectionId` (int), `templateId` (int instance id, as for explode). Returns 404 if not found.
- Request body: `ConOperationCommonProperties` (same shape as above; the int ids reference materials/bolt assemblies in the project). An unknown id is 422, as on the connection-level PUT.
- Response: 204 No Content. No body.

### POST `/projects/{projectId}/connections/{connectionId}/templates/{templateId}/load-defaults`
Reset the template's parameters to their default expressions and re-validate. Applies only to parameters with `isVisible: true` and a non-empty default — a parameter created with `POST .../parameters` has an empty `default`, so it is left as it is.
- Path params: `projectId` (GUID string), `connectionId` (int), `templateId` (int instance id, as for explode). Returns 404 if not found.
- Request body: none.
- Response 200: `ParameterUpdateResponse`.

| Field | Type | Notes |
|---|---|---|
| setToModel | bool | True if the defaults were committed to the model |
| parameters | array<`IdeaParameter`> | Resulting parameter values after applying defaults |
| failedValidations | array<`IdeaParameterValidationResponse`> | Parameters whose validation failed |

`IdeaParameterValidationResponse`: `key` (string), `message` (string), `validationStatus` (string).

`IdeaParameter` (one level): `key` (string), `expression` (string), `default` (string), `value` (any), `unit` (string), `valueType` (`ConParameterValueType`), `parameterType` (string), `description` (string), `validationStatus` (string), `isVisible` (bool, nullable), `lowerBound` (string), `upperBound` (string), `parameterValidation` (`IdeaParameterValidation` object: `validationExpression`, `validationExpressionEvaluated`, `lowerBound`, `lowerBoundEvaluated`, `upperBound`, `upperBoundEvaluated`, `validationStatus`, `message`).

---

### DTO: ConConnectionTemplate

| Field (camelCase) | Type | Notes |
|---|---|---|
| libraryTemplateId | string (GUID) | Library template id; same GUID reused when the same template is applied multiple times — the `{templateId}` of the per-template routes on v4 |
| templateId | int | Unique instance id of the template within the connection — the `{templateInstanceId}` of GET-by-id and the `{templateId}` of every per-template route on v5 |
| members | array<`ConMember`> | **Swagger declares this as `array<ConItem>` (just `id`/`name`/`active`), but the entries are full `ConMember` objects** (after `apply-template`, and in `GET .../templates`): each carrying a `$type` discriminator naming `ConMember` plus `isContinuous`, `crossSectionId`, `connectedBy`, `mirrorY`/`mirrorZ`, `isBearing`, `position`, `model`, `stiffnessAnalysis` — the full shape documented under DTO: ConMember above, not the thin `ConItem`. |
| operations | array<`ConItem`> (per swagger) | Operations used in the template. Whether entries carry more than the swagger `ConItem` fields is not documented — read them defensively, as for `members`. |
| parameterKeys | array<string> | Parameter identifiers used in the template |
| commonProperties | `ConOperationCommonProperties` | Common weld/plate/bolt-assembly ids (see above) |

`ConItem` (one level, per swagger — but see the `members` caveat above): `id` (int), `name` (string), `active` (bool).

### DTO: TemplateConversions

| Field | Type | Notes |
|---|---|---|
| conversions | array<`BaseTemplateConversion`> | Polymorphic list; entries carry `$type` discriminators |
| countryCode | string | Country/design-code context of the conversions |

`BaseTemplateConversion` (base) fields: `originalValue` (string), `originalTemplateId` (string), `newValue` (string), `description` (string), `newTemplateId` (string).

**`$type` is declared on each SUBTYPE, not on the base** — and each subtype's `$type` property carries a `default` holding its exact wire value, so the string you must send is readable straight from the swagger. The base schema declares only the `discriminator` (`propertyName: "$type"`) whose `mapping` points at all 10 concrete subtypes; `TemplateConversions.conversions.items` is a `oneOf` over those 10. Each wire value is a long qualified string — send it verbatim as the swagger `default` gives it, e.g.:

```
"$type": "IdeaStatiCa.Api.Connection.Model.CssTemplateConversion, IdeaStatiCa.Api"
```

The subtype schemas are NOT closed (`additionalProperties` is not set to false), so an unknown extra property is not a schema violation.

Concrete polymorphic subtypes (all extend `BaseTemplateConversion`). **Only `MemberTemplateConversion` declares extra fields; the other 9 differ by `$type` identity alone (the 5 inherited base fields + `$type`).**
- `MemberTemplateConversion`: `isBearing` (bool, default false), `originalMemberName` (string), `newMemberName` (string). — the only subtype with own fields.
- `BoltAssemblyTemplateConversion`, `BoltGradeTemplateConversion`, `CssTemplateConversion`, `CleatTemplateConversion`, `ConcreteTemplateConversion`, `ElectrodeTemplateConversion`, `PlateMaterialTemplateConversion`, `TimberTemplateConversion`, `PinTemplateConversion`: base fields + `$type` only.

(Order matters: the entries are matched positionally, so keep the list as `get-default-mapping` returned it. On `apply-template` only `newValue`, `newTemplateId`, and — for member conversions — `newMemberName`/`originalMemberName` are read from the supplied mapping.)

> **Not expanded in this doc:** The get-template / `ConTemplateCreateResult.template` 'contemp' string has no concrete deserialization-target DTO with documented fields. Treat it as an opaque serialized template payload (operations, connection data, analysis info, loads, parameters, param-model links, section/clipping data) that is fed back verbatim into get-default-mapping/apply-template.


---

## ConnectionLibrary

Endpoints for browsing the connection design library (design sets and the design items / templates inside them), proposing matching templates for an open connection, fetching a template's XML or preview picture, and publishing a connection back into the library as a template.

All endpoints require the `ClientId` header. Endpoints are versioned; this documents the routes under base `http://localhost:5000/api/5`. 

Serialization note: responses use camelCase property names and enums become camelCase strings (e.g. `id`, `conDesignSetId`).

---

### GET /api/5/connection-library/get-design-sets

Returns all design sets available to the current user (predefined/IDEA, company, and private sets). No parameters beyond the `ClientId` header.

- Response 200 (application/json): `array<ConDesignSet>`

See **DTO: ConDesignSet** below.

---

### POST /api/5/projects/{projectId}/connections/{connectionId}/propose

Classifies the typology of the specified open connection and proposes matching design items (templates) from the library, filtered by the supplied search parameters. The connection's design code is taken from the connection itself; the search parameters only restrict which sets and which structural features are required/excluded.

- Path params: `projectId` (string, GUID of the open project), `connectionId` (integer, opaque CBFEM connection id).
- Request body (application/json): `ConConnectionLibrarySearchParameters`.
- Response 200 (application/json): `array<ConDesignItem>`.

Behavior notes:
- `members` is a list of member ids that scopes typology classification; empty/omitted means classify the whole connection.
- Each `SearchOption` feature flag (`hasBolts`, `hasWelds`, `hasAnchor`, `hasClipAngles`, `isMoment`, `isShear`, `isTruss`, `isParametric`) takes `ignore`, `must` (must have) or `mustNot` (must not have).
- `inPredefinedSet` / `inCompanySet` / `inPersonalSet` restrict which set kinds are searched (all default `true`).

See **DTO: ConConnectionLibrarySearchParameters** and **DTO: ConDesignItem** below.

---

### GET /api/5/connection-library/get-template

Returns the connection template for a design item as a `text/plain` string that is **Base64-encoded** — Base64-decode the body to get the `<ConnectionTemplate>` XML (it is NOT raw XML and NOT JSON). If the design item has no template, an empty 200 body is returned. Returns 404 if the design item id is not found in the library.

- Query params: `designSetId` (string, GUID — accepted but the lookup is performed by item id), `designItemId` (string, GUID).
- Response 200 (text/plain): `string` (connection template XML).

---

### GET /api/5/connection-library/get-picture

Returns the preview picture of a design item as a PNG image (binary file stream; download name `{designItemId}.png`).

- Query params: `designSetId` (string, GUID), `designItemId` (string, GUID).
- Response 200 (image/png): binary PNG image, not JSON.

---

### POST /api/5/projects/{projectId}/connections/{connectionId}/publish

Generates a template from the specified open connection (including a rendered preview picture and the embedded project bytes) and publishes it as a new design item into the user's Private or Company design set. Returns `true` on success.

- Path params: `projectId` (string, GUID of the open project), `connectionId` (integer, opaque CBFEM connection id).
- Request body (application/json): `ConTemplatePublishParam`.
- Response 200 (application/json): `boolean`.

Behavior notes: if `name` is omitted the connection header name (or `CON-{connectionId}`) is used; `companyName` and `author` default to `"ConnectionAPI"` when null; `designSetType` defaults to `Company`, and any value other than `Private` is treated as `Company`.

---

### DTO: ConDesignSet

| JSON field | Type | Notes |
|---|---|---|
| `id` | string (GUID) | Design set identifier (use as `designSetId`). |
| `name` | string | Display name of the set. |
| `description` | string | Description. |
| `ownerId` | string | Owner identifier. |
| `type` | string | Set kind as text. **Values are `"Idea"`, `"Private"`, `"Company"` (PascalCase-ish)** — this field breaks the API's usual lowerCamelCase enum convention (e.g. `CountryCode`'s `ecen`, `SearchOption`'s `ignore`). It's a plain `string` in swagger, not a typed enum, so don't assume a fixed casing guarantee. |

### DTO: ConDesignItem

| JSON field | Type | Notes |
|---|---|---|
| `version` | string | Template/format version. |
| `name` | string | Display name of the design item. |
| `designCode` | string | Design code of the template. |
| `conDesignSetId` | string (GUID) | Parent design set id (use as `designSetId`). |
| `conDesignItemId` | string (GUID) | Design item id (use as `designItemId` for get-template / get-picture). |

### DTO: ConConnectionLibrarySearchParameters

| JSON field | Type | Default | Notes |
|---|---|---|---|
| `members` | array<int> | `[]` | Member ids scoping typology classification. |
| `inPredefinedSet` | boolean | `true` | Include IDEA/predefined sets. |
| `inCompanySet` | boolean | `true` | Include company sets. |
| `inPersonalSet` | boolean | `true` | Include personal/private sets. |
| `hasBolts` | `SearchOption` | `ignore` | |
| `hasWelds` | `SearchOption` | `ignore` | |
| `hasAnchor` | `SearchOption` | `ignore` | |
| `hasClipAngles` | `SearchOption` | `ignore` | |
| `isMoment` | `SearchOption` | `ignore` | |
| `isShear` | `SearchOption` | `ignore` | |
| `isTruss` | `SearchOption` | `ignore` | |
| `isParametric` | `SearchOption` | `ignore` | |

`SearchOption` enum (serialized camelCase string): `ignore`, `must`, `mustNot`.

### DTO: ConTemplatePublishParam

| JSON field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | null | Published item name; falls back to connection header name or `CON-{connectionId}`. |
| `author` | string | null | Falls back to `"ConnectionAPI"`. |
| `companyName` | string | null | Falls back to `"ConnectionAPI"`. |
| `designSetType` | `ConDesignSetType` | `company` | Target set kind. |

`ConDesignSetType` enum (serialized camelCase string): `private`, `company`. Any value other than `private` is treated as `company`.

> **Not expanded in this doc:** the get-template response string is the IDEA StatiCa connection template (a manufacture XML/text payload), not a JSON-serialized public DTO — there is no public class the returned string deserializes into. Treat it as an opaque token.


---

## Conversion

Endpoints for converting a Connection project to a different national design code. **A project converts to any target listed under `change-code` except its own code, with the two exceptions below; `ecen` is never a target.** Asking for the code the project already has is 422 *"The project is already in design code 'American'."* on both endpoints — also for an `ecen` project asking for `ecen`. **A pin an operation uses blocks the conversion, whatever the target:** 422 naming the pins on both endpoints. A pin no operation uses does not block, and it is dropped from the converted project. **A reinforcement or headed-stud material blocks `change-code`, used or not:** 422 naming the material (*"Unsupported material B 500B"*, *"… SD1"*); `get-default-mapping` still answers 200. All endpoints require the `ClientId` header.

**Review and set every `targetValue` before `change-code`.** `get-default-mapping` suggests from a table keyed on the item's name; a name the table does not hold gets one generic value of the target code (e.g. `A36` for steel, `W16X36` for `canada` sections) — the common case for a non-Eurocode source, and possible for a Eurocode one (`HEB200` → `W21X68`). `change-code` applies the values exactly as you send them, cross-sections included; a name the target library does not hold is 422 *"Cross section '…' was not found in the MPRL database"*.

Both endpoints exchange the same DTO, `ConConversionSettings` — it is the response of `get-default-mapping` (the server fills in suggested target materials) and the request body of `change-code` (the caller sends back the finalized mappings). It is a plain JSON object, not a serialized string.


---

### GET /api/5/projects/{projectId}/get-default-mapping

Returns default conversion mappings from the source project's materials to the requested target design code. For each distinct material/cross-section/fastener in the project it produces a `ConversionMapping` whose `sourceValue` is the existing name and `targetValue` is the suggested replacement in the target code (how it is chosen: § Conversion).

- Path param: `projectId` — GUID of the opened project.
- Query param: `countryCode` — target design code, a `CountryCode` enum (serialized/accepted as a camelCase string; see enum below).
- Response 200 (`application/json`): `ConConversionSettings`.
- Errors: 401 (missing/invalid `ClientId`), 404 (project not found), 422 (the project already has that code, an operation uses a pin, or `countryCode=none` — *"A target design code must be specified."*), **501** for a target that is not a conversion target (`ecen` from any other code, `sia`: *"Conversion to design code 'SIA' is not supported."*).
- This project-level conversion `get-default-mapping` works on an empty project and returns the mapping for the project's library materials. The connection-level template endpoints (`get-template`, the connection-level `get-default-mapping`, `create-from-connection`) are the ones that need a connection with content — on a brand-new empty connection they return 500.

### POST /api/5/projects/{projectId}/change-code

Applies the supplied conversion table and rewrites the project's materials/cross-sections/fasteners to the target design code in place. The server validates that **every** material (Steel, Welds, Concrete, BoltGrade), bolt assembly, and cross-section present in the project has a corresponding `sourceValue` entry in the request (case-insensitive); any missing entry yields 422 listing the missing items.

- Path param: `projectId` — GUID of the opened project.
- Request body (`application/json`): `ConConversionSettings`. `targetDesignCode` selects the conversion routine.
- Response: **204 No Content** on success. The project is mutated server-side; no body is returned.
- **`steelEdition` is reset to the target code's default** (§ `ConProjectData` → `steelEdition`) on the project and every connection. Set the edition you want with `PUT /projects/{projectId}` after the conversion.
- Errors: 401, 404, 422 (the project already has that code, an operation uses a pin, a reinforcement or headed-stud material in the project, `none`/`sia` as target, or a conversion list missing an entry — *"Missing conversions: Missing Steel: 'S 355'"*), 501 (`ecen` as target).
- Supported `targetDesignCode` values: `canada`, `australia`, `rus`, `chn`, `india`, `hkg`, `american` — any of them except the project's own code.
- **Read a converted cross-section's steel from the model, not from its definition**: after the conversion `GET .../materials/cross-sections` still names the source steel in `definition.materialName` (e.g. `S 355`), while the model and `export-iom-connection-data` carry the mapped one (e.g. `A36`). Before re-posting such a definition, set `materialName` to a steel from `GET .../materials/steel`.

Note: this endpoint is serialized per project by a project lock.

---

### DTO: ConConversionSettings


| JSON property | Type | Notes |
|---|---|---|
| `targetDesignCode` | `CountryCode` enum | Target design code (camelCase string, e.g. `"american"`, `"canada"`). |
| `concrete` | `ConversionMapping[]` | Concrete material name mappings. |
| `crossSections` | `ConversionMapping[]` | Cross-section (short name) mappings. |
| `fasteners` | `ConversionMapping[]` | Bolt-assembly name mappings. |
| `steel` | `ConversionMapping[]` | Steel material name mappings. |
| `welds` | `ConversionMapping[]` | Welding-material name mappings. |
| `boltGrade` | `ConversionMapping[]` | Bolt-grade material mappings. |

### DTO: ConversionMapping


| JSON property | Type | Notes |
|---|---|---|
| `sourceValue` | `string` | Existing material/section/fastener name in the project. |
| `targetValue` | `string` | Replacement name in the target design code. |

### Enum: CountryCode


| Name (PascalCase) | Numeric | JSON (camelCase) | Meaning |
|---|---|---|---|
| `None` | 0 | `none` | No code |
| `ECEN` | 1 | `ecen` | Eurocode (never a conversion target) |
| `India` | 5 | `india` | India code |
| `SIA` | 6 | `sia` | Swiss code — not in the product (§ POST /projects); as a conversion target 422 on `change-code`, 501 on `get-default-mapping` |
| `American` | 8 | `american` | AISC/ACI/ASTM |
| `Canada` | 9 | `canada` | Canadian |
| `Australia` | 10 | `australia` | Australian |
| `RUS` | 11 | `rus` | Russian |
| `CHN` | 12 | `chn` | Chinese |
| `HKG` | 13 | `hkg` | Hong Kong |

(Note: short all-caps names like `ECEN`, `RUS`, `CHN`, `HKG`, `SIA` lower-case fully under camelCase.)


---

## Export

Endpoints for exporting a connection to interchange/CAD formats: IDEA Open Model (IOM) XML, the IOM `ConnectionData` object, IFC, and DWG. All four are `GET`, require the `ClientId` header, and are scoped to one connection (`projectId` GUID in path, `connectionId` int in path). An export is serialized with the project's writes and calculations, so it cannot race them.


### GET /api/5/projects/{projectId}/connections/{connectionId}/export-iom

Exports the connection as IOM XML. The response body is a raw XML **string** (`Content-Type: application/xml`, also advertised as `text/plain`) — not JSON, so the camelCase serialization rules do NOT apply here; it is IOM XML (OpenModelContainer format).

Parameters:
- `projectId` (path, string/GUID) — opened project id.
- `connectionId` (path, int) — connection to export.
- `version` (query, string, optional) — when provided, the IOM model is downgraded to that schema version via the IOM version downgrade before being returned (e.g. `"2.0.0"` is normalized to `"2"`). Omit it to get the current/native version.

The XML deserializes to **`OpenModelContainer`**. One level deep:

| Property | Type | Notes |
|---|---|---|
| OpenModel | OpenModel | Structural data (members, plates, materials, cross-sections, the connection point, etc.). |
| OpenModelResult | OpenModelResult | Finite-element analysis results, when present. |

No request body. Errors: 401 (missing/invalid ClientId), 404 (project/connection not loaded), 500.

**Encoding gotcha:** the response bytes are UTF-8, but the XML declaration says `encoding="utf-16"`. Before feeding the XML back to `import-iom-file` or `update-iom-file`, make the bytes match the declaration: decode the response as UTF-8 and re-encode the text as UTF-16 with BOM (in Python: `xml_bytes.decode("utf-8").encode("utf-16")`), or rewrite the declaration to match the bytes you send. The same XML then imports successfully; sending the response bytes unchanged fails with HTTP 500.

### GET /api/5/projects/{projectId}/connections/{connectionId}/export-iom-connection-data

Returns the IOM `ConnectionData` for the connection. Content negotiable: `application/json` (default, camelCase) or `application/xml`.

Parameters: `projectId` (path, string/GUID), `connectionId` (path, int). No request body.

Response: **`ConnectionData`**. One level deep:

| Property | Type | Notes |
|---|---|---|
| ConnectionPoint | ReferenceElement | The connection node reference. |
| Beams | `array<BeamData>` | Connected members. |
| Plates | `array<PlateData>` | Plates. |
| FoldedPlates | `array<FoldedPlateData>` | Folded (bent) plates. |
| BoltGrids | `array<BoltGrid>` | Bolt grids. |
| AnchorGrids | `array<AnchorGrid>` | Anchor grids. |
| PinGrids | `array<PinGrid>` | Pin grids. |
| Welds | `array<WeldData>` | Welds. |
| ConcreteBlocks | `array<ConcreteBlockData>` | Concrete blocks / foundations. |
| CutBeamByBeams | `array<CutBeamByBeamData>` | Beam-by-beam cut operations. |

> **Count the COLLECTION, never the type name.** In the JSON body the keys are the camelCased
> collection names — `plates`, `welds`, `beams`, `concreteBlocks` — and the type names in the
> table above (`PlateData`, `WeldData`, …) **do not appear in the payload at all**. Searching the
> raw text for `"PlateData"` returns 0 whatever the model contains, which reads as "nothing
> materialised" and is simply wrong. Parse the JSON and take `len(iom["plates"])`.

Selected nested DTOs, one level deep:

**`BeamData`** — `Name` (string), `Plates` (array of PlateData), `CrossSectionType` (string), `MprlName` (string), `OriginalModelId` (string), `Cuts` (array of CutData), `IsAdded` (bool), `AddedMemberLength` (double), `IsNegativeObject` (bool), `AddedMember` (ReferenceElement), `MirrorY` (bool), `RefLineInCenterOfGravity` (bool), `IsBearingMember` (bool), `AutoAddCutByWorkplane` (bool). (Plus `Id` from `OpenElementId`.)

**`PlateData`** — `Id` (int), `Name` (string), `Thickness` (double), `Material` (string), `OutlinePoints` (array of Point2D), `Origin` (Point3D), `AxisX`/`AxisY`/`AxisZ` (Vector3D), `Region` (string, SVG; the outer outline only — no openings), `Geometry` (Region2D: `outline` + `openings`), `OriginalModelId` (string), `IsNegativeObject` (bool — `true` on a negative plate, a cutting tool). **`OutlinePoints` comes back `null` in practice — the real outline is in `Geometry.outline`: `{startPoint: Point2D, segments: [{$type: LineSegment2D|ArcSegment2D, endPoint, ...}]}`, plate-frame 2D. World = `Origin + u·AxisX + v·AxisY` per vertex. The outline lies on the plate MIDSURFACE (thickness is centred on that plane; apply ±Thickness/2 along AxisZ for faces).**

**`WeldData`** — `Id` (int), `Name` (string), `Thickness` (double), `Material` (ReferenceElement — the weld material, `Id` `0` = automatic), `WeldType` (WeldType enum), **`IsIntermittent` (bool)**, **`ConnectedParts` (array of ReferenceElement** — each `{TypeName, Id}`, e.g. `{BeamData, 1}` + `{PlateData, 7}`; not a list of id strings), `Start` (Point3D), `End` (Point3D). `WeldType` serializes as a named enum (no raw ints), in IOM's own vocabulary — `Bevel`, `PJP`, `DoubleFillet` — which is NOT the REST spelling (`cjp`, `pjp`, `doubleFillet`); do not match the two by string. The stitch/intermittent character is carried separately in **`IsIntermittent`** (NOT folded into `WeldType`), so a stitch fillet reads `DoubleFillet` + `isIntermittent:true`. Read `isIntermittent`, not `weldType`, to detect stitch welds.

**`ConcreteBlockData`** — `Id` (int), `Name` (string), `Material` (ReferenceElement — `MatConcrete`), `Length` / `Width` (double — the plan size along the host plate's local x / y), `Height` / `Depth` (double — both the block height), `Center` (Point3D), `OutlinePoints` (array of Point2D), `Origin` (Point3D), `AxisX`/`AxisY`/`AxisZ` (Vector3D), `Region` (string SVG), `OriginalModelId` (string). Unlike PlateData, the block's outline IS in `OutlinePoints` (it has no `Geometry`); `Depth` extrudes along AxisZ. These are the elements `export-iom` writes; this endpoint lists each block (and each weld) only as a bare `{"id": N}` — `grids.md` § anchor-grid specifics.

**`FoldedPlateData`** — `Plates` (array of PlateData), `Bends` (array of BendData).

**`BendData`** — `Plate1Id` (int), `Plate2Id` (int), `Radius` (double), `Point1OfSideBoundary1`/`Point2OfSideBoundary1` (Point3D), `EndFaceNormal1` (Vector3D), `Point1OfSideBoundary2`/`Point2OfSideBoundary2` (Point3D).

**`CutBeamByBeamData`** — `Name` (string), `ModifiedObject` (ReferenceElement), `CuttingObject` (ReferenceElement), `IsWeld` (bool), `WebWeld` (WeldDefinition), `FlangeWeld` (WeldDefinition), `Offset` (double), `Method` (CutMethod enum), `Orientation` (CutOrientation enum), `PlaneOnCuttingObject` (DistanceComparison enum), `CutPart` (CutPart enum), `ExtendBeforeCut` (bool).

Enums serialize as camelCase strings: `WeldType` (notSpecified, fillet, doubleFillet, bevel, pjp, pjpRear, lengthAtHaunch, filletRear, contact, intermittent), `CutOrientation` (default, parallel, perpendicular), `CutMethod` (boundingBox, surface, mitre, surfaceAll), `CutPart` (begin, end), `DistanceComparison` (closer, farther, same).

`BoltGrid`, `AnchorGrid`, `PinGrid`, `ReferenceElement`, `OpenElementId`, `Region2D`, `Point2D`, `Point3D`, `Vector3D` are other IOM types in the `IdeaRS.OpenModel` namespace (public NuGet package `IdeaStatiCa.OpenModel`; referenced but not expanded here). Errors: 401, 404, 500.

### GET /api/5/projects/{projectId}/connections/{connectionId}/export-ifc

Exports the connection to IFC. The response is a **file stream** of the IFC text (`Content-Type: text/plain`, `Content-Disposition` filename `Connection_{connectionId}_{yyyyMMddHHmmss}.ifc`). The body is the IFC file content itself — there is no JSON DTO.

Parameters: `projectId` (path, string/GUID), `connectionId` (path, int). No request body. Errors: 401, 404, 500 (legacy v1-v3 overload returns 400 on failure).

#### What the IFC text contains

The only export channel that carries **solids together with element names**.

| entity | element |
|---|---|
| `IFCBEAM`, `IFCMEMBER`, `IFCCOLUMN` | member |
| `IFCPLATE` | plate |
| `IFCMECHANICALFASTENER` | bolt |
| `IFCFASTENER` | weld when its `ObjectType` (arg 5) is `WELD`, else bolt |

Name is **arg 3**, description arg 4: `#773=IFCPLATE('guid',#5,'PL',$,…)` → `PL`.

Geometry: product **arg 7** → `IFCPRODUCTDEFINITIONSHAPE` → `IFCSHAPEREPRESENTATION` → items.
IDEA emits **`IFCFACETEDBREP`** — sometimes wrapped in `IFCMAPPEDITEM` (adds a transform) or
`IFCBOOLEANRESULT` (first operand is the positive body). Each faceted brep references one
`IFCCLOSEDSHELL` whose single argument is the face list.

Cuts and plate openings arrive **baked into the shell**. **Bolt and anchor holes are the
exception**: each is an `IFCOPENINGELEMENT` tied to its plate by an `IFCRELVOIDSELEMENT`, so a
reader that renders the shell alone draws the plates without their holes — subtract the openings.
A `reinforcement` anchor has no opening and leaves the plate whole. Negative volumes have no
product — they are cutting tools, not bodies; a member they cut is an `IFCBOOLEANRESULT` whose
second operand is the tool's shape, so read the first operand.

A **member is one faceted brep made of separate plate boxes** — an I-section is three disjoint
boxes (two flanges and the web) in one closed-shell list, not one welded solid. **Welds are
grouped**: one `IFCFASTENER` (`ObjectType` `WELD`) carries several welds — its name lists the
joined parts (e.g. `'B, EP1, WID1a, WID1b'`), its description the type and throat
(`'DoubleFillet (5 mm)'`). Count welds from IOM, not from IFC fasteners.

Records are `#id=TYPE(args);`. **Arguments cannot be split on commas naively** — nesting depth
and `'`-quoted strings (with `''` escapes) have to be respected. Coordinates inside a faceted
brep are local; world position requires composing the `IFCLOCALPLACEMENT` parent chain.

### GET /api/5/projects/{projectId}/connections/{connectionId}/export-dwg

Exports the connection to DWG. This is a long-running export — the request blocks
until the DWG is ready (up to ~10 minutes) and then streams it back.

The response is a **binary file stream** (`Content-Type: application/octet-stream`,
download name `Connection_{connectionId}_{yyyyMMddHHmmss}.dwg`). There is no JSON response
body.

The client passes no auth beyond `ClientId` — the export reuses the machine's installed
IDEA license.

Parameters: `projectId` (path, string/GUID), `connectionId` (path, int). No request body.

Status/error behavior (ProblemDetails): 404 if the project or connection is not loaded; 502 if
the Viewer fails to open the project or start the export; 504 (Gateway Timeout) if the export
does not finish within ~10 minutes.

> **Not expanded in this doc** (consult the live spec if needed): OpenModel and OpenModelResult (referenced as the two members of OpenModelContainer; not expanded - large IOM root types in IdeaRS.OpenModel); BoltGrid / AnchorGrid / PinGrid (IOM grid types referenced by ConnectionData; not expanded); ReferenceElement / OpenElementId / Region2D / Point2D / Point3D / Vector3D (IOM base/geometry types referenced by ConnectionData members; not expanded)


---

## Report

All report endpoints (`reports/pdf`, `reports/word`, `reports/htmlZip`, and the
multi-connection POST variants) return file bytes (PDF `%PDF-`, Word/htmlZip a `PK` ZIP; typically a
few MB). **A report takes seconds to tens of seconds** — more when it has to
calculate first — so give report calls a generous timeout (the request is slow, not hung). No `calculate` is needed first — which results a report uses: `endpoints.md` § Report.

All Report endpoints stream a **raw binary file** (no JSON DTO in the success body). The response carries content type `application/octet-stream` and a `Content-Disposition` filename of the form `Connection_{ids}_{yyyyMMddHHmmss}.{ext}` (ext = `pdf`, `docx`, or `zip`). The output format is selected purely by the URL suffix (`/pdf`, `/word`, `/htmlZip`) — there is no format field in any request body. All endpoints require the `ClientId` header and are serialized per project. Which calculation a report uses: `endpoints.md` § Report.

The multi-connection endpoints validate the ids before rendering, so send only ids you have confirmed in the project: if none of the ids in the body exists (or the array is empty) the call fails fast with 422 and a `ProblemDetails` naming the offending input; mixing a valid id with one that does not exist fails with 404 naming the missing connection. Either way nothing is rendered — a failure is a few hundred bytes of `application/problem+json`, a success is `application/octet-stream` starting with the PDF/ZIP magic bytes.


### POST /api/5/projects/{projectId}/reports/pdf
Generates a single combined PDF report covering multiple connections.

- Path param: `projectId` (Guid as string).
- Request body: `array<integer>` — a required JSON array of connection ids. These are the per-project connection ids (the `id` on `ConConnection`), not the opaque solver ids. See the id-validation rule above the endpoint list.
- Response 200: binary PDF bytes. `Content-Type: application/octet-stream`, filename `Connection_{id1}-{id2}-..._{timestamp}.pdf`.
- Errors: 401 (missing/invalid ClientId), 404, 422, 500 — bodies are `ProblemDetails`.

### POST /api/5/projects/{projectId}/reports/word
Same as the PDF multi-connection endpoint but produces a Word document.

- Path param: `projectId` (Guid as string).
- Request body: `array<integer>` (required) — connection ids; same validation as the PDF variant.
- Response 200: binary Word (.docx) bytes. `Content-Type: application/octet-stream`, filename `Connection_{ids}_{timestamp}.docx`.
- Errors: 401 / 404 / 422 / 500 as `ProblemDetails`.

### GET /api/5/projects/{projectId}/connections/{connectionId}/reports/htmlZip
HTML report for a single connection, packaged as a ZIP archive (the full working directory of generated HTML + asset files is zipped).

- Path params: `projectId` (Guid as string), `connectionId` (integer).
- Request body: none (GET).
- Response 200: binary ZIP bytes. `Content-Type: application/octet-stream`, filename `Connection_{connectionId}_{timestamp}.zip`.
- Note: HTML report generation is blocked for Trial or Education licenses — those fail with an authorization error (401 or 500), not an empty ZIP.
- Errors: 401 / 404 / 500 as `ProblemDetails`.

### GET /api/5/projects/{projectId}/connections/{connectionId}/reports/pdf
PDF report for a single connection.

- Path params: `projectId` (Guid as string), `connectionId` (integer).
- Request body: none (GET).
- Response 200: binary PDF bytes. `Content-Type: application/octet-stream`, filename `Connection_{connectionId}_{timestamp}.pdf`.
- Errors: 401 / 404 / 500 as `ProblemDetails`.

### GET /api/5/projects/{projectId}/connections/{connectionId}/reports/word
Word report for a single connection.

- Path params: `projectId` (Guid as string), `connectionId` (integer).
- Request body: none (GET).
- Response 200: binary Word (.docx) bytes. `Content-Type: application/octet-stream`, filename `Connection_{connectionId}_{timestamp}.docx`.
- Errors: 401 / 404 / 500 as `ProblemDetails`.

### Notes on shapes
- There are no named request/response DTO classes for this group. The two POST bodies are plain `array<int>` (serialized as a JSON array of integers, e.g. `[1, 3]`). All success responses are binary file streams, not JSON, so the global camelCase serialization rules do not apply to the success payloads.
- The report detail level is fixed server-side and not exposed as a parameter.

> **Not expanded in this doc** (consult the live spec if needed): No named DTOs exist for the Report group: both POST request bodies are JSON `array<integer>` and all five success responses are raw binary file streams (PDF/.docx/.zip bytes), not serialized objects.


---

## Settings

Project-wide solver/check/code configuration. Settings are identified by a slash-joined key path plus an integer version. Over the wire both endpoints use a plain JSON object (key → value): the JSON property name is the slash-joined key path **without** the `@version` suffix, and the value is the raw setting value (number, bool, string, enum-as-string, or a small nested object), serialized one level deep.


### Key naming
Each key is a slash-joined path of parts, e.g. `calculationCommon/Checks/Shared/OptimalCheckLevel`.
It also has an integer version (default 1), which `PUT` accepts as an `@NN` suffix (zero-padded
to 2 digits, e.g. `@01`) and `GET` omits. A setting may exist at multiple versions; GET returns only the highest version per key path. Example real keys/values:
- `calculationCommon/Checks/Shared/OptimalCheckLevel` = `0.025`
- `calculationCommon/Checks/Shared/WarningCheckLevel` = `0.92`
- `calculationCommon/Checks/Shared/LocalDeformationLimit` = `0.025`

The dictionary's size depends on the design code, and an older file can carry fewer keys —
fetch it and count rather than expecting a number.

**Solver knobs live here too, and they change what the results contain.** Example:
`calculationCommon/Model/Solver/Shared/NumberOfBucklingModes` sets how many buckling shapes are
computed, and `/results` returns `bucklingResults` = that many **per calculated load effect** (2
modes → 4 entries across 2 load effects; 5 → 10). The key round-trips through
`PUT .../settings` and the new count applies to the next `calculate`. A parallel
`Model/Member_Solver/...` copy exists for the Member application — edit the one whose branch
matches the app you are driving.

**Material partial safety factors (γ_M0 etc.) are here.** The Eurocode factors are plain numeric settings under `calculation/Analysis/CodeFactors/EN/...`:
- `calculation/Analysis/CodeFactors/EN/GammaM0` (yielding; default 1.0)
- `.../GammaM1` (instability; 1.0) · `.../GammaM2` (ultimate/fracture; 1.25) · `.../GammaM3` (preloaded bolts) · `.../GammaC` (concrete) · `.../GammaInst` · `.../GammaMfi` · `.../GammaMu`

(Other codes use their own suffix, e.g. `.../US`.) `PUT` with `{"calculation/Analysis/CodeFactors/EN/GammaM0": 1.5}` returns 200 and the value sticks. **γ_M0 affects the code check of the next `calculate`, not the stored load effects** (their forces do not change with it).

> **A project created with `POST /projects` or saved by the desktop carries the full settings set.** An older file can hold fewer keys, some only a handful; a `PUT` to a key the project lacks is 404 *"Setting … was not found in settings."* One path segment names the design code (`cost/EN/…`, `materials/US/…`, `calculation/Analysis/CodeFactors/EN/GammaM0`; `…/Shared/…` for code-independent ones), so a key exists only in projects of that code. **What `GET` returns, `PUT` takes back unchanged**, for every key of every code.
>
> Value shapes to know before writing one:
> - **Library picks are an `ItemId` + `TableId` GUID pair** — `materials/<code>/MaterialDefaults/*` (two keys per pick), `design/.../CleatSectionId`, and `steelGradeId` / `boltGradeId` inside unit-cost rows (`{"itemId":…,"tableId":…}`). Copy a pair already present in the project: no API response maps a pair to a name, and any well-formed GUID is accepted unchecked.
> - **Unit-cost tables** (`cost/<code>/CostDefaults/*/UnitCosts`) come back as a `$type`-tagged object but are also accepted as a plain array, e.g. `[{"steelGradeId": null, "unitCost": 2.5}]` (`null` = *All unspecified*). `plateThickness` and `boltDiameter` in those rows are **lower bounds in metres** — `0.006` is *≥ 6.0 mm*, `0.02` is *≥ M20*; for fillet welds the value is the throat thickness. Costs are per kg in `CurrencyUnitSymbol`.
> - **A text setting holding an ISO date-time with seconds (`…T07:08:09`, with or without an offset) is stored re-rendered** — `"2021-05-06T07:08:09"` reads back `"05/06/2021 07:08:09"`, any offset dropped; other text, other date forms included, is kept as sent.
> - **Enum settings publish no list of values**; take them from a project that holds the value you want.
> - The material defaults do not reach elements added later — an operation without `materialId` gets the project's first steel either way (`operations.md`).

### GET /api/5/projects/{projectId}/settings
Gets setting values for the project.

- Headers: `ClientId` (required).
- Path: `projectId` (GUID).
- Query: `search` (optional, string). Case-insensitive; matches a setting if **any single key part** equals the search term exactly. It is a whole-part match, not a substring match. **Omit `search` entirely to get the COMPLETE settings dictionary** — this is the reliable way to discover every available key (incl. the γ_M0 etc. paths) and its current value. ⚠️ `search` is a whole-key-part exact match, so `search=GammaM0` works (it's a full part) but `search=Gamma` returns nothing (no key part is literally "Gamma"); when unsure, fetch ALL (no `search`) and filter client-side.
- Response 200 `application/json`: a JSON object (key → value). Property names are the version-less slash-joined key paths; values are the current setting values. Only the highest version of each key is returned.
- Errors: 401 (missing/invalid ClientId), 404 (project not found), 500.

A term that is not a whole key part returns zero, which looks identical to "no such setting" — so when a search comes back empty, re-fetch without `search` and filter client-side before concluding the key does not exist.

Example response (truncated):
```json
{
  "calculationCommon/Checks/Shared/OptimalCheckLevel": 0.025,
  "calculationCommon/Checks/Shared/WarningCheckLevel": 0.92,
  "calculationCommon/Checks/Shared/LocalDeformationLimit": 0.025
}
```

### PUT /api/5/projects/{projectId}/settings
Updates one or multiple setting values in the project.

- Headers: `ClientId` (required). Writes to one project are serialized.
- Path: `projectId` (GUID).
- Request body `application/json`: a JSON object (key → value) of key -> new value. Keys may be supplied **with or without** the `@version` suffix (e.g. both `calculationCommon/Checks/Shared/OptimalCheckLevel` and `...OptimalCheckLevel@01` work). Only keys that already exist are accepted.
- Value conversion: each value is read as JSON and converted to the stored setting's type. Enums are case-insensitive and also take their integer value; a number may come as `7`, `7.0` or `"7"`. **Send integers to integer settings** — a fraction is rounded silently (`7.5` → `8`), the string `"8.0"` is 422. **`null` is refused** for every type (422), an empty string is a valid text value. A value that does not convert is 422 naming the key and the type — *"Failed to convert setting '…/NumberOfBucklingModes' value \"many\" to type Int32: …"*.
- Versioning rule: if a key is sent with an explicit `@version` that is **older** than the stored version, that update is silently skipped (not an error). A newer `@version` than the stored one is accepted and written; the stored version does not change.
- **Send each setting once.** The same key twice — in another casing, or once bare and once with the stored `@version` — is 422 *"Settings 'a' and 'b' name the same setting; send it once."* An older-version key skipped by the rule above does not count as a second copy.
- **A batch is all or nothing.** Every key and value is checked before any is written: a 404 or 422 names the first failing key in body order and leaves every setting as it was. Fix that key and send the whole batch again.
- Response 200 `application/json`: a JSON object (key → value) containing only the settings that were updated, keyed by the version-less key name, with their newly converted values.
- Errors: 401 (missing/invalid ClientId), 404 (project not found, or a supplied setting key does not exist), 422 (a value could not be converted to the setting's type, or a setting sent twice), 500.

Example request:
```json
{
  "calculationCommon/Checks/Shared/OptimalCheckLevel": 0.03,
  "calculationCommon/Checks/Shared/WarningCheckLevel@01": 0.9
}
```
Example response echoes the applied changes:
```json
{
  "calculationCommon/Checks/Shared/OptimalCheckLevel": 0.03,
  "calculationCommon/Checks/Shared/WarningCheckLevel": 0.9
}
```

Note: there is no fixed DTO schema for the object's properties — the property set is the project's settings catalog (its size depends on the design code — fetch it and count), and value types are per-setting (mostly numeric/bool, some enums serialized as camelCase strings, occasionally small nested objects). Each value is the stored value, documented one level deep only.

> **Not expanded in this doc** (consult the live spec if needed): The concrete per-setting value types and the full enumeration of the setting key paths are not declared by a single DTO; the settings object is open-ended, so individual setting value schemas (e.g. nested-object settings) are not statically typed.


---

## Presentation

The Presentation group returns geometry/visualization data for a connection, intended for the IDEA StatiCa Scene3D viewer (npm package `@ideastatica/scene`). Both endpoints return the *same payload*: a serialized `DrawData` object. The difference is only the content type and how it is wrapped.


**Serialization note (this group is special).** In this payload, unlike the rest of the API:
- Property names are camelCase (as elsewhere) and enums are camelCase strings.
- Null properties are omitted from the JSON.
- There is **no `$type` discriminator**. Each group carries a `type` field (`"singleColor"` or `"multipleColor"`), and `selected.type` carries a `kind` field (`"member"`, `"plate"`, `"weld"`, `"boltGrid"`, …). The variant's fields appear directly.

### GET /api/5/projects/{projectId}/connections/{connectionId}/presentations
Returns data for Scene3D visualization.
- Headers: `ClientId` (required).
- Path params: `projectId` (string/GUID), `connectionId` (integer).
- Response `200` (`application/json`): a `DrawData` object (see DTO below). Delivered as an already-serialized JSON string.

### GET /api/5/projects/{projectId}/connections/{connectionId}/presentations/text
Returns the exact same Scene3D `DrawData` payload, but as `text/plain`.
- Headers: `ClientId` (required).
- Path params: `projectId` (string/GUID), `connectionId` (integer).
- Response `200` (`text/plain`): a string whose contents are the JSON serialization of a `DrawData` object. In other words, the response body is identical to the `presentations` endpoint, just delivered with content type `text/plain` instead of `application/json`. Deserialize it as `DrawData`.

### DTO: DrawData

| Field (JSON) | Type | Notes |
|---|---|---|
| `groups` | array<`IGroup`> | Drawing groups; each is a single-colour or a multiple-colour group (see below). |
| `vertices` | `array<double>` | Flat vertex coordinate buffer (x,y,z triples). |
| `normals` | `array<double>` | Flat normal vector buffer. |

The remaining shapes below are the one-level expansions of the types referenced by `DrawData`.

#### Group variants (`IGroup`)
A group is one of two variants, told apart by its `type` string (there is no `$type`): `"singleColor"` or `"multipleColor"`. Fields both carry: `faces`, `selected`, `lines`, `priority`, `text`.
> Swagger flattens `IGroup` to the shared fields only (`{faces, selected, lines, priority, text}`, `additionalProperties:false`) — it does NOT emit the two variants nor the `type`/`color`/`colorSpectrum`/`values` fields. The live payload DOES carry `type` + `color` — so trust the variant tables below over the swagger `IGroup` schema (swagger is lossy here).

Single-colour group (`type` = `"singleColor"`):

| Field (JSON) | Type | Notes |
|---|---|---|
| `color` | `array<int>` | Single color (e.g. RGBA components). |
| `faces` | `array<int>` | Indices into the vertex/normal buffers. |
| `selected` | `Selected` | Selection metadata (omitted if null). |
| `dependsOn` | object | Conditional coloring info (omitted if null; fields below). |
| `lines` | `array<Line>` | Edge/line geometry. |
| `priority` | `int` | Render priority. |
| `text` | `array<Text>` | Text labels attached to the group. |
| `type` | `string` | Constant `"singleColor"`. |

Multiple-colour group (`type` = `"multipleColor"`):

| Field (JSON) | Type | Notes |
|---|---|---|
| `colorSpectrum` | `array<ColorSpectrum>` | Color gradient ranges (for result/stress plots). |
| `displacement` | `array<double>` | Per-vertex displacement values. |
| `faces` | `array<int>` | Face indices. |
| `selected` | `Selected` | Selection metadata (omitted if null). |
| `lines` | `array<Line>` | Edge/line geometry. |
| `priority` | `int` | Render priority. |
| `text` | `array<Text>` | Text labels. |
| `type` | `string` | Constant `"multipleColor"`. |
| `values` | `array<double>` | Per-vertex scalar values mapped onto the spectrum. |

#### `colorSpectrum` entry
| Field (JSON) | Type | Notes |
|---|---|---|
| `color` | `array<int>` | Color for this spectrum band. |
| `from` | `double` | Lower bound of the value range. |
| `to` | `double` | Upper bound of the value range. |

#### Line
| Field (JSON) | Type | Notes |
|---|---|---|
| `color` | `array<int>` | Line color. |
| `pairs` | `array<int>` | Vertex index pairs defining segments. |
| `thickness` | `double` | Line thickness. |

#### Text
| Field (JSON) | Type | Notes |
|---|---|---|
| `color` | `array<int>` | Text color. |
| `value` | `string` | Text content. |
| `position` | `TextPosition` | Placement (origin + angles). |
| `fontSize` | `double` | Font size. |
| `tag` | `double` | Numeric tag. |

#### TextPosition
| Field (JSON) | Type | Notes |
|---|---|---|
| `origin` | `array<double>` | Position coordinates. |
| `angles` | `array<double>` | Orientation angles. |

#### Selected
| Field (JSON) | Type | Notes |
|---|---|---|
| `id` | `string` | Id of the selected item. |
| `type` | `SelectedType` | `{kind}` — what the group is (see below). |

#### `dependsOn`
| Field (JSON) | Type | Notes |
|---|---|---|
| `color` | `array<int>` | Colors applied when the dependency is selected. |
| `id` | `Selected` | The item this group's appearance depends on. |

#### `selected.type` kinds
`selected.type` is an object whose `kind` string names what the group is (there is no `$type`). Values: `wall`, `opening`, `lineSupport`, `wireFabric`, `aroundOpening`, `groupOfBar`, `loadCase` (which also carries `impulsId`: string), `member`, `plate`, `boltGrid`, `pin`, `anchor`, `concreteBlock`, `weld`, `tendon`. For connection presentations the relevant kinds are typically `member`, `plate`, `boltGrid`, `pin`, `anchor`, `concreteBlock`, `weld`, `tendon`. Only `loadCase` adds a field beyond `kind`.

> Note: `DrawData` is available as a public SDK DTO; consume that shape.


---
