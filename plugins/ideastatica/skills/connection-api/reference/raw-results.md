# Interpreting raw CBFEM results (`rawresults-text`)

`POST /api/5/projects/{projectId}/connections/rawresults-text` (body: `[connId, ...]`)
returns an **array of JSON strings** — one per requested connection. **Each element is
itself a JSON document** (a serialized results object), so you must parse twice:

```python
arr = resp.json()                 # list[str]
data = json.loads(arr[0])         # results for the first connection
```
(If a connection failed, its element is the literal string `"Results for connection {id} failed"`.)

**Single-connection form:** `POST .../connections/{connId}/rawresults-text` takes the
connection in the PATH (no body) and returns ONE JSON string — parse once, not twice. It also
accepts an optional **`?loadEffectIds=`** query to compute a SUBSET of the connection's load
effects; omit it for all of them. The same selector exists on
`POST .../connections/{connId}/calculate` (returns a single `ConResultSummary`) and on
`POST .../connections/{connId}/calculate-async`. The plural body-array endpoints have no such
selector.

**Answers:** the double parse · the unit convention (§"THE critical rule" — read it before you
use a single number; it is the most common mistake here) · why multiple load effects come back
as an ENVELOPE and not per-LE · the structure of the results object, section by section ·
a reading checklist at the end.

**Does NOT answer:** the pre-scaled numbers from `calculate` / `results` (MPa, percent) →
`io-shapes.md` §Calculation · what a failed check *means* or how to diagnose it →
`diagnostics.md` · load-effect authoring → `io-shapes.md` §LoadEffect.

## THE critical rule: raw results are in SI base units and 0..1 ratios

**Prefer this channel whenever you are computing rather than displaying** — one convention
covers the whole document, so a number cannot be misread (the contrast block below shows what
the simplified endpoints do instead).

Unlike the simplified `/results` and `/calculate` endpoints (which pre-scale values to
MPa / percentages for display), **raw results are unscaled**:

- **Stress / strength / modulus → Pascals.** Divide by 1e6 for MPa (so yield 355 MPa
  appears as `3.55e8`, E 210 GPa as `2.1e11`).
- **Lengths / thickness / leg size → metres.** Multiply by 1000 for mm.
- **Forces → Newtons.** Divide by 1000 for kN.
- **Strains, utilizations, limits → dimensionless ratios (0..1).** Multiply by 100 to get
  the percentages the GUI shows (e.g. the plate strain limit `0.05` = 5 %).
- **`'NaN'` strings** appear for fields that are not relevant to the active design code or the
  element — treat as not-applicable; `checkStatus` still gives pass/fail. A weld that is not
  rated by a stress utilisation — a **`cjp` weld**, or any `edgeToEdge` weld — has `maxUnityCheck`
  and `betaW` `"NaN"` with `checkStatus: true` (its `/results` row: `io-shapes.md` §
  CheckResWeld, `isFullStrength`). Guard every numeric
  field with a type check — a falsy default (`x or 0` in Python) keeps the string.
- Very large/small values are plain JSON numbers in scientific notation. `NaN`/`Infinity`
  come through as the **strings** `"NaN"` etc.

> **Contrast with the simplified endpoints** `/results` and `/calculate` (documented in
> `io-shapes.md`). There the same numbers are pre-scaled and the units are NOT uniform:
> weld/bolt/anchor `unityCheck` is already a **percent** (not a 0..1 ratio), plate
> `maxStress` is in **MPa**, plate `maxStrain` is on a **ratio×10000** scale
> (ε_Pl % = maxStrain / 100), and `checkResSummary.checkValue` means different things per
> `name` (percent for Analysis/Welds/Bolts/Anchors, ratio for Plates). Raw results avoid that
> inconsistency — everything is SI + ratios. Prefer raw results when you need numeric
> values you control the scaling of; prefer `unityCheckMessage` from the simplified
> endpoints when you just want a display string that matches the app.

## The two endpoints agree wherever numbers come back

The scaling relationships above hold in every regime that returns numbers, including a joint
far past its resistance whose analysis is reported as failed:

- plate `maxStress` in Pa / 1e6 = the `/results` MPa value — e.g. raw `3.5e8 Pa` ↔
  `/results` `350.0 MPa`;
- plate `maxStrain` × 10000 = the `/results` `maxStrain` — e.g. raw `0.0225` ↔ `225.0`;
- raw ratio checks (weld `unityCheckWeld`, anchor `maxUnityCheck`) × 100 = the `/results`
  percentages.

The conversions are exact (to floating-point rounding), so you can convert freely in both
directions.

**Read the outcome from `checkResSummary`'s `Analysis` rows, not from an applied-load
fraction.** `analysis[*].appliedLoadPercentage` stays at 1.0 however plastic the joint becomes
**as long as `StopAtLimitStrain` is off** (the default), so by itself it does not distinguish a
comfortable joint from a grossly overloaded one. Turn that setting on and it starts reporting how
far the load ramp actually got, which is the basis of the first-yield recipe in the `analysis`
section below — so always check the setting before reading this field either way. Beyond the
member-overload cutoff there is no result document at all: `rawresults-text` then returns the
plain text `Results for connection {id} failed: …` — check for that sentence before parsing.

## Multiple load effects: results are the ENVELOPE, not per-LE

- **Each result group returns exactly ONE entry per element** — the **critical
  (governing/envelope) result across all active load effects**, not one entry per LE.
  Adding more load effects does not change the number of entries in a group.
- **Which LE produced that extreme is on the entry**: every result carries `loadCaseId`
  (int) + `loadCase` (string). The `summary` rows likewise report the governing `loadCaseId`.

> ⚠️ **The envelope is PER ELEMENT, so one response mixes load cases — and it does not look
> like it does.** A multi-LE run returns the element count you expect (one row per bolt, per
> plate, …), which reads like "the results for those LEs". It is not: each row is that
> element's worst case, and the `loadCase` field can differ from row to row. Only the value
> that governed survives — an element's reading under a non-governing LE is simply absent from
> the row. `welds` compounds it, because its rows are per SEGMENT, so a single weld can mix
> load cases across its own segments. **`analysis` is the exception**: exactly one row per LE,
> which is why the merging is easy to miss everywhere else.
>
> **A load effect can vanish from a group entirely** — if it governs nothing there, it appears
> on no row, even though it was solved and `analysis` lists it. The share of checks the
> envelope swallows grows with the number of LEs, so on a model with many LEs most of them are
> invisible in the per-element groups.
>
> **The check:** group any element collection by `loadCase` and count the distinct values. More
> than one means you are holding a digest, not per-LE results; compare that set against the
> active LEs to see which ones vanished. To get a specific LE's numbers, isolate it —
> `?loadEffectIds=` on the calculating endpoint, or read `forcesAllLoadCases` (below).
- **Per-LE FORCES ARE available via `forcesAllLoadCases`** (on bolts, anchors and pins —
  **not on welds**; in a fatigue analysis it read `null` on every bolt and anchor row, the
  regular `bolts` / `boltsAnchor` rows too):
  a dict **keyed by load-effect id** → force array with layout `[n, qy, qz]` in N (axial,
  shear-y, shear-z; a pin's `n` is always 0). The keys are **JSON strings** (like every
  id-keyed object here), so index by `"2"`, not `2`; map the id to a name via
  `GET .../load-effects`. This is the only place per-LE detail survives — and it is complete:
  it holds every LE's force, including those the envelope discards, equal to an isolated run of
  that LE. **So you do NOT need one run per LE to get fastener forces.**
- **Welds have no per-LE forces.** Their `forcesAllItems` belongs to the row's governing LE
  only (`welds` table below); a weld reading for another LE needs a `?loadEffectIds=` run.
- **Timber bolts (`boltCheckResDataTimbers`) carry six values per load effect in
  `forcesAllLoadCases`**, for the bolt segment at the steel plate only. The first three are
  `[n, qy, qz]` in N as above (the shear resultant `hypot([1],[2])` equals `boltShearForce`); the
  meaning of the last three is not documented. Their per-plane forces, `angle` and
  `elementAxisY` / `elementAxisZ` belong to the governing load effect.
- **But `forcesAllLoadCases` carries FORCES ONLY, so the response is still an envelope.**
  From a non-governing LE's entry you can rebuild the axial force (`[0]`), the shear resultant
  (`hypot([1],[2])`) and — since resistances are LE-independent — the tension utilisation;
  these equal isolated runs exactly. You CANNOT rebuild `unityCheckShear`,
  `interactionTensionShear` or `maxUnityCheck`: those need code-dependent intermediate
  coefficients (`bearingCoeff`, `alpha_b_Shear_EN`, reduction factors) that the row exposes only
  for the governing LE. A per-LE *utilisation* matrix therefore needs one `?loadEffectIds=` run
  per LE.
- **Consequence:** raw results are an envelope, NOT a full LE × element matrix. Plate
  stresses/strains, weld checks, concrete-block and base-plate-shear checks are reported only
  for the governing LE. To evaluate a specific LE on its own, use one of the three ways below.
- **Compare plates across load effects by `maxStrain`, not `maxStress`.** Once a plate yields, its
  stress climbs only along the hardening slope (E/1000, a couple of MPa per percent of plastic
  strain), so the stress barely separates load effects that the strain tells clearly apart.
- To pick the worst element in a group, sort by `maxUnityCheck`. `calculate-load-extremes`
  can pre-reduce the active set to only the critical load effects.

> **Isolating one LE — three ways, in order of preference.**
> 1. **`?loadEffectIds=`** on `calculate` / `calculate-async` — solves only the listed LEs and
>    leaves the stored model untouched. It overrides `active`: an LE that is active but not
>    listed stays uncalculated. It applies per request and leaves no state behind
>    (calculations on one project still queue — `endpoints.md` § Calculation).
>    **A report does not keep the subset**: it shows the active load effects and stores that run
>    (`endpoints.md` § Report), so `results` read after a report reflects all of them again. For a report of a subset, use the active flags (way 2).
> 2. **`active:false`** — both `POST` and `PUT .../load-effects` honour it; the flag reads back
>    on both GETs, `calculate` skips that LE, and the flag survives a `download` → re-`open`
>    round-trip. Mutates the stored model, so restore the flags
>    afterwards. Note there is **no `PUT .../load-effects/{id}`** (405) — the collection form
>    `PUT .../load-effects` takes the whole LE object and its `id` field selects the target.
>    **Send ONE object, not an array**: despite the collection-shaped path, an array body is
>    a 400 deserialization error. To toggle several, PUT them one at a time.
> 3. **`DELETE`** the others — destructive, needs a throwaway copy. Only when you also want the
>    LEs gone.
>
> `POST .../load-effects/calculate-load-extremes` also rewrites `active`, but it decides for
> itself which LEs survive — it is not directable at a specific one.

**The envelope behaves the same for `stress_Strain`, `stiffness`, `capacity_Design`,
`total_Design`, `fireRestance` and `horizontalTying`**: deleting a non-governing LE changes
nothing, and deleting a governing LE lets only the elements it governed fall through to the
next-worst.
**`fatigues` is the one exception**: it is not an envelope. Each result is one load effect
against the reference; see the fatigue section below for how to choose which one.

### Reading `loadCaseId` correctly
- On **detail entries** (plate/bolt/anchor/weld/concreteBlock/basePlateShear),
  `loadCaseId` identifies the governing LE **per element** — different elements in the same
  group can report different governing LEs. There is no single governing LE for the whole
  connection; read it per element.
- To get an LE's name, take `loadCaseId` and map it via `GET .../load-effects` (the
  `loadCase` name string on `summary` rows is not always populated — prefer the id).
- `loadCaseId = 0` on summary rows means **"not tied to a specific LE"**, not id 0.

## Structure of the results object
A set of dictionaries **keyed by element ids** (string keys in JSON; not necessarily
1-based, may have gaps). Empty groups are present but `{}`. Typical groups: `codeType`,
`plates`, `platesInfo`, `platesDeformation`, `welds`, `weldsInfo`, `bolts`, `boltsInfo`,
`boltsAnchor`, `concreteBlocks`, `basePlateShear`, `summary`, `analysis`, `projectItem`,
`costEstimationResults`. Other groups (`pins`, `bucklings`, `stiffnesess*`, …) populate when the
connection has those components. **`fatigueChecks`/`fatigueSectionsChecks`/`fatigueBoltChecks`/
`fatigueAnchorChecks`/`fatigueWelds`** populate for an `analysisType:"fatigues"` connection — see
the dedicated "Fatigue result groups" section below for their fields and the reference-LE rule.

All result entries share a common tail: `id` (int), `name` (string), `checkStatus` (bool),
`loadCaseId` (int), `loadCase` (string), `maxUnityCheck` (double).

### `summary` (one row per check category)
| Field | Meaning |
|---|---|
| `checkContext` | which check this row is: `analysis`, `plate`, `plateDeformation`, `weld`, `buckling`, … |
| `checkValue` | **ratio**; `-1.0` = not calculated. For `analysis` it is the applied-load level (1.0 = 100 %) |
| `limit` | the ratio limit it is compared against |
| `checkStatus` | bool, passed |

### `plates`
| Field | Unit / meaning |
|---|---|
| `maxStress` | von Mises stress, **Pa** |
| `maxStrain` | plastic strain, **ratio** (×100 = ε_Pl %) |
| `limitPlasticStrain` | strain limit, ratio (typically 0.05 = 5 %) |
| `thickness` | **m** |
| `materialName` | string |
| `materialFy` | yield strength, **Pa** |
| `materialFuWithoutReduction` | ultimate strength, **Pa** |
| `materialModulusOfElasticity` | E, **Pa** |
| `items` | FE element ids of this plate (int list) |

### `platesDeformation`
| Field | Unit |
|---|---|
| `maxDeformation` | **m** |
| `maxDeformationRatio` | ratio (×100 = %) |
| `limitDeformation` | ratio limit (typically 0.03 = 3 %) |
| `thickness` | **m** |

### `welds`
| Field | Unit / meaning |
|---|---|
| `name` | weld name (matches the app) |
| `unityCheckWeld` / `unityCheckStress` | **ratio** (×100 = %); = `maxUnityCheck` |
| `thickness` / `designedThickness` | throat, **m** |
| `legSize` | **m** |
| `maxEquivalentStress` | equivalent stress, **Pa** |
| `equivalentStressResistance` | **Pa** |
| `sigmaPerpendicular` | **Pa** |
| `tauy` / `taux` | shear stress components, **Pa** |
| `plasticStrain` | ratio |
| `weldType2` | string (e.g. `doubleFillet`) |
| `length` | **m** |
| `forcesAllItems` | the row's **governing LE only** (`loadCaseId`), not per-LE: keyed by the weld row's own key in `welds` (e.g. `"10016"`, not the weld item id), then by FE node id (**JSON string keys**) → a 10-number array per node of the weld's stress results in **Pa** (σ⊥, τ, equivalent stress, …) in an undocumented order — not forces, despite the name. May be `{}`. There is **no `forcesAllLoadCases`** on welds |

### `bolts`
Forces and resistances in **N**, unity checks as **ratios**.

| Field | Unit / meaning |
|---|---|
| `name` | bolt name (matches the app) |
| `boltAssemblyName` | assembly (string) |
| `boltTensionForce` / `boltShearForce` | acting forces, **N** |
| `boltTensionResistance` / `boltShearResistance` / `boltBearingResistance` | resistances, **N** |
| `unityCheckTension` / `unityCheckShear` / `unityCheckBearing` | ratios |
| `interactionTensionShear` | combined check, ratio (= `maxUnityCheck`) |
| `numberOfShearPlanes` | int |
| `boltShearType` | string (e.g. `bearing`) |
| `connectorDiameter` / `boreHoleDiameter` | **m** |
| `connectorTensileArea` / `connectorGrossArea` | **m²** |
| `forcesAllLoadCases` | dict keyed by load-effect id (**JSON string keys**) — per-LE forces `[n, qy, qz]` in **N** |

### `boltsAnchor` (also `boltsAnchorCompression`)
Anchors carry the same steel-side fields as bolts, plus anchorage-specific resistances and
a governing combined check. Forces/resistances in **N**, lengths in **m**, checks as ratios.

| Field | Unit / meaning |
|---|---|
| `name` | anchor name |
| `anchor` | bool |
| `boltTensionForce` / `boltTensionResistance` | steel tension, **N** |
| `unityCheckTension` / `unityCheckTensionMax` | steel / governing tension check, ratio |
| `interactionTensionShear` | combined (= `maxUnityCheck`) |
| `heff` | effective embedment depth, **m** |
| `anchorType` | string |
| `forcesAllLoadCases` | dict keyed by load-effect id (**JSON string keys**) — per-LE forces `[n, qy, qz]` in **N** |

> The anchor object also exposes numerous design-code-specific resistance and coefficient
> fields. They follow the same unit conventions (resistances in N, stresses in Pa, factors
> dimensionless) and carry `'NaN'` when not applicable to the active code. Read them by name
> from the live response if you need a specific one.

### `concreteBlocks`
| Field | Unit / meaning |
|---|---|
| `name` | block name |
| `fjd` | design bearing strength, **Pa** |
| `averageStress` | average contact stress, **Pa** |
| `nsd` | acting compressive force, **N** |
| `aeff` | effective bearing area, **m²** |
| `unityCheckStress` | ratio (= `maxUnityCheck`) |
| `fck` | concrete char. strength, **Pa** |

### `basePlateShear`
| Field | Unit / meaning |
|---|---|
| `name` | string |
| `shearForceTransferMethod` | how shear is carried (`friction`/`shearIron`/…) |
| `vx` / `vy` / `v` | acting shear, **N** |
| `vrdx` / `vrdy` | shear resistances, **N** |
| `frictionCoefficient` | factor |
| `unityCheck` | ratio (= `maxUnityCheck`) |

> Note: base-plate shear (and the detailed concrete-block fields above) are available only
> from this raw endpoint — `ConnectionCheckRes` from `/results` has no base-plate-shear field.

### `analysis`
| Field | Meaning |
|---|---|
| `appliedLoadPercentage` | fraction of load applied (1.0 = 100 %). Reads 1.0 in any run that returns results **while `StopAtLimitStrain` is off** — judge the outcome from the `Analysis` summary rows instead. With the stop ON it becomes meaningful: see "Finding first yield" below |
| `maxPlateEps` / `maxWeldEps` | **do not use — not populated.** Nominally the max plate/weld strain across the model, as a ratio; it reads `0.0` even when the plates are plastic. **Read plastic strain from `plates[].maxStrain` per plate** (and `welds[].plasticStrain`); an "is anything plastic?" check built on `maxPlateEps` passes vacuously |
| `singularityDetected` | bool |

### Finding first yield without a search (`StopAtLimitStrain`)

To learn how much load a joint takes before it goes plastic, let the solver walk to it instead
of bisecting amplitudes:

1. `PUT .../settings` — `calculationCommon/Checks/Shared/LimitPlasticStrain` to ~`1e-4`
   (and `…/LimitPlasticStrainForHighStrengthSteel` alongside it),
   `calculationCommon/Analysis/AnalysisGeneral/Shared/StopAtLimitStrain` **and**
   `…/Member_StopAtLimitStrain` to `true`. Raise
   `…/Member_NumberOfLoadSteps` (default **10**, i.e. 10 % granularity) for a finer read.
2. Apply a load deliberately far too large and solve.
3. `analysis[*].appliedLoadPercentage` is now the fraction the ramp reached; **first-yield
   magnitude = applied magnitude × that fraction**. One solve per component, no search.

An elastic state returns `1.0` (the solver does not intervene); an overloaded one returns the
fraction reached. Restore the real `LimitPlasticStrain` and turn the stops off afterwards — the
lowered limit is not the model's.

Two cautions. The scaled-down magnitude is derived from a run that had *already yielded*, where
the secant is softer than the true elastic slope, so it errs high — confirm the working
amplitude with a normal run and check `plates[].maxStrain` is 0. And a magnitude found for one
member or angle does not transfer to another, even with the same section.

**The number of `analysis` entries depends on `analysisType`:**
- `stress_Strain`, `stiffness`, `total_Design`, `fireRestance`: **one entry per active load
  effect**, keyed by each LE's `loadCaseId`. This is the full per-LE
  `appliedLoadPercentage` breakdown.
- `capacity_Design`, `horizontalTying`: these analysis types use their own dedicated load
  effects and **ignore the regular ones** — `analysis` has one entry per active *dedicated* LE,
  and the envelope over them behaves the same as the four types above.
  **The dedicated LEs are not created for you.** Switching `analysisType` on a connection that
  has only ordinary load effects adds nothing (the LE list is unchanged) and the calculation
  comes back `passed: false` with the *"There are no loads on members"* Analysis row — the same
  answer as a connection with no loads at all. The desktop adds the dedicated load effect when
  the analysis type is switched there; the API has no field that marks a load effect as one.
  Open a project whose connection was switched in the desktop; otherwise the calculation has
  nothing to solve. See `schemas.md` § ConAnalysisTypeEnum.
- `fatigues`: **2** entries, the reference (`name:"Reference"`) and the one load effect it is
  compared with (`name` = that load effect's name); see the fatigue section below.

### `totalCapacity` — the joint's load factor (how far the load can be scaled)

Populated when the connection's `analysisType` is **`total_Design`** (the desktop's
**"Joint design resistance"**). Same shape as `analysis` — an object keyed by load-effect id — but here
**`appliedLoadPercentage` is the MULTIPLIER by which the load effect can be scaled before
the joint reaches its resistance**, not a 0..1 convergence fraction:

```
POST .../connections/{connId}/rawresults-text
→ totalCapacity["1"].appliedLoadPercentage = F      # this LE can be scaled F times
```

**One entry per active load effect**, keyed by `loadCaseId` — same keying as `analysis`.
Each factor is relative to ITS OWN load effect, so a heavier LE gets a smaller factor and
`LE.load x factor` lands on the same absolute resistance for every entry (e.g. LEs at
1.0x / 2.0x / 0.5x of a base load give factors F / F/2 / 2F — all three products equal F times
the base). The desktop report shows this as **"Load factor"**
and takes the **MINIMUM** across the entries, i.e. the governing load effect — do the same.

**The factor covers four checks only**: plastic strain in plates, bolts (tension, shear,
interaction), anchors (steel tension and shear) and welds. Other components are not checked in
this analysis, so run `stress_Strain` for the full code check. A factor below 1.0 means the ramp
stopped before the design load; the results of that load effect are its last converged step.

**It is not in the summary.** `POST .../calculate` returns `ConResultSummary`, whose schema
is closed (`id`, `passed`, `resultSummary[]`) and carries no multiplier; the detailed
`POST .../connections/results` has none either. `rawresults-text` is the only channel.

Useful because the factor cannot be extrapolated from a `stress_Strain` run: a utilisation
u does NOT imply a 1/u reserve — plastic redistribution makes the real factor different. One `total_Design` calculate answers
it directly, which is the cheap way to size a load ramp instead of guessing and paying for
non-converging runs.

The sibling field `criticalLoadCoeff` reads `0.0` on every entry — do not use it.
`maxPlateEps` / `maxWeldEps` on these entries repeat the same value across all keys and, as in
`analysis` (table above), are not a usable strain reading — take strain from
`plates[].maxStrain`.

### Fatigue result groups (`fatigueChecks`, `fatigueSectionsChecks`, `fatigueBoltChecks`, `fatigueAnchorChecks`, `fatigueWelds`)

**Concept: a stress range between the reference load effect and ONE other load effect, never an
envelope across load effects.** The desktop works the same way: after one calculation the engineer
switches between load effects and reads each one against the reference. The values are nominal
stress ranges, the input to a code fatigue assessment (S-N curve, detail category); there is no
resistance, damage ratio or number of cycles. So every fatigue entry carries `checkStatus:false`,
`limitCheckStatus:true` and `maxUnityCheck:0.0`, also on a connection whose `calculate` reports
`passed:true`. Read the stresses, not the flags.

**Which pair a call returns:**
- **The reference is the first calculated load effect in the connection's load-effect list.** On
  a list built over REST that is the lowest id, because `POST .../load-effects` appends with the
  highest id in use + 1 (`io-shapes.md` § LoadEffect). It is not a flag: `analysis` names it
  `"Reference"`, and deleting it passes the role to the next one.
- **A call without a selection returns the reference against the LAST calculated load effect**
  (the highest id). The load effects in between are not part of that result.
- **To read load effect x, calculate the pair**:
  `POST .../connections/{connId}/rawresults-text?loadEffectIds=<reference>&loadEffectIds=<x>`, or
  `calculate` with the same query followed by `results`. The order of the ids does not matter, the
  active flags stay untouched, and the values equal the desktop's for x. One run per load effect.
- **A fatigue calculation needs at least two load effects.** With one alone (through the subset or
  the active flags) the call still answers 200 but carries *"More than one load effects should be
  defined"* in place of results: `calculate` as a `passed:false` Analysis row, `rawresults-text`
  as a message string instead of the JSON object.
- Deactivating every load effect above x (`active:false`, `PUT .../load-effects`) gives the same
  pair but changes the stored model; prefer the subset for results. **For a report of load effect
  x, use the active flags**: a report shows the active load effects and does not reuse a subset run.

**The ranges hold only while the plates stay elastic under the fatigue actions** (high-cycle
fatigue, no yielding). Confirm `plates[].maxStrain` is 0 for every load effect you read.

**To compare against other reference forces**, PUT them into the reference load effect's
`memberLoadings` (`PUT .../load-effects`) and recalculate; the role stays with that load effect.
Back up its content first if you need it again. To make a new load effect the reference,
`DELETE .../load-effects` (all of them) and POST it first.

**Groups and the desktop tables** (Check tab, Fatigue):

| group | desktop table | fields |
|---|---|---|
| `fatigueChecks` | Weld sections: a plate section placed next to each weld, 1.5 x the leg size from the weld toe; per weld the more stressed section | `normalStress` = σ_max with `shearStress` = the τ at the same point; `shearStress2` = τ_max with `normalStress2` = the σ at the same point |
| `fatigueSectionsChecks` | Fatigue sections: user-defined sections, made with a `work-plane` operation | the same four fields |
| `fatigueWelds` | Welds | `maxEquivalentStress` = σ_wf,max with `taux` = the τ_wf at the same point; `tauxwf` = τ_wf,max with `sigmawf` = the σ_wf at the same point |
| `fatigueBoltChecks` / `fatigueAnchorChecks` | Bolts / Anchors | `normalStress` = Δσ (tension force / tensile stress area), `shearStress` = Δτ (shear force of the most loaded shear plane / shear area) |

Which groups populate depends on the components present: e.g. a base plate with anchors fills
`fatigueChecks` (weld/plate stress ranges) and `fatigueAnchorChecks`, and leaves the groups for
components it does not have `{}`.

`fatigueChecks` (per weld/plate joint, keyed by opaque per-joint ids that need not be contiguous or 1-based):
| Field | Unit / meaning |
|---|---|
| `plateName` / `joinedItemName` | names of the plate and the joined item the weld line belongs to |
| `weldType2` | string (e.g. `bevel`) |
| `designedThickness` | **m** |
| `legSize` | **m** |
| `length` | weld line length, **m** |
| `normalStress` / `shearStress` | the largest \|σ\| along the section and the τ at the same point, **Pa** |
| `shearStress2` / `normalStress2` | the largest \|τ\| along the section and the σ at the same point, **Pa** |
| `stressDiagram` / `stressDiagramTau` | `[[position_m, stress_Pa], ...]` polylines of the normal / shear stress range along the section (position in **m** from 0 to `length`), already relative to the reference |
| `plateUID` | list of int, internal plate ids this check touches |
| `originId` | double, internal reference id |
| `sectionLine` | list of `["x,y,z", "x,y,z"]` global-coordinate string pairs — the two endpoints of the weld line, **m** |

`fatigueAnchorChecks` (per anchor, one entry per anchor):
| Field | Unit / meaning |
|---|---|
| `boltAssemblyName` | assembly name (e.g. `"M16 8.8"`) |
| `slottedHole` | bool |
| `normalStress` / `shearStress` | **Pa** |
| `forcesAllLoadCases` | dict keyed by load-effect id (JSON string keys) when populated — same shape as the non-fatigue bolt/anchor groups; may be `null` |
| `plateName` | string or `null` |
| `length` | **m** |

Both groups share the common result-entry tail (`id`, `name`, `checkStatus`, `loadCaseId`,
`loadCase`, `maxUnityCheck`, `form`) like every other raw-results group — but per the concept note
above, `checkStatus`/`maxUnityCheck` are not meaningful here; read `loadCaseId`/`loadCase` to know
which LE (relative to the fixed reference) each stress value belongs to.

### `costEstimationResults`
Fields: `steelCosts`, `filletWeldCosts`, `pjpWeldCosts`, `buttWeldCosts`, `boltCosts`,
`holeDrillingCost`, `totalEstimatedCost`, `logMessage`. (The production-cost endpoint
surfaces only `totalEstimatedCost`.)

## Joining results back to the geometry — colouring a model by utilisation

`GET .../presentations` gives every drawing group a `selected: {id, type:{kind}}`, so a check
result can be attached to the solid it belongs to. **No IFC parsing is needed for this** — that
is only for getting breps into a CAD tool.

> **Join through `/results`, not through raw — they are different id spaces.** The scene, IOM
> and `checkResWeld[].id` share one, which is what makes the table below work; the raw document
> has its own. Raw entries carry a `name`, so name is the only bridge from raw back to
> geometry — and plate names are unique while weld names are not (a `doubleFillet`'s second leg
> comes back with `name: ""`). Practical route: colour from `/results` by id, and reach into
> raw only for the extra fields, matching on name. Details: §"Use the summary results for this
> join" below.

| scene `kind` | how it joins to a result | quality |
|---|---|---|
| `weld` | scene `id` **==** `checkResWeld[].id` | exact on identity, but **`id` is not unique**: a `doubleFillet` yields TWO rows per weld, one per leg (same id, one named and one with `name: ""`, slightly different `unityCheck`). **Take the max per id**, or you colour by whichever row you hit first. Two things not to read as a bug: **the join is expected to be partial** — a `contact` rides in the same collection and gets no weld check, so scene groups without a result are normal and their count should match your contacts — and there is a **catch-all `id: 0`** carrying several rows whose `unityCheck` is `"NaN"`. Colour what matches; leave the rest at the neutral colour rather than forcing a join |
| `plate` | scene `id` → IOM `plates[].name` → `checkResPlate[].name` | works, but needs IOM as the bridge: **the plate results carry no id, only a name** |
| `member` | its own plates are named `B{id}-tfl 1`, `B{id}-w 1`, … | by name prefix; there is no member-level check |
| `boltGrid` | `checkResBolt` / `checkResAnchor` | **coarse** — one scene group covers the whole grid while the results list every bolt (`B1`…) or anchor (`A1`…) separately; take the max |
| *the concrete block* | **`selected` is absent** | not joinable. The block is the group with `selected: null` (translucent grey, alpha 45). Mapping it to `checkResConcreteBlock` works only while it is the ONLY unidentified group — an assumption, not a rule |

**Plates report strain, not a utilisation** — and the scale differs per endpoint, which is the
trap:

| endpoint | `maxStrain` | percentage of the limit |
|---|---|---|
| `POST .../connections/results` | ratio × 10000 (ε_Pl % = `maxStrain`/100) | `maxStrain / 10000 / limit * 100` |
| `POST .../rawresults-text` | plain ratio | `maxStrain / limit * 100` |

a plate reading `4.677` from `/results` is ε_Pl = 0.047 %, which the
summary prints as `0.0 < 5.0%`. Treating that as a ratio against the 0.05 limit yields 9355 %
and paints a sound member red. `limit` is `calculationCommon/Checks/Shared/LimitPlasticStrain`
from `GET /projects/{id}/settings` — a fraction (0.05 = 5 %), and a project setting, so read it
rather than assuming 5 %.

Welds, bolts, anchors and the concrete block all carry a real `unityCheck` in percent, except a
weld with `isFullStrength: true` (`"NaN"`).

The vertex buffers are **flat float arrays** (`[x,y,z, x,y,z, …]`), not objects, and `faces`
indexes them as triangles — a group's mesh is `faces[i], faces[i+1], faces[i+2]` stepping by 3.
Colour per group, not per vertex: the resolution of this join is **one value per element**,
never a stress field across a surface.

**Use the summary results (`POST .../results`) for this join, not `rawresults-text`.** The
detailed results are keyed by their own ids, which do NOT match the scene:

| detailed collection | joinable to the scene? |
|---|---|
| `plates` | **only by `name`** — entries whose name exists in IOM `plates[]` (`EP1`, `STIFF1a`, …) map to a scene group; the rest are the members' own flanges and webs, which the scene draws inside the `member` group |
| `welds` | **no** — its keys are a separate numbering entirely, and there are more rows than scene weld groups (rows are per segment, and a double fillet contributes two). `joinedItemName` names the part the weld attaches TO, not the weld |
| `bolts` | per bolt, while the scene has one group for the whole grid |

Do not infer the id spaces from their ranges: they are opaque solver ids that need not start at
1 and may have gaps, and a range that looks distinctive on one model is not a test you can
apply to another. **Intersect the two key sets on your own model** — where they do not overlap,
`name` is the only bridge.

Detailed results are the place for *values* (stress, resistances, thicknesses); the summary
results are the place for *identity*.

## Practical reading checklist
1. Parse twice (array element → `json.loads`).
2. Skip empty groups (`{}`) and summary rows whose `checkValue == -1.0`.
3. Convert for display: stress `/ 1e6` → MPa, length `* 1000` → mm, force `/ 1000` → kN,
   ratio `* 100` → %.
4. Compare each check to its `limit` (also a ratio) or use `checkStatus`.
5. Treat `'NaN'` strings as not-applicable fields.
