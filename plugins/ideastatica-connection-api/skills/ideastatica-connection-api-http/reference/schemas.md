# Connection REST API — key schemas & enums

Field names below match the JSON wire format (camelCase) as emitted by the service.
Verify against `http://localhost:5000/swagger/5.0/swagger.json` → `components.schemas`
for the authoritative, full set — only the most-used types are summarized here.
The typed-operation DTOs (`ConWeldOperation`, `ConCutOperation`, the grid operations,
`ConPlatePositioning`, `ConGridGeometry`, and their enums) live in `operations.md`.

## Project

### ConProjectData  (body of `POST /api/5/projects`, `PUT /api/5/projects/{projectId}`)
| Field | Type | Notes |
|---|---|---|
| `name` | string | |
| `description` | string | |
| `projectNumber` | string | |
| `author` | string | |
| `countryCode` | `CountryCode` enum | design code / country |
| `date` | string (date-time) | |
| `steelEdition` | `ConSteelCodeEditionEnum` | code edition — `io-shapes.md` § `ConProjectData` |

### ConProject  (response of open/create)
| Field | Type | Notes |
|---|---|---|
| `projectId` | string (uuid) | use in all `/projects/{projectId}/...` paths |
| `projectInfo` | `ConProjectData` | |
| `connections` | `ConConnection[]` | |

## Connection

### ConConnection
| Field | Type | Notes |
|---|---|---|
| `id` | int | use as `connectionId` and in calculate/results arrays |
| `identifier` | string | |
| `name` | string | |
| `description` | string | |
| `analysisType` | `ConAnalysisTypeEnum` | |
| `steelEdition` | `ConSteelCodeEditionEnum` | per-connection code edition — `io-shapes.md` § `ConProjectData` |
| `includeBuckling` | bool | The ONLY way to turn buckling on (`analysisType: "buckling"` is refused — see below). With it set, the summary's Buckling row flips from `skipped: true` / `checkValue: -100.0` / *"Not calculated"* to a real value, and `/results` returns `bucklingResults` entries, one per computed shape. Those two together are how you confirm it ran. |

## Calculation

### calculate / results request body
JSON array of connection ids — `[1]`, `[1, 2, 3]`. Plain `integer[]`, not an object.

### ConResultSummary  (response of `.../connections/calculate`)
| Field | Type | Notes |
|---|---|---|
| `id` | int | connection id |
| `passed` | bool | overall pass/fail |
| `resultSummary` | `CheckResSummary[]` | per-check summary |

### CheckResSummary
| Field | Type | Notes |
|---|---|---|
| `checkValue` | double | check value — **NOT a uniform unit** (percent for Analysis/Welds/Bolts/Anchors, a small ratio for Plates). Don't assume 0..1; for display prefer `unityCheckMessage`. **`-100.0` is a sentinel for "not calculated/skipped"** (e.g. the Buckling row when `includeBuckling` is false, and the GMNA row) — check `skipped` rather than treating `-100.0` as a real percentage. See `io-shapes.md` / `raw-results.md`. |
| `checkStatus` | bool | this check passed? |
| `loadCaseId` | int | |
| `name` | string | check name (e.g. plates, bolts, welds) |
| `unityCheckMessage` | string | preformatted detail message — the safe thing to display |
| `skipped` | bool | if true, check not calculated — ignore `checkValue` |

Detailed results: `POST .../connections/results` returns `ConnectionCheckRes[]`
(richer CBFEM data). Raw results: `POST .../connections/rawresults-text` returns a JSON
string representing `CheckResultsData`.

## Load effects

### ConLoadEffect  (`GET/POST/PUT .../connections/{connId}/load-effects`)
| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `name` | string | |
| `active` | bool | included in calculation |
| `isPercentage` | bool | send `false` (`io-shapes.md` § LoadEffect) |
| `memberLoadings` | `ConLoadEffectMemberLoad[]` | per-member internal forces |

Each member loading references a member and carries a section load with components
`n`, `vy`, `vz`, `mx`, `my`, `mz` (axial force, shears, torsion, bending moments) and a
position (member begin/end). Inspect the live schema for exact nested field names
(`ConLoadEffectMemberLoad`, `ConLoadEffectSectionLoad`, position enum) before relying on them.

### ConLoadSettings  (`.../load-effects/get|set-load-settings`)
| Field | Type | Notes |
|---|---|---|
| `loadsInEquilibrium` | bool | |
| `loadsInPercentage` | bool | send `false` (`io-shapes.md` § LoadEffect) |

Send both flags on every `set-load-settings` call (`io-shapes.md` § DTO: ConLoadSettings).

## Errors — ProblemDetails (RFC 7807)
Error bodies follow the ProblemDetails shape below. **Parse by status code, not by media type**:
404, 409, 422 and 500 come as `application/problem+json`; 400 and 401 as `application/json`
(400 with an `errors` map from model binding). 415 usually has no body (`projects/open`, the
load-effects POST, calculate, `import-iom-file`); `POST /api/5/projects` answers 415 with a
ProblemDetails body.
| Field | Type |
|---|---|
| `status` | int (HTTP status) |
| `title` | string |
| `detail` | string |

| Status | Meaning |
|---|---|
| 401 | `ClientId` header missing, misspelled, not a GUID, or an unknown id (SKILL.md rule 1) |
| 400 | Model binding: a malformed body or a missing required property — the `errors` map names it |
| 404 | Project / connection not found (or project not open in this client session) |
| 409 | An operation id of another kind; a `calculate-async` while a job runs (`endpoints.md` § Calculation) |
| 422 | Validation failed |
| 500 | Internal server error |
| 502 / 504 | Downstream service error / timeout |

## Enums

### CountryCode (design code)
`none`, `ecen` (Eurocode), `india`, `sia`, `american`, `canada`, `australia`, `rus`,
`chn`, `hkg`

> Wire format: these are emitted as the lowercase strings above. Confirm casing against
> the live spec for your version — serialization settings can change it.

### ConAnalysisTypeEnum
`stress_Strain`, `stiffness`, `capacity_Design`, `fatigues`, `total_Design`,
`horizontalTying`, `capacityLoadLevels`, `fireRestance`, `buckling`

Set per connection: `PUT .../connections/{connectionId}` with the full body from a GET and
`analysisType` changed (`io-shapes.md` § PUT
/api/5/projects/{projectId}/connections/{connectionId} says what an omitted field does). **The wire names do NOT match the desktop
labels** — pick by this table, not by which name sounds right:

| Desktop "Analysis type" | abbreviation | REST value | desktop offers it |
|---|---|---|---|
| Stress, strain | EPS | `stress_Strain` | always |
| Stiffness | ST | `stiffness` | advanced-analysis licence |
| Capacity design | CD | `capacity_Design` | advanced-analysis licence, not for `hkg` |
| **Joint design resistance** | DR | **`total_Design`** | advanced-analysis licence |
| Fatigue | FAT | `fatigues` | advanced-analysis licence |
| Fire resistance | FIR | `fireRestance` (note the missing "s") | advanced-analysis licence |
| Horizontal tying | HT | `horizontalTying` | advanced-analysis licence, `ecen` only |
| *(not offered)* | | `capacityLoadLevels` | never |

`buckling` is rejected on write. Enable buckling through the connection's `includeBuckling`
flag instead, together with `stress_Strain`, `capacity_Design` or `fireRestance`
(`io-shapes.md` § PUT /api/5/projects/{projectId}/connections/{connectionId}).

Two traps:
- **`capacityLoadLevels` is NOT "Joint design resistance"** despite how it reads. It is a
  separate mode that the desktop UI does not even offer.
- **`capacity_Design` and `horizontalTying` calculate a load effect of their own**, which the
  desktop adds when the analysis type is switched there (`LE-MC1`, `LE-HT`). Switching over REST
  adds none, and the API has no field that marks a load effect as one: the run returns 200 with
  `passed: false` and *"There are no loads on members"*. Switch such a connection in the
  desktop, then open the saved project over REST. `GET .../load-effects` lists the dedicated load
  effects next to the ordinary ones, with nothing that marks them, and a `loadEffectIds` subset
  of ordinary load effects does not apply: the run solves the dedicated ones.

To read the joint's load factor, use `total_Design` and read `totalCapacity` from
`rawresults-text` — see `reference/raw-results.md`.
