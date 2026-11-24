// Read and INTERPRET raw CBFEM results — IDEA StatiCa Connection Rest API 5.0 (C#).
// Mirror of examples/raw_results.py.
//
// POST .../connections/rawresults-text returns an array of JSON *strings*; each string is
// itself a serialized CheckResultsData (double-encoded). Unlike /results and /calculate,
// raw results are UNSCALED — SI base units (Pa, metres) and dimensionless ratios (0..1).
// This converts to GUI units (stress->MPa, length->mm, ratio->%). See reference/raw-results.md.
//
// Run (e.g. with the .NET 10 SDK):
//   dotnet new console -o csdemo && cd csdemo   # replace Program.cs with this file
//   dotnet run -- path/to/model.ideaCon
//   Service default: http://localhost:5000

using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;

const string Base = "http://localhost:5000/api/5";

if (args.Length < 1) { Console.WriteLine("Usage: dotnet run -- path/to/model.ideaCon"); return; }
var ideaConPath = args[0];

using var http = new HttpClient();

var clientId = (await http.GetStringAsync($"{Base}/clients/connect-client")).Trim().Trim('"');
http.DefaultRequestHeaders.Add("ClientId", clientId);
Console.WriteLine($"Connected. ClientId = {clientId}");

using var form = new MultipartFormDataContent();
var fileContent = new ByteArrayContent(await File.ReadAllBytesAsync(ideaConPath));
fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
form.Add(fileContent, "ideaConFile", Path.GetFileName(ideaConPath));
var openResp = await http.PostAsync($"{Base}/projects/open", form);
openResp.EnsureSuccessStatusCode();
var projectId = (await openResp.Content.ReadFromJsonAsync<JsonObject>())!["projectId"]!.GetValue<string>();
Console.WriteLine($"Opened project {projectId}");

try
{
    var connections = await http.GetFromJsonAsync<JsonArray>($"{Base}/projects/{projectId}/connections");
    var ids = connections!.Select(c => c!["id"]!.GetValue<int>()).ToList();
    if (ids.Count == 0) { Console.WriteLine("No connections."); return; }

    // rawresults-text calculates the connections itself; no calculate call first.

    var rawResp = await http.PostAsJsonAsync($"{Base}/projects/{projectId}/connections/rawresults-text", ids);
    rawResp.EnsureSuccessStatusCode();
    // array<string>; each element is itself a JSON document — the SECOND parse.
    var elems = await rawResp.Content.ReadFromJsonAsync<List<string>>();

    for (int i = 0; i < ids.Count; i++)
    {
        Console.WriteLine($"Connection {ids[i]}:");
        var elem = elems![i];
        if (elem.StartsWith("Results for connection")) { Console.WriteLine($"  {elem}"); continue; }
        ReportRaw(JsonNode.Parse(elem)!.AsObject());  // second parse
    }
}
finally
{
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("Project closed.");
}

// Raw results emit 'NaN'/'Infinity' as STRINGS for N/A code-specific fields.
static double? Num(JsonNode? n) => n is JsonValue v && v.TryGetValue<double>(out var d) ? d : null;
static bool Ok(JsonObject o) => o["checkStatus"] is JsonValue v && v.TryGetValue<bool>(out var b) && b;
static IEnumerable<JsonObject> Vals(JsonNode? group) =>
    group is JsonObject o ? o.Select(kv => kv.Value).OfType<JsonObject>() : Enumerable.Empty<JsonObject>();

void ReportRaw(JsonObject data)
{
    // --- summary: ratio checkValue per checkContext (-1.0 = not calculated) ---
    Console.WriteLine("  Summary:");
    foreach (var row in Vals(data["summary"]))
    {
        var cv = Num(row["checkValue"]);
        if (cv is null || cv == -1.0) { Console.WriteLine($"    {row["checkContext"],-16} (not calculated)"); continue; }
        Console.WriteLine($"    {row["checkContext"],-16} {cv * 100,6:F2}%  limit {(Num(row["limit"]) ?? 0) * 100:F1}%  [{(Ok(row) ? "ok" : "NOT OK")}]");
    }

    // --- plates: stress Pa->MPa, plastic strain ratio->% ---
    var plates = Vals(data["plates"]).ToList();
    if (plates.Count > 0)
    {
        Console.WriteLine("  Plates (stress -> MPa, plastic strain -> %):");
        foreach (var p in plates)
        {
            var stress = Num(p["maxStress"]); var strain = Num(p["maxStrain"]); var limit = Num(p["limitPlasticStrain"]);
            Console.WriteLine($"    {p["name"],-6} sigma={(stress.HasValue ? $"{stress / 1e6:F1} MPa" : "n/a"),-11} " +
                              $"eps_pl={(strain.HasValue ? $"{strain * 100:F2}%" : "n/a"),-7} " +
                              $"(limit {(limit.HasValue ? $"{limit * 100:F0}%" : "n/a")}) " +
                              $"t={(Num(p["thickness"]) ?? 0) * 1000:F0}mm {p["materialName"]} [{(Ok(p) ? "ok" : "NOT OK")}]");
        }
    }

    // --- welds: unityCheck ratio->%, stresses Pa->MPa, plastic strain ratio->% ---
    var welds = Vals(data["welds"]).OrderByDescending(w => Num(w["unityCheckWeld"]) ?? 0).ToList();
    if (welds.Count > 0)
    {
        Console.WriteLine("  Welds (utilization -> %, stresses -> MPa, plastic strain -> %):");
        string Mpa(JsonNode? n) { var v = Num(n); return v.HasValue ? $"{v / 1e6:F1}" : "n/a"; }
        foreach (var w in welds)
        {
            var pl = Num(w["plasticStrain"]);
            var uc = Num(w["unityCheckWeld"]);
            Console.WriteLine($"    {w["name"],-8} {(uc.HasValue ? $"{uc * 100:F1}%" : "n/a"),7}  " +
                              $"sigma_eqv={Mpa(w["maxEquivalentStress"])}/{Mpa(w["equivalentStressResistance"])} MPa  " +
                              $"sigma_perp={Mpa(w["sigmaPerpendicular"])}  tau=({Mpa(w["taux"])},{Mpa(w["tauy"])})  " +
                              $"eps_pl={(pl.HasValue ? $"{pl * 100:F2}%" : "n/a")}");
            Console.WriteLine($"             throat={(Num(w["thickness"]) ?? 0) * 1000:F1}mm " +
                              $"leg={(Num(w["legSize"]) ?? 0) * 1000:F1}mm {w["weldType2"]} [{(Ok(w) ? "ok" : "NOT OK")}]");
        }
    }

    // --- bolts: forces N->kN, checks ratio->%. forcesAllLoadCases keyed by LE id. ---
    var bolts = Vals(data["bolts"]).OrderByDescending(b => Num(b["maxUnityCheck"]) ?? 0).ToList();
    if (bolts.Count > 0)
    {
        Console.WriteLine("  Bolts (forces -> kN, checks -> %):");
        foreach (var b in bolts)
        {
            Console.WriteLine($"    {b["name"],-5} Ft={(Num(b["boltTensionForce"]) ?? 0) / 1000,6:F1}kN " +
                              $"Fv={(Num(b["boltShearForce"]) ?? 0) / 1000,6:F1}kN  " +
                              $"UC_t={(Num(b["unityCheckTension"]) ?? 0) * 100,4:F0}% " +
                              $"UC_v={(Num(b["unityCheckShear"]) ?? 0) * 100,4:F0}% " +
                              $"inter={(Num(b["interactionTensionShear"]) ?? 0) * 100,5:F1}%  {b["boltAssemblyName"]} [{(Ok(b) ? "ok" : "NOT OK")}]");
            // per-load-effect force vectors [n, qy, qz] in N
            if (b["forcesAllLoadCases"] is JsonObject fa)
                foreach (var kv in fa)
                {
                    var f = kv.Value as JsonArray;
                    if (f is { Count: >= 3 })
                        Console.WriteLine($"           LE {kv.Key}: n={f[0]!.GetValue<double>() / 1000:F1} " +
                                          $"qy={f[1]!.GetValue<double>() / 1000:F1} qz={f[2]!.GetValue<double>() / 1000:F1} kN");
                }
        }
    }

    // --- anchors: steel + concrete failure modes ---
    var anchors = Vals(data["boltsAnchor"]).OrderByDescending(a => Num(a["maxUnityCheck"]) ?? 0).ToList();
    if (anchors.Count > 0)
    {
        Console.WriteLine("  Anchors (forces -> kN, checks -> %):");
        foreach (var a in anchors)
            Console.WriteLine($"    {a["name"],-5} Ft={(Num(a["boltTensionForce"]) ?? 0) / 1000,6:F1}kN  " +
                              $"UC_steel_t={(Num(a["unityCheckTension"]) ?? 0) * 100,4:F0}% " +
                              $"UC_cone={(Num(a["unityCheckConeTensionRes"]) ?? 0) * 100,4:F0}% " +
                              $"inter={(Num(a["interactionTensionShear"]) ?? 0) * 100,5:F1}%  " +
                              $"heff={(Num(a["heff"]) ?? 0) * 1000:F0}mm [{(Ok(a) ? "ok" : "NOT OK")}]");
    }

    // --- concrete block ---
    foreach (var cb in Vals(data["concreteBlocks"]))
        Console.WriteLine($"  Concrete block {cb["name"]}: avg stress {(Num(cb["averageStress"]) ?? 0) / 1e6:F1} / " +
                          $"fjd {(Num(cb["fjd"]) ?? 0) / 1e6:F1} MPa  Nsd={(Num(cb["nsd"]) ?? 0) / 1000:F1}kN  " +
                          $"UC={(Num(cb["maxUnityCheck"]) ?? 0) * 100:F1}% [{(Ok(cb) ? "ok" : "NOT OK")}]");

    // --- base plate shear ---
    foreach (var bp in Vals(data["basePlateShear"]))
        Console.WriteLine($"  Base plate shear {bp["name"]}: V={(Num(bp["v"]) ?? 0) / 1000:F1}kN  " +
                          $"transfer={bp["shearForceTransferMethod"]}  UC={(Num(bp["maxUnityCheck"]) ?? 0) * 100:F1}% [{(Ok(bp) ? "ok" : "NOT OK")}]");

    // --- cost: totalEstimatedCost is the headline; *Costs are itemized breakdowns ---
    if (data["costEstimationResults"] is JsonObject cost)
    {
        int nSteel = (cost["steelCosts"] as JsonArray)?.Count ?? 0;
        int nWeld = (cost["filletWeldCosts"] as JsonArray)?.Count ?? 0;
        Console.WriteLine($"  Estimated cost: total={Num(cost["totalEstimatedCost"]) ?? 0:F2} " +
                          $"({nSteel} steel items, {nWeld} fillet-weld items)");
    }
}
