// Asynchronous calculation with job polling, and a load-effect SUBSET — Connection Rest API 5.0 (C#).
// Mirror of examples/async_calculation.py.
//
// Flow: open -> read load effects -> POST .../connections/{id}/calculate-async with
// ?loadEffectIds=... -> poll GET .../calculation-jobs/{jobId} until terminal -> print the
// summary the job carries -> show the same subset selector on the SYNCHRONOUS
// POST .../connections/{id}/calculate.
//
// WHY ASYNC — it is not faster; the solver takes just as long. It buys three things:
//   - No long-held request. The synchronous POST .../connections/calculate keeps the socket
//     open until the LAST connection is solved, so the client needs a timeout longer than the
//     run; dropping it cancels the calculation and can leave partial results
//     (reference/endpoints.md § Calculation). calculate-async answers 202 immediately.
//   - Visible progress. The job's `message` names the load effect and solver iteration being
//     computed right now; a synchronous call is a black box until it returns.
//   - Cancellable. DELETE .../calculation-jobs/{jobId} cancels the job (202); poll the job
//     until it is terminal (reference/endpoints.md § CalculationJobs).
//
// WHY THE SUBSET — ?loadEffectIds= solves ONLY the listed load effects, even if the others
// are active. In a parametric loop this is usually the biggest single saving. It works on
// both the synchronous and the async single-connection endpoints; the plural body-array
// endpoints have no such option.
//
// SIZING A LOAD RAMP — when generating a series of load effects, do NOT guess the top of
// the range: a load effect the joint cannot carry is the slowest of all, since the solver
// retries it in ever smaller increments before giving up. Ask the engine instead. Set the
// connection's analysisType to "total_Design" (the desktop's "Joint design resistance") and
// read the multiplier from rawresults-text for ONE load effect - the selector goes on
// rawresults-text itself, which calculates:
//
//   PUT  .../connections/{id}          the full GET body, "analysisType":"total_Design"
//   POST .../connections/{id}/rawresults-text?loadEffectIds=<one LE>
//       -> totalCapacity["<loadCaseId>"].appliedLoadPercentage   e.g. 4.55
//   PUT  .../connections/{id}          the full GET body, "analysisType":"stress_Strain"   // restore
//
// (Always send the whole connection body you read — reference/io-shapes.md
// § PUT /api/5/projects/{projectId}/connections/{connectionId}.)
//
// That factor scales THAT load effect to the joint's resistance, so a ramp at
// 0.5 / 0.7 / 0.9 x factor stays inside the envelope and every run converges quickly. With
// several load effects there is one entry per load effect (keyed by loadCaseId) — take the
// MINIMUM, as the desktop report does. See reference/raw-results.md (totalCapacity) and
// reference/schemas.md (analysis-type table).
//
// Run (e.g. with the .NET 10 SDK):
//   dotnet new console -o csdemo && cd csdemo   # replace Program.cs with this file
//   dotnet run -- path/to/model.ideaCon
//   Service default: http://localhost:5000

using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Nodes;

const string Base = "http://localhost:5000/api/5";
var terminal = new HashSet<string> { "finished", "failed", "cancelled" };

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
var project = (await openResp.Content.ReadFromJsonAsync<JsonObject>())!;
var projectId = project["projectId"]!.GetValue<string>();
var connections = project["connections"] as JsonArray ?? new JsonArray();
if (connections.Count == 0) { Console.WriteLine("No connections."); await http.GetAsync($"{Base}/projects/{projectId}/close"); return; }
var connectionId = connections[0]!["id"]!.GetValue<int>();
Console.WriteLine($"Opened project {projectId}, using connection {connectionId}");

try
{
    var effects = await http.GetFromJsonAsync<JsonArray>(
        $"{Base}/projects/{projectId}/connections/{connectionId}/load-effects?isPercentage=false")
        ?? new JsonArray();
    Console.WriteLine($"Load effects: [{string.Join(", ", effects.Select(e => $"({e!["id"]},{e!["name"]})"))}]");
    if (effects.Count == 0) { Console.WriteLine("No load effects — nothing to calculate."); return; }

    // Repeatable query parameter: ?loadEffectIds=1&loadEffectIds=2&...
    // All but the last load effect; on a model with one load effect the subset is that one.
    var subset = effects.Take(Math.Max(1, effects.Count - 1)).Select(e => e!["id"]!.GetValue<int>()).ToList();
    var query = string.Join("&", subset.Select(id => $"loadEffectIds={id}"));

    // --- 1) async job over a SUBSET of the load effects ------------------------
    var start = await http.PostAsync(
        $"{Base}/projects/{projectId}/connections/{connectionId}/calculate-async?{query}", null);
    start.EnsureSuccessStatusCode();   // 202 Accepted; 409 = a job is already running
    var job = (await start.Content.ReadFromJsonAsync<JsonObject>())!;
    var jobId = job["jobId"]!.GetValue<string>();
    Console.WriteLine($"Started job {jobId} for load effects [{string.Join(", ", subset)}] " +
                      $"(status {job["status"]})");

    while (!terminal.Contains(job["status"]!.GetValue<string>()))
    {
        await Task.Delay(1000);
        job = (await http.GetFromJsonAsync<JsonObject>(
            $"{Base}/projects/{projectId}/calculation-jobs/{jobId}"))!;
        // `message` carries the live solver line (load effect + iteration).
        // `progress` is a 0..1 fraction for the CURRENT connection (endpoints.md § CalculationJobs).
        var pct = job["progress"]?.GetValue<double>() ?? 0.0;
        Console.WriteLine($"    {job["status"],-9} {pct:F2}  {job["message"]}");
    }

    var status = job["status"]!.GetValue<string>();
    Console.WriteLine($"Job {status}: {job["connectionsCompleted"]} of " +
                      $"{(job["connectionIds"] as JsonArray)?.Count ?? 0} connection(s) completed");

    if (status == "failed")
    {
        Console.WriteLine($"  error: {job["error"]}");
    }
    else
    {
        foreach (var summary in (job["results"] as JsonArray ?? new JsonArray()).Cast<JsonObject>())
        {
            Console.WriteLine($"  connection {summary["id"]}: passed = {summary["passed"]}");
            PrintChecks(summary);
        }
    }

    // A running job can be cancelled with (202; poll the job until terminal, then read
    // POST .../connections/results per connection — reference/endpoints.md § CalculationJobs):
    //   await http.DeleteAsync($"{Base}/projects/{projectId}/calculation-jobs/{jobId}");

    // --- 2) the same subset selector, synchronously ----------------------------
    // Use this when the solve is short enough that polling is not worth it.
    // NOTE: the single-connection endpoint returns ONE ConResultSummary object,
    // while the plural POST .../connections/calculate returns an ARRAY.
    var sync = await http.PostAsync(
        $"{Base}/projects/{projectId}/connections/{connectionId}/calculate?{query}", null);
    sync.EnsureSuccessStatusCode();
    var single = (await sync.Content.ReadFromJsonAsync<JsonObject>())!;
    Console.WriteLine($"Synchronous calculate of the same subset: passed = {single["passed"]}");
    PrintChecks(single);
}
finally
{
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("Project closed.");
}

static void PrintChecks(JsonObject summary)
{
    foreach (var chk in (summary["resultSummary"] as JsonArray ?? new JsonArray()).Cast<JsonObject>())
    {
        if (chk["skipped"] is JsonValue sk && sk.TryGetValue<bool>(out var b) && b) continue;
        var ok = chk["checkStatus"]!.GetValue<bool>() ? "ok" : "NOT OK";
        var msg = chk["unityCheckMessage"]?.GetValue<string>() ?? $"checkValue={chk["checkValue"]}";
        Console.WriteLine($"    - {chk["name"]}: {msg} [{ok}]");
    }
}
