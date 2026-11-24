// Read and update connection parameters (parametric design) — Connection Rest API 5.0 (C#).
// Mirror of examples/parameters.py.
//
// Flow: open project -> GET parameters (IdeaParameter[]) -> with a plate operation, create
// `demo_p`, link it to that plate's thickness, read it back from IOM, PUT, unlink -> PUT one
// IdeaParameterUpdate by Key -> POST evaluate-expression (body is a bare JSON string) -> recalculate.
//
// Run (e.g. with the .NET 10 SDK):
//   dotnet new console -o csdemo && cd csdemo   # replace Program.cs with this file
//   dotnet run -- path/to/model.ideaCon ["2 * Width + 5"]
//   Service default: http://localhost:5000

using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Nodes;

const string Base = "http://localhost:5000/api/5";

if (args.Length < 1) { Console.WriteLine("Usage: dotnet run -- path/to/model.ideaCon [expression]"); return; }
var ideaConPath = args[0];
var expression = args.Length > 1 ? args[1] : "2 * Width + 5";

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
    if (connections!.Count == 0) { Console.WriteLine("No connections."); return; }
    var connId = connections[0]!["id"]!.GetValue<int>();
    Console.WriteLine($"Using connection {connId} ({connections[0]!["name"]})");

    // 1) Read all parameters (including hidden). includeHidden as lowercase query string.
    var paramsArr = await http.GetFromJsonAsync<JsonArray>(
        $"{Base}/projects/{projectId}/connections/{connId}/parameters?includeHidden=true");
    Console.WriteLine($"\nParameters ({paramsArr!.Count}):");
    PrintParameters(paramsArr);

    // 1b) Create a parameter and link it to a plate thickness, so this also runs against a model
    //     that defines no parameters. Pick the target by NAME and read back what that name means.
    var cBase = $"{Base}/projects/{projectId}/connections/{connId}";
    var catalog = await http.GetFromJsonAsync<JsonArray>($"{cBase}/parameters/linkable-properties") ?? new JsonArray();
    var targetProp = catalog.OfType<JsonObject>().FirstOrDefault(p =>
        (string?)p["name"] == "Thickness" && (string?)p["valueType"] == "Float"
        && (string?)p["owner"]?["kind"] == "operation" && ((string?)p["group"] ?? "").EndsWith("plate"));
    if (targetProp is not null)
    {
        var opId = targetProp["owner"]!["operationId"]!.GetValue<int>();
        var propId = targetProp["propertyId"]!.ToString();   // ids are opaque strings
        async Task<string> Thickness()
        {
            // export-iom-connection-data is content-negotiated: ask for JSON explicitly.
            using var req = new HttpRequestMessage(HttpMethod.Get, $"{cBase}/export-iom-connection-data");
            req.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            var iomResp = await http.SendAsync(req);
            iomResp.EnsureSuccessStatusCode();
            var iom = await iomResp.Content.ReadFromJsonAsync<JsonObject>();
            return string.Join(", ", (iom!["plates"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
                .Select(p => $"{p["name"]}={p["thickness"]}"));
        }
        var created = await http.PostAsJsonAsync($"{cBase}/parameters", new JsonObject
        {
            ["key"] = "demo_p", ["parameterType"] = "Float", ["expression"] = "0.02",
            ["description"] = "created by the example",
        });
        var linkResp = created.IsSuccessStatusCode
            ? await http.PostAsJsonAsync($"{cBase}/parameters/links", new JsonObject
            {
                ["parameter"] = "demo_p", ["kind"] = "operation", ["operationId"] = opId, ["propertyId"] = propId,
            })
            : created;
        if (linkResp.IsSuccessStatusCode)
        {
            var link = (await linkResp.Content.ReadFromJsonAsync<JsonObject>())!;
            Console.WriteLine($"\nCreated and linked 'demo_p' to Thickness (operation {opId}, propertyId {propId})");
            // A 200 on the link says the value type fits, not that it applied - read the model back.
            Console.WriteLine($"  IOM plate thickness after linking 0.02: {await Thickness()}");
            (await http.PutAsJsonAsync($"{cBase}/parameters",
                new JsonArray(new JsonObject { ["key"] = "demo_p", ["expression"] = "0.03" }))).EnsureSuccessStatusCode();
            Console.WriteLine($"  after PUT 0.03:                          {await Thickness()}");
            (await http.DeleteAsync($"{cBase}/parameters/links/{link["id"]}")).EnsureSuccessStatusCode();
            Console.WriteLine($"  unlinked; the last applied value stays:  {await Thickness()}");
        }
        else
            Console.WriteLine($"  create/link refused: {(int)linkResp.StatusCode} {await linkResp.Content.ReadAsStringAsync()}");
        paramsArr = await http.GetFromJsonAsync<JsonArray>($"{cBase}/parameters?includeHidden=true");
    }
    if (paramsArr!.Count == 0) { Console.WriteLine("No parameters to update."); return; }

    // 2) Update the first parameter's expression by its Key (append "+ 0" so it stays valid).
    var target = (JsonObject)paramsArr[0]!;
    var key = target["key"]!.GetValue<string>();
    var oldExpr = target["expression"]?.GetValue<string>();
    var newExpr = string.IsNullOrEmpty(oldExpr) ? "0" : $"({oldExpr}) + 0";
    Console.WriteLine($"\nUpdating parameter '{key}': '{oldExpr}' -> '{newExpr}'");

    // body is array<IdeaParameterUpdate> { key, expression }
    var updates = new JsonArray(new JsonObject
    {
        ["key"] = key, ["expression"] = newExpr,
    });
    var putResp = await http.PutAsJsonAsync(
        $"{Base}/projects/{projectId}/connections/{connId}/parameters", updates);
    putResp.EnsureSuccessStatusCode();
    var result = await putResp.Content.ReadFromJsonAsync<JsonObject>();  // ParameterUpdateResponse

    Console.WriteLine($"  setToModel = {result!["setToModel"]}");
    foreach (var fv in (result["failedValidations"] as JsonArray ?? new JsonArray()).Cast<JsonObject>())
        Console.WriteLine($"    FAILED key={fv["key"]} status={fv["validationStatus"]} msg={fv["message"]}");
    // A PUT stores an expression it cannot evaluate and still answers 200; that shows only on
    // the parameter's own validationStatus, not in failedValidations.
    foreach (var p in (result["parameters"] as JsonArray ?? new JsonArray()).Cast<JsonObject>())
        if (p["validationStatus"]?.GetValue<string>() is { } st && st != "Ok")
            Console.WriteLine($"    WARNING key={p["key"]} status={st} msg={p["parameterValidation"]?["message"]}");
    Console.WriteLine("  Resulting parameters:");
    PrintParameters(result["parameters"] as JsonArray);

    // 3) Evaluate free-form expressions (body is a bare JSON string; response is a string).
    //    A self-contained one first; then the caller's - any expression it cannot evaluate
    //    answers a diagnosis-free 500 (reference/parameters.md).
    foreach (var expr in new[] { "1+1", expression })
    {
        Console.WriteLine($"\nEvaluating '{expr}'");
        var evalResp = await http.PostAsJsonAsync(
            $"{Base}/projects/{projectId}/connections/{connId}/evaluate-expression", expr);
        if (evalResp.IsSuccessStatusCode)
            Console.WriteLine($"  result = {await evalResp.Content.ReadFromJsonAsync<string>()}");
        else
            Console.WriteLine($"  evaluate-expression failed: {(int)evalResp.StatusCode} - the expression could not be evaluated on this model");
    }

    // 4) Recalculate so the change takes effect.
    Console.WriteLine("\nRecalculating...");
    var calc = await http.PostAsJsonAsync($"{Base}/projects/{projectId}/connections/calculate", new[] { connId });
    calc.EnsureSuccessStatusCode();
    foreach (var s in (await calc.Content.ReadFromJsonAsync<JsonArray>())!.Cast<JsonObject>())
        Console.WriteLine($"  Connection {s["id"]}: {(s["passed"]!.GetValue<bool>() ? "PASS" : "FAIL")}");
}
finally
{
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("\nProject closed.");
}

// IdeaParameter documented fields: key, expression, value, unit, validationStatus (+ more).
void PrintParameters(JsonArray? ps)
{
    if (ps is null || ps.Count == 0) { Console.WriteLine("  (no parameters)"); return; }
    foreach (var p in ps.Cast<JsonObject>())
        Console.WriteLine($"  key={p["key"]} expression={p["expression"]} value={p["value"]} " +
                          $"unit={p["unit"]} validationStatus={p["validationStatus"]}");
}
