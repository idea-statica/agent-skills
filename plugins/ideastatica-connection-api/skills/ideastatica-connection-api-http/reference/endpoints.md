# Connection REST API — endpoint catalog

All paths are relative to base URL `http://localhost:5000`. Every endpoint
except `connect-client` and `idea-service-version` requires the `ClientId` header.

Source of truth: the running service's own spec — **count it rather than quoting a figure**, the
surface differs between builds.

Swagger UI is at `/` (which redirects to `/index.html`) — **not** at `/swagger`, which is a
404. Each served version publishes its own document at `/swagger/<version>/swagger.json`, and
the response headers name the current one (`api-supported-versions` / `api-deprecated-versions`).

> **v5 is current; v4 is deprecated and fully functional.** **Every version from v1 to v5 is
> served** — `connect-client` and the spec answer 200 on all five — and v1–v4 are deprecated
> (their swagger titles carry "(deprecated)"). v4 is frozen, so anything newer exists only on
> v5. Its swagger says: *"still served, but it will be removed in a later release. Use version
> 5.0."* No date is given.
>
> **The whole v4→v5 difference is cross-sections plus one load-effect route.** v5 = v4 plus
> six cross-section routes, one `{cssId}/geometry` sub-resource, and
> `DELETE .../load-effects` (delete all); no other route, and no request body of a surviving
> route, differs; the rows below marked **not on v4** are those. One response differs: the
> cross-section list/create pair answers an IOM cross section on v4 (`cross-sections.md`). One
> path parameter differs: the per-template routes take the int `templateId` on v5 and the library
> GUID on v4 (`io-shapes.md` § Template). To check another
> service, diff the two specs' path sets.
>
> **All 13 typed modelling operations answer on both versions**, and every v4 route is also
> served on v5.

**This page vs `io-shapes.md`:** this one is **paths and per-endpoint behaviour** — which
routes exist, their methods, parameters, status codes, and the async job flow. `io-shapes.md`
is **field shapes** — what a request body and a response actually contain, under the names the
service really reads. Looking for a route → here. Looking for a field name or spelling
(e.g. `mprlName` for a cross-section) → `io-shapes.md` § Material.

The section names below are the swagger tags, so search by the tag you already have.

## Client

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/clients/connect-client` | Connects a client to the ConnectionRestApi service and returns a unique identifier for the client. |
| GET | `/api/5/clients/idea-service-version` | Gets the IdeaStatica API assembly version. |

## Project

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects` | Gets the list of projects in the service that were opened by the connected client. |
| POST | `/api/5/projects` | Creates a new IdeaCon project. It is NOT empty of connections — it ships with a default empty connection CON1 (id 1). |
| POST | `/api/5/projects/import-iom-file` | Create the IDEA Connection project from IOM provided in xml format. |
| POST | `/api/5/projects/open` | Opens an IdeaCon project from the provided file. |
| GET | `/api/5/projects/{projectId}` | Get data of the project. |
| PUT | `/api/5/projects/{projectId}` | Updates ConProjectData of project. |
| GET | `/api/5/projects/{projectId}/close` | Closes the project and releases resources in the service. **A GET with a side effect** (204): it closes the project; later calls on it answer 404. |
| GET | `/api/5/projects/{projectId}/download` | Downloads the current IdeaCon project from the service, including all changes made by previous API calls. |
| POST | `/api/5/projects/{projectId}/update-iom-file` | Update the IDEA Connection project by an `OpenModelContainer` (model and results; the type is in the public NuGet package `IdeaStatiCa.OpenModel`). |

## Connection

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/connections` | Gets data about all connections in the project. |
| POST | `/api/5/projects/{projectId}/connections` | Adds a new empty connection to the project. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}` | Deletes a specific connection from the project. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}` | Gets data about a specific connection in the project. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}` | Updates data of a specific connection in the project. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/copy` | Creates a copy of an existing connection in the project. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/get-topology` | Gets the topology of the connection in JSON format. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/production-cost` | Gets the production cost of the connection. |

## LoadEffect

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects` | Gets all load effects defined in the specified connection. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects` | **not on v4** (400 *unsupported API version* there) — Deletes every load effect with its internal forces; 200 returns the deleted ids (`[]` when none). Load effects posted afterwards are numbered from 1. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects` | Adds a new load effect to the connection. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects` | Update load impulses in conLoading. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/calculate-load-extremes` | Calculates load extremes for the connection and keeps only the critical load effects active. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/get-load-settings` | Get Load settings for connection in project. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/set-load-settings` | Set Load settings for connection in project. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/{loadEffectId}` | Delete load effect loadEffectId. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/load-effects/{loadEffectId}` | Gets load impulses from the specified load effect. |

## Calculation

| Method | Path | Summary |
|---|---|---|
| POST | `/api/5/projects/{projectId}/connections/calculate` | Runs CBFEM calculation and returns the summary of the results. |
| POST | `/api/5/projects/{projectId}/connections/rawresults-text` | Gets JSON string which represents raw CBFEM results (an instance of CheckResultsData). |
| POST | `/api/5/projects/{projectId}/connections/results` | Gets detailed results of the CBFEM analysis. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/calculate` | Runs CBFEM calculation of a single connection and returns the summary of the results. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/rawresults-text` | Runs CBFEM calculation of a single connection and gets a JSON string which represents its raw CBFEM results. |

The two **single-connection** variants take the connection in the PATH (no body array) and
accept an optional **`?loadEffectIds=`** query (repeatable / array) to calculate a SUBSET of
the connection's load effects. The plural forms above take the bare JSON array of connection
ids as the body and have no such selector. Response of the singular `calculate` is one
`ConResultSummary` object, not an array.

**One calculation per project at a time.**
- A second `calculate-async` while a job runs answers **409**. A `calculate-async` sent while a
  synchronous `calculate` runs waits for it and then answers 202.
- These wait until the running calculation ends, then answer normally: a synchronous
  `calculate`, `rawresults-text`, every write, `POST .../connections/results`,
  `GET .../download`, `GET .../export-iom`, `GET .../export-iom-connection-data`,
  `GET .../export-ifc`, `GET .../export-dwg`, every report (`GET .../reports/*` of one
  connection, `POST .../reports/*`) and every typed operation read
  (`GET .../operations/{kind}` and `GET .../operations/{kind}/{operationId}`).
- The other GETs (project, connections, members, the plain `GET .../operations` list,
  settings, materials, load effects, load settings, `GET .../presentations/text`) answer at
  once.
- For a long run use `calculate-async`, or give the client a timeout longer than the run.
  Dropping a synchronous calculate request (client timeout, closed socket) cancels that
  calculation and leaves the project unlocked, but the connection can keep partial results
  (some load effects) — calculate it again.

**`?loadEffectIds=` is the authoritative list of what to solve — it OVERRIDES the `active`
flag.** A load effect that is `active:false` still gets calculated when its id is listed.
The full numeric `resultSummary` is identical with the LE active or deactivated.
`active` only decides anything when you do NOT pass the selector. An unknown id is rejected —
`?loadEffectIds=99` → **422** `"Load effects [99] were not found in connection 1."`

**The selector does NOT carry over between the two endpoints.** `rawresults-text` is itself a
calculating endpoint — it re-runs CBFEM on its own terms rather than reading back what
`calculate` just produced. So `calculate?loadEffectIds=1` followed by a bare `rawresults-text`
silently gives you raw results for ALL active LEs. Pass the selector to **each** call that must
be restricted; `rawresults-text?loadEffectIds=1` honours it (`analysis` → `['1']`, and
`?loadEffectIds=99` → 422).

Signals for "was the subset honoured?" — the governing `loadCaseId` in `resultSummary` (follows
the selection), and run time (a subset run is visibly shorter). The
`analysis` key set of `rawresults-text` tracks that call's OWN scope: it has one entry per
**active** LE when called bare, and one per **selected** LE when called with the selector — so
it is only a valid oracle for the call that produced it, never for a previous `calculate`.

> **With no active load effects, `calculate` says so.** You get 200, `passed: false`, and a
> single `resultSummary` row: `name: "Analysis"`, `checkStatus: false`, `checkValue: 0.0`,
> and a `unityCheckMessage` ENDING with `There are no loads on members` — other complaints are
> concatenated in front of it (`"Plate clash warning Weld clash warning There are no loads on
> members"`), so match a substring, not the whole string. So `passed: false` does not by itself
> mean the joint failed — **read `unityCheckMessage`** to tell "nothing to solve" from a real
> failure. Do not test for an empty `resultSummary`: it is never empty. The same answer comes
> back whether the load effects are merely inactive or absent altogether.
>
> **A connection with no MEMBERS is a different failure with a similar look**: the row reads
> `CBFEM analysis failed - the solver did not produce any results.` and says nothing about
> loads. Don't collapse the two — one means "nothing to solve", the other "nothing to solve
> WITH".

## CalculationJobs (asynchronous calculation)

| Method | Path | Summary |
|---|---|---|
| POST | `/api/5/projects/{projectId}/connections/calculate-async` | Starts an asynchronous CBFEM calculation job for the given connections. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/calculate-async` | Starts an asynchronous CBFEM calculation job for a single connection. |
| GET | `/api/5/projects/{projectId}/calculation-jobs/{jobId}` | Gets the current state of a job: status, the connection currently being calculated with its per-load-case solver progress, and — once finished — the result summaries. |
| DELETE | `/api/5/projects/{projectId}/calculation-jobs/{jobId}` | Requests cancellation: the in-flight solver process is killed and remaining connections are skipped. |

Both `calculate-async` forms return **202** with a `ConCalculationJob`; the single-connection
form also accepts `?loadEffectIds=`. Poll `GET .../calculation-jobs/{jobId}` until `status`
is terminal. **409** on start = a job is already running for that project (§ Calculation).

`ConCalculationJob`: `jobId` (uuid), `projectId` (uuid), `status`, `progress` (double),
`connectionIds` (int[]), `connectionsCompleted` (int), `currentConnectionId` (int, nullable),
`createdAt`, `finishedAt` (nullable), `message` (nullable), `error` (nullable),
`results` (`ConResultSummary[]`, populated once finished).

**`progress` is the fraction (0..1, not 0..100) of load effects finished in the CURRENT
connection.** It restarts at 0 for each connection of a multi-connection job and reads 1.0 when
the job finishes. For the overall progress of the job use `connectionsCompleted` against
`connectionIds`.

Three more fields worth reading alongside it:
- `connectionsCompleted` / `connectionIds.length` — the job's progress in whole connections.
- `currentConnectionId` — the connection being solved right now.
- `message` — the live solver line, naming the load effect and iteration.

`ConCalculationJobStatusEnum` = `queued` | `running` | `finished` | `failed` | `cancelled`.

**Cancelling.** `DELETE .../calculation-jobs/{jobId}` answers **202**; its body may still read
`running`. Poll the job until its status is terminal: `cancelled`, or `finished` / `failed` if
it ended first. A cancelled job's `results` is null. A connection the job finished keeps its new
results. What a connection the cancel interrupted holds afterwards depends on timing — it can be
empty, or carry partial or complete new results — so read `POST .../connections/results` per
connection afterwards and calculate again every connection the job did not finish. A DELETE on a
finished job answers 202 and leaves it `finished`; an unknown job id is 404.

## Member

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/members` | Gets information about all members in the connection. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/members` | Adds a new member to the connection. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}/members` | Updates the member in the connection with the provided data. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/members/{memberId}` | Deletes the specified member from the connection. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/members/{memberId}` | Gets information about the specified member in the connection. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}/members/{memberId}/set-bearing-member` | Set bearing member for memberId. |

## Operation

| Method | Path | Summary |
|---|---|---|
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/operations` | Delete all operations for the connection — the applied templates and the parameters go too (`io-shapes.md`). |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/operations` | Gets the list of operations for the connection. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/operations/common-properties` | Gets common operation properties. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}/operations/common-properties` | Updates common properties for all operations. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/operations/weld-sizing` | Pre-designs welds in the connection. |

### Typed operations (see `reference/operations.md`)

> All 13 kinds are available. To check another service, ask the collection route:
> `GET .../connections/{id}/operations/<kind>` → 200 means available, 404 means the route is absent
> (`GET .../operations` still answers `200 []` in that case, so it is the route missing, not the
> project). Do not probe `.../operations/weld/1` for this — an id that exists under another kind
> answers **409**, and an absent one 404, so it cannot tell "no such route" from "no such operation".

Uniform pattern for each `{kind}` ∈ `weld`, `cut`, `plate-cut`, `bolt-grid`, `anchor-grid`,
`pin-grid`, `contact`, `contact-grid`, `negative-member`, `negative-plate`,
`stiffening-member`, `stiffening-plate`, `work-plane` — **13 kinds, on 2 path templates**
(`/{kind}` carries GET+POST+PUT, `/{kind}/{operationId}` carries GET). Two extra
non-CRUD helper paths also live under `/operations/` (`common-properties`, `weld-sizing`),
so the swagger shows 15 `/operations/*` path stems in total, not 13.

| Method | Path | Summary |
|---|---|---|
| GET | `.../operations/{kind}` | Lists the connection's operations of that kind (full typed DTOs). |
| POST | `.../operations/{kind}` | Adds a new operation of that kind. Returns `{operation, issues, addedWithoutIssues}`. A body `id` already in use replaces that operation when it is of the same kind, **409** otherwise. |
| PUT | `.../operations/{kind}` | Replaces the whole operation selected by the body's `id` — no merge with the stored one, so send its typed GET body with your changes (`operations.md`). Same result wrapper. 404 for an unknown id, **409** for an id of another kind. |
| GET | `.../operations/{kind}/{operationId}` | Gets one operation. **409 if the id exists but is a different kind** (the detail names both types); 404 if it exists in no kind. |
| — | `.../operations/common-properties`, `.../operations/weld-sizing` | Helper endpoints (not per-kind CRUD). |

No per-operation DELETE exists — only `DELETE .../operations` (all at once).

**There is no PUT on the single-operation path either.** All 13 typed `.../operations/{kind}/{id}`
endpoints expose **GET only**, so `PUT .../operations/pin-grid/{id}` returns **405**. Updates go
through the collection form `PUT .../operations/{kind}` with the target chosen by the body's `id`
— the same shape as `PUT .../load-effects`. Round-tripping works for a `userPositions`
grid: GET it, PUT the unmodified body back through the collection form, and the fasteners
survive; layer grids: `grids.md`.

## Material

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/materials` | Gets materials used in the specified project. |
| GET | `/api/5/projects/{projectId}/materials/bolt-assemblies` | Gets bolt assemblies used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/bolt-assemblies` | Add bolt assembly to the project. |
| GET | `/api/5/projects/{projectId}/materials/bolt-grade` | Gets materials used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/bolt-grade` | Adds a material to the project. |
| GET | `/api/5/projects/{projectId}/materials/concrete` | Gets materials used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/concrete` | Adds a material to the project. |
| GET | `/api/5/projects/{projectId}/materials/cross-sections` | Gets cross sections used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/cross-sections` | Add cross section to the project by `mprlName`. **The response carries NO geometry** — read it from the `/geometry` sub-resource below. |
| GET | `/api/5/projects/{projectId}/materials/cross-sections/{cssId}` | **not on v4** — `id`, `name` and the full `definition`; **no geometry** — that is the `/geometry` sub-resource below. `cross-sections.md`. |
| GET | `/api/5/projects/{projectId}/materials/cross-sections/{cssId}/geometry` | **not on v4** — the outline as its own sub-resource. |
| GET | `/api/5/projects/{projectId}/materials/cross-sections/parametric/shapes` | **not on v4** — The 26 parametric shape names. |
| GET | `/api/5/projects/{projectId}/materials/cross-sections/parametric/shapes/{shapeType}` | **not on v4** — Template for one shape: every dimension with its `$type`, `name` and default value; it is itself a valid POST body once `materialName` is set. |
| POST | `/api/5/projects/{projectId}/materials/cross-sections/parametric` | **not on v4** — Create from dimensions. Body is the definition itself — the shape template with `materialName` set; `shapeType` required (400 when omitted or null), `materialName` required (422). Returns `id`, `name`, `definition` — no geometry. |
| PUT | `/api/5/projects/{projectId}/materials/cross-sections/parametric/{cssId}` | **not on v4** — Update the dimensions of a parametric section. |
| PUT | `/api/5/projects/{projectId}/materials/cross-sections/library/{cssId}` | **not on v4** — Replace a library section in place (`mprlName`, `materialName`, mirrors); members using the id follow. `cross-sections.md`. |
| GET | `/api/5/projects/{projectId}/materials/headed-stud-grade` | Gets materials used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/headed-stud-grade` | Adds a material to the project. |
| GET | `/api/5/projects/{projectId}/materials/pin` | Gets pins used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/pin` | Add pin to the project. **ECEN design code only.** |
| GET | `/api/5/projects/{projectId}/materials/reinforcement` | Gets materials used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/reinforcement` | Adds a material to the project. |
| GET | `/api/5/projects/{projectId}/materials/steel` | Gets materials used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/steel` | Adds a material to the project. |
| GET | `/api/5/projects/{projectId}/materials/welding` | Gets materials used in the specified project. |
| POST | `/api/5/projects/{projectId}/materials/welding` | Adds a material to the project. |
| GET | `/api/5/projects/{projectId}/materials/{materialType}/library` | Lists the MPRL names available in the material library for the project's design code. |

### `materials/{materialType}/library` — discovering the names you may send

Returns a bare `array<string>` of MPRL names valid for the project's design code — the
answer to "what name may I send?". **`materialType` accepts nine values, and every library
you need is among them:**

`steel` · `concrete` · `bolt-grade` · `welding` · `headed-stud-grade` · `reinforcement` ·
`pin` · `cross-sections` · `bolt-assemblies`

Library sizes on an ECEN project: 96 steels, 16 concretes, 8 bolt grades, 14 welding, 2
headed-stud grades, 11 reinforcement, 6 pins, **tens of thousands of cross-sections**, **133 bolt
assemblies** (an `american` project: 43 steels, 94 bolt assemblies; pins are ECEN only). So discover the name from the library rather than knowing it out-of-band.

`materialType` is matched exactly: send `cross-sections` and `bolt-assemblies` in that
hyphenated plural form. camelCase or singular variants (`crossSection`, `css`, `section`,
`boltAssembly`, …) are refused with a 422 whose message lists the nine accepted values — read
that message rather than guessing at spellings.

The library is design-code specific: the same call on an Indian project heads `E 250
(Fe 410 W)` and on a Chinese one `Q235`, so create the project with the `countryCode` you
want first.

Note the two GET flavours per material type: `GET .../materials/{type}` = what this project
uses; `GET .../materials/{type}/library` = what the design code offers.

## Parameter

| Method | Path | Summary |
|---|---|---|
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/evaluate-expression` | Evaluate the expression and return the result. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/parameters` | Delete all parameters and parameter model links for the connection connectionId in the project projectId. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/parameters` | Gets all parameters defined for the specified project and connection. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}/parameters` | Updates parameters for the specified connection in the project with the values provided. Collection form — a JSON array; there is no `PUT .../parameters/{key}`. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/parameters` | Create a parameter. The response carries the evaluated value; a bad expression is **422** before anything is stored. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/parameters/{key}` | Delete one parameter by key (the plain `DELETE .../parameters` above wipes them all). |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/parameters/linkable-properties` | Every property in the connection a parameter can drive; each row carries its `owner`. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/operations/{operationId}/linkable-properties` | The same for one operation. A nonexistent id is **404**. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/members/{memberId}/linkable-properties` | The same for one member. A nonexistent id is **404**. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/parameters/links` | List parameter → property links. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/parameters/links` | Link a parameter to a property; applies the value at once. An unknown parameter / property / owner, a value the target cannot take, a property already driven and a value that does not settle are all **422** here, not 404. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/parameters/links/{linkId}` | Unlink; **204**. The last applied value stays in the model. |

Bodies, the worked flow and the links that answer 200 and change nothing: `parameters.md`.

## Template

| Method | Path | Summary |
|---|---|---|
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/apply-template` | Apply the connection template applyTemplateParam on the connection connectionId in the project projectId. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/get-default-mapping` | Get the default mappings for the application of the connection template passed in templateToApply |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/get-template` | Create a template for the connection connectionId in the project projectId. |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/templates` | Delete all templates in connection. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/templates` | Retrieves a list of templates associated with a specific connection within a project. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/templates/create-from-connection` | Create a reusable connection template from connectionId with structured metadata. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/templates/explode` | Explode all templates (delete parameters, keep operations). |
| DELETE | `/api/5/projects/{projectId}/connections/{connectionId}/templates/{templateId}` | Delete specific template. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/templates/{templateId}/common-properties` | Get common properties for specific template. |
| PUT | `/api/5/projects/{projectId}/connections/{connectionId}/templates/{templateId}/common-properties` | Set common properties for specific template. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/templates/{templateId}/explode` | Explode specific template (delete parameters, keep operations). |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/templates/{templateId}/load-defaults` | Load parameter defaults for specific template. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/templates/{templateInstanceId}` | Retrieves a specific template by its ID for a given connection within a project. |

## ConnectionLibrary

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/connection-library/get-design-sets` | Retrieves a list of design sets available for the user. |
| GET | `/api/5/connection-library/get-picture` | Retrieves the picture associated with the specified design item as a PNG image. |
| GET | `/api/5/connection-library/get-template` | Retrieves the template associated with the specified design set and design item. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/propose` | Proposes a list of design items for a specified connection within a project. |
| POST | `/api/5/projects/{projectId}/connections/{connectionId}/publish` | Publish template to Private or Company set. |

## Conversion

| Method | Path | Summary |
|---|---|---|
| POST | `/api/5/projects/{projectId}/change-code` | Changes the design code of the project. |
| GET | `/api/5/projects/{projectId}/get-default-mapping` | Gets default conversion mappings for converting the project to a different design code. |

## Export

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/export-dwg` | Exports the connection to DWG format (long-running; streams DWG bytes, may take up to ~10 min). Errors are ProblemDetails: 404 unknown connection, 502 when the Viewer fails to open or start the export, 504 on timeout. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/export-ifc` | Exports the connection to IFC format. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/export-iom` | Exports the connection to XML which includes the `OpenModelContainer` (NuGet package `IdeaStatiCa.OpenModel`). |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/export-iom-connection-data` | Gets the `ConnectionData` for the specified connection (NuGet package `IdeaStatiCa.OpenModel`). |

## Report

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/reports/htmlZip` | Generates a report for the specified connection in PDF, Word, or HTML zip format. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/reports/pdf` | Generates a report for the specified connection in PDF, Word, or HTML zip format. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/reports/word` | Generates a report for the specified connection in PDF, Word, or HTML zip format. |
| POST | `/api/5/projects/{projectId}/reports/pdf` | Generates a report for multiple connections in PDF or Word format. |
| POST | `/api/5/projects/{projectId}/reports/word` | Generates a report for multiple connections in PDF or Word format. |

**A report shows the connection's active load effects.** It reuses a calculation of exactly that
set (`calculate` or `calculate-async`) made after the last write that emptied this connection's
results — so a calculation followed by a report solves once, also after edits of other connections. Otherwise, a `loadEffectIds` subset run included, it calculates
the active set first and stores that run as the connection's results. Choose what a
report shows with the active flags (`raw-results.md` § Multiple load effects, *Isolating one LE*).

## Settings

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/settings` | Gets setting values for the project. |
| PUT | `/api/5/projects/{projectId}/settings` | Updates one or multiple setting values in the project. |

## Presentation

| Method | Path | Summary |
|---|---|---|
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/presentations` | Returns data for Scene3D visualization. |
| GET | `/api/5/projects/{projectId}/connections/{connectionId}/presentations/text` | Returns serialized data for Scene3D in JSON format. |
