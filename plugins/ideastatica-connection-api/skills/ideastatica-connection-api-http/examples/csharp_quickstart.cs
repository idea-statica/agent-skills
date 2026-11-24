// Quickstart for the IDEA StatiCa Connection REST API (Connection Rest API 5.0)
// using raw HttpClient. Mirrors examples/quickstart.py.
//
// For production C#, prefer the generated NuGet client `IdeaStatiCa.ConnectionApi`
// (auto-generated from the same swagger.json) — but you still set the ClientId header
// yourself after connect-client. This sample uses plain HttpClient for clarity.
//
// Run (e.g. with the .NET 10 SDK):
//   dotnet new console -o csdemo && cd csdemo
//   # replace Program.cs with this file
//   dotnet run -- path/to/model.ideaCon
// System.Net.Http.Json ships in-box with modern .NET (no package needed on .NET 5+).
//   Service default: http://localhost:5000

using System.Net.Http.Headers;
using System.Net.Http.Json;

const string Base = "http://localhost:5000/api/5";

using var http = new HttpClient();

// 1. connect-client -> RAW GUID string (text/plain), NOT JSON.
var clientId = (await http.GetStringAsync($"{Base}/clients/connect-client"))
    .Trim().Trim('"');
Console.WriteLine($"Connected. ClientId = {clientId}");

// Attach ClientId to every subsequent request (exact header casing: "ClientId").
http.DefaultRequestHeaders.Add("ClientId", clientId);

// 2. Open a project — multipart/form-data, file field MUST be named "ideaConFile".
var ideaConPath = args.Length > 0 ? args[0] : throw new ArgumentException("pass .ideaCon path");
using var form = new MultipartFormDataContent();
var bytes = await File.ReadAllBytesAsync(ideaConPath);
var fileContent = new ByteArrayContent(bytes);
fileContent.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
form.Add(fileContent, "ideaConFile", Path.GetFileName(ideaConPath));

var openResp = await http.PostAsync($"{Base}/projects/open", form);
openResp.EnsureSuccessStatusCode();
var project = await openResp.Content.ReadFromJsonAsync<ConProject>();
var projectId = project!.ProjectId;
Console.WriteLine($"Opened project {projectId}");

try
{
    // 3. List connections.
    var connections = await http.GetFromJsonAsync<List<ConConnection>>(
        $"{Base}/projects/{projectId}/connections");
    var ids = connections!.Select(c => c.Id).ToList();

    // 5. Calculate — body is a JSON array of ints.
    var calcResp = await http.PostAsJsonAsync(
        $"{Base}/projects/{projectId}/connections/calculate", ids);
    calcResp.EnsureSuccessStatusCode();
    var summaries = await calcResp.Content.ReadFromJsonAsync<List<ConResultSummary>>();

    foreach (var s in summaries!)
        Console.WriteLine($"  Connection {s.Id}: {(s.Passed ? "PASS" : "FAIL")}");

    // 8. Download the updated project.
    var outBytes = await http.GetByteArrayAsync($"{Base}/projects/{projectId}/download");
    await File.WriteAllBytesAsync("result.ideaCon", outBytes);
    Console.WriteLine("Saved result.ideaCon");
}
finally
{
    // 9. Close to free service memory (GET, not DELETE).
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("Project closed.");
}

// Minimal DTOs — JSON is camelCase; System.Text.Json matches case-insensitively by default
// in ASP.NET-style responses, but be explicit if you hit mismatches.
record ConProject(Guid ProjectId, List<ConConnection>? Connections);
record ConConnection(int Id, string? Name);
record ConResultSummary(int Id, bool Passed, List<CheckResSummary>? ResultSummary);
record CheckResSummary(double CheckValue, bool CheckStatus, int LoadCaseId, string? Name);
