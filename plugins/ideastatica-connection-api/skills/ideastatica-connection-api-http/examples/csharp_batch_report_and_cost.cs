// Batch calculate, production cost, and multi-connection reports — Connection Rest API 5.0 (C#).
// Mirror of examples/batch_report_and_cost.py.
//
// Flow: open -> calculate ALL connections ASYNCHRONOUSLY (calculate-async + job polling)
// -> GET production-cost per connection (ConProductionCost) -> POST .../reports/pdf and
// .../reports/word with array<int> of ids (ONE combined report each) -> GET single-connection PDF.
//
// A batch is the case that justifies async: see examples/csharp_async_calculation.cs for the
// job mechanics on their own, plus the ?loadEffectIds= subset selector.
//
// EXPECT A LONG RUN. The wall time is the solver's, not this program's: it scales with
// (connections) x (active load effects), and a load effect the joint cannot carry is the
// slowest of all — the solver retries it in ever smaller load increments before giving up.
// A batch can run for many minutes. Judge a slow run by the job's `message` (it names the
// load effect being solved) rather than assuming the service is stuck. The batch endpoints
// always solve every ACTIVE load effect; to restrict the solve, use the per-connection
// endpoints with ?loadEffectIds= (see examples/csharp_async_calculation.cs).
//
// IMPORTANT: every Report endpoint returns a RAW BINARY FILE STREAM (not JSON) — read the
// bytes and write to disk. The camelCase/JSON rules do not apply to those bodies.
//
// Run (e.g. with the .NET 10 SDK):
//   dotnet new console -o csdemo && cd csdemo   # replace Program.cs with this file
//   dotnet run -- path/to/model.ideaCon
//   Service default: http://localhost:5000

using System.Net.Http.Headers;
using System.Net.Http.Json;
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

var connections = await http.GetFromJsonAsync<JsonArray>($"{Base}/projects/{projectId}/connections") ?? new JsonArray();
if (connections.Count == 0) { Console.WriteLine("No connections."); await http.GetAsync($"{Base}/projects/{projectId}/close"); return; }
var ids = connections.Select(c => c!["id"]!.GetValue<int>()).ToList();
Console.WriteLine($"Connections: [{string.Join(", ", connections.Select(c => $"({c!["id"]},{c!["name"]})"))}]");

try
{
    // 1) Calculate ALL connections at once, ASYNCHRONOUSLY.
    // The synchronous POST .../connections/calculate holds the request open until the LAST
    // connection is solved, forcing a long blind timeout on a big project. calculate-async
    // answers 202 at once, names the connection being solved as it goes, and can be
    // cancelled with DELETE .../calculation-jobs/{jobId}.
    var terminal = new HashSet<string> { "finished", "failed", "cancelled" };
    var start = await http.PostAsJsonAsync($"{Base}/projects/{projectId}/connections/calculate-async", ids);
    start.EnsureSuccessStatusCode();          // 202; 409 = a job is already running
    var job = (await start.Content.ReadFromJsonAsync<JsonObject>())!;
    var jobId = job["jobId"]!.GetValue<string>();
    Console.WriteLine($"  job {jobId} started for connections [{string.Join(", ", ids)}] (status {job["status"]})");

    while (!terminal.Contains(job["status"]!.GetValue<string>()))
    {
        await Task.Delay(1000);
        job = (await http.GetFromJsonAsync<JsonObject>($"{Base}/projects/{projectId}/calculation-jobs/{jobId}"))!;
        // `connectionsCompleted` = the job's progress (`progress` covers only the current
        // connection — endpoints.md § CalculationJobs).
        Console.WriteLine($"  {job["status"],-9} {job["connectionsCompleted"]}/{ids.Count} done, " +
                          $"current={job["currentConnectionId"]} {job["message"]}");
    }
    if (job["status"]!.GetValue<string>() != "finished")
        throw new InvalidOperationException($"calculation {job["status"]}: {job["error"]}");

    foreach (var s in (job["results"] as JsonArray ?? new JsonArray()).Cast<JsonObject>())
    {
        Console.WriteLine($"  Connection {s["id"]}: {(s["passed"]!.GetValue<bool>() ? "PASS" : "FAIL")}");
        foreach (var chk in (s["resultSummary"] as JsonArray ?? new JsonArray()).Cast<JsonObject>())
        {
            if (chk["skipped"] is JsonValue sk && sk.TryGetValue<bool>(out var b) && b) continue;
            var ok = chk["checkStatus"]!.GetValue<bool>() ? "ok" : "NOT OK";
            var msg = chk["unityCheckMessage"]?.GetValue<string>() ?? $"checkValue={chk["checkValue"]}";
            Console.WriteLine($"    - {chk["name"]}: {msg} [{ok}]");
        }
    }

    // 2) Production cost per connection (ConProductionCost — only totalEstimatedCost is documented).
    Console.WriteLine("Production cost per connection:");
    foreach (var cid in ids)
    {
        var cost = await http.GetFromJsonAsync<JsonObject>($"{Base}/projects/{projectId}/connections/{cid}/production-cost");
        Console.WriteLine($"  Connection {cid}: totalEstimatedCost = {cost!["totalEstimatedCost"]}");
    }

    // 3) Multi-connection reports (binary streams). POST array<int> of ids -> one combined file each.
    var pdfMulti = await (await http.PostAsJsonAsync($"{Base}/projects/{projectId}/reports/pdf", ids))
        .EnsureSuccessStatusCode().Content.ReadAsByteArrayAsync();
    await File.WriteAllBytesAsync("report_all.pdf", pdfMulti);
    var wordMulti = await (await http.PostAsJsonAsync($"{Base}/projects/{projectId}/reports/word", ids))
        .EnsureSuccessStatusCode().Content.ReadAsByteArrayAsync();
    await File.WriteAllBytesAsync("report_all.docx", wordMulti);
    Console.WriteLine($"Saved report_all.pdf ({pdfMulti.Length} bytes) and report_all.docx ({wordMulti.Length} bytes)");

    // 4) Single-connection PDF (binary stream) for the first connection.
    var pdfSingle = await http.GetByteArrayAsync($"{Base}/projects/{projectId}/connections/{ids[0]}/reports/pdf");
    await File.WriteAllBytesAsync($"report_connection_{ids[0]}.pdf", pdfSingle);
    Console.WriteLine($"Saved report_connection_{ids[0]}.pdf ({pdfSingle.Length} bytes)");
}
finally
{
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("Project closed.");
}
