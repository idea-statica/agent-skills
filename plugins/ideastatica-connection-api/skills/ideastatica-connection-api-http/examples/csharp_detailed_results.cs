// Read detailed CBFEM check results — IDEA StatiCa Connection Rest API 5.0 (C#).
// Mirror of examples/detailed_results.py.
//
// POSTs connection ids to .../connections/results and walks each ConnectionCheckRes
// (summary, plates, welds, bolts, anchors, buckling) + OpenMessages.
//
// IMPORTANT: you must call /calculate first in the SAME client session,
// else the result arrays come back empty. In the simplified /results endpoint, weld/bolt/
// anchor `unityCheck` is ALREADY A PERCENT (do NOT multiply by 100); plate maxStress is
// MPa and maxStrain is on a ratio×10000 scale (eps_pl% = maxStrain/100).
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

// 1. connect-client -> RAW GUID string (text/plain). Attach as ClientId on every call.
var clientId = (await http.GetStringAsync($"{Base}/clients/connect-client")).Trim().Trim('"');
http.DefaultRequestHeaders.Add("ClientId", clientId);
Console.WriteLine($"Connected. ClientId = {clientId}");

// 2. Open the project (multipart, field "ideaConFile").
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

    // Must calculate first (same session) — then /results returns the structured data.
    var calc = await http.PostAsJsonAsync($"{Base}/projects/{projectId}/connections/calculate", ids);
    calc.EnsureSuccessStatusCode();

    var resultsResp = await http.PostAsJsonAsync($"{Base}/projects/{projectId}/connections/results", ids);
    resultsResp.EnsureSuccessStatusCode();
    var results = await resultsResp.Content.ReadFromJsonAsync<JsonArray>();

    foreach (var res in results!.Cast<JsonObject>())
    {
        Console.WriteLine($"\n=== Connection {res["id"]} ({res["name"]}) ===");
        PrintPlates(res["checkResPlate"] as JsonArray);
        PrintCategory("Welds", res["checkResWeld"] as JsonArray, "unityCheck");
        PrintCategory("Bolts", res["checkResBolt"] as JsonArray, "unityCheck");
        PrintCategory("Anchors", res["checkResAnchor"] as JsonArray, "unityCheck");
        PrintBuckling(res["bucklingResults"] as JsonArray);
        PrintSummary(res["checkResSummary"] as JsonArray);
        PrintMessages(res["messages"] as JsonObject);
    }
}
finally
{
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("\nProject closed.");
}

// --- helpers: read documented fields only; null-safe like the Python dict.get() ---

static double? Num(JsonNode? n) =>
    n is JsonValue v && v.TryGetValue<double>(out var d) ? d : null;
static bool Status(JsonObject o) =>
    o["checkStatus"] is JsonValue v && v.TryGetValue<bool>(out var b) ? b : true;

// Welds/bolts/anchors: unityCheck is ALREADY A PERCENT in /results — do not ×100.
void PrintCategory(string label, JsonArray? rows, string field)
{
    if (rows is null || rows.Count == 0) { Console.WriteLine($"  {label}: none"); return; }
    double worst = double.MinValue; bool allOk = true;
    foreach (var r in rows.Cast<JsonObject>())
    {
        if (!Status(r)) allOk = false;
        var v = Num(r[field]);
        if (v.HasValue && v.Value > worst) worst = v.Value;
    }
    var status = allOk ? "PASS" : "FAIL";
    Console.WriteLine($"  {label}: {rows.Count} item(s), worst unity {worst:F1}% [{status}]");
}

// Plates: maxStress is MPa, maxStrain is plastic strain on a ratio×10000 scale
// (eps_pl% = maxStrain/100). No unityCheck ratio for plates.
void PrintPlates(JsonArray? rows)
{
    if (rows is null || rows.Count == 0) { Console.WriteLine("  Plates: none"); return; }
    bool allOk = true; double worstStrain = 0, worstStress = 0;
    foreach (var r in rows.Cast<JsonObject>())
    {
        if (!Status(r)) allOk = false;
        worstStrain = Math.Max(worstStrain, Num(r["maxStrain"]) ?? 0);
        worstStress = Math.Max(worstStress, Num(r["maxStress"]) ?? 0);
    }
    var status = allOk ? "PASS" : "FAIL";
    Console.WriteLine($"  Plates: {rows.Count} item(s), max plastic strain {worstStrain / 100:F2}%, " +
                      $"max stress {worstStress:F1} MPa [{status}]");
}

// Buckling carries a factor (not a unity check); report the smallest (worst).
void PrintBuckling(JsonArray? rows)
{
    if (rows is null || rows.Count == 0) { Console.WriteLine("  Buckling: none (not analyzed)"); return; }
    var factors = rows.Cast<JsonObject>().Select(r => Num(r["factor"])).Where(f => f.HasValue).Select(f => f!.Value).ToList();
    Console.WriteLine(factors.Count > 0
        ? $"  Buckling: {rows.Count} shape(s), min factor {factors.Min():F2}"
        : $"  Buckling: {rows.Count} shape(s), factor n/a");
}

// Summary checkValue is NOT a uniform unit (percent for Analysis/Welds, ratio for Plates);
// display the preformatted unityCheckMessage, skip skipped rows.
void PrintSummary(JsonArray? rows)
{
    if (rows is null) { Console.WriteLine("  Summary rows: (none)"); return; }
    Console.WriteLine("  Summary rows:");
    bool allOk = true; int printed = 0;
    foreach (var r in rows.Cast<JsonObject>())
    {
        if (r["skipped"] is JsonValue s && s.TryGetValue<bool>(out var sk) && sk) continue;
        printed++;
        if (!Status(r)) allOk = false;
        var msg = r["unityCheckMessage"]?.GetValue<string>() ?? $"checkValue={r["checkValue"]}";
        Console.WriteLine($"    - {r["name"]}: {msg} [{(Status(r) ? "ok" : "NOT OK")}]");
    }
    if (printed == 0) Console.WriteLine("    (no summary rows)");
    Console.WriteLine($"  Summary overall: [{(allOk ? "PASS" : "FAIL")}]");
}

// OpenMessages: { messages: [ { number, description } ] }
void PrintMessages(JsonObject? messages)
{
    var list = messages?["messages"] as JsonArray;
    if (list is null || list.Count == 0) return;
    Console.WriteLine("  Messages:");
    foreach (var m in list.Cast<JsonObject>())
    {
        var kind = m["number"]?.ToString() ?? "Message";
        Console.WriteLine($"    [{kind}] {m["description"]}");
    }
}
