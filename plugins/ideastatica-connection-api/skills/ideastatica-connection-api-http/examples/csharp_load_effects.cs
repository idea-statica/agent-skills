// Define load effects then calculate — Connection Rest API 5.0 (C#).
// Mirror of examples/load_effects.py.
//
// Flow: open -> GET members (ConMember[]) -> GET load-effects -> POST a new ConLoadEffect
// (memberLoadings with section loads n/vy/vz/mx/my/mz) -> PUT update one -> set-load-settings
// -> calculate-load-extremes -> calculate.
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

var connections = await http.GetFromJsonAsync<JsonArray>($"{Base}/projects/{projectId}/connections");
if (connections!.Count == 0) { Console.WriteLine("No connections."); await http.GetAsync($"{Base}/projects/{projectId}/close"); return; }
var connId = connections[0]!["id"]!.GetValue<int>();
Console.WriteLine($"Using connection {connId} ({connections[0]!["name"]})");
var cbase = $"{Base}/projects/{projectId}/connections/{connId}";

try
{
    // 1) Members give the real ids / positions that load effects must reference.
    var members = await http.GetFromJsonAsync<JsonArray>($"{cbase}/members") ?? new JsonArray();
    if (members.Count == 0) { Console.WriteLine("No members."); return; }
    Console.WriteLine($"Members: [{string.Join(", ", members.Select(m => $"({m!["id"]},{m!["name"]})"))}]");

    // 2) Existing load effects (so we have an id to PUT later) — and, more importantly, the
    //    (memberId, position) slots this connection actually registers. That is not derivable
    //    from connectedBy; see BuildMemberLoadings. A model imported with results has at least one LE.
    var existing = await http.GetFromJsonAsync<JsonArray>($"{cbase}/load-effects?isPercentage=false") // absolute N / N·m
        ?? new JsonArray();
    Console.WriteLine($"Existing load effects: [{string.Join(", ", existing.Select(le => $"({le!["id"]},{le!["name"]})"))}]");

    // The first load effect that loads a member fixes the end it accepts (reference/io-shapes.md
    // § LoadEffect): reuse the (memberId, position) pairs of an existing load effect.
    var knownSlots = new Dictionary<int, string>();
    if (existing.Count > 0 && existing[0]!["memberLoadings"] is JsonArray used)
        foreach (var ld in used.OfType<JsonObject>())
            if (ld["memberId"] is JsonValue id && ld["position"] is JsonValue pos)
                knownSlots.TryAdd(id.GetValue<int>(), pos.GetValue<string>());

    // 3) POST a new load effect with one section load per active member.
    var newLe = new JsonObject
    {
        ["name"] = "API LE1",
        ["active"] = true,        // honoured; send it explicitly
        ["isPercentage"] = false, // always: absolute N / N·m values
        ["memberLoadings"] = BuildMemberLoadings(members, knownSlots),
    };
    var createResp = await http.PostAsJsonAsync($"{cbase}/load-effects", newLe);
    createResp.EnsureSuccessStatusCode();
    var created = await createResp.Content.ReadFromJsonAsync<JsonObject>();
    Console.WriteLine($"Created load effect id={created!["id"]} name={created["name"]}");

    // 4) PUT to update one existing load effect (id selects which one).
    //    Prefer a pre-existing one; otherwise update the one we just created.
    //
    //    PUT can only UPDATE member/position slots the load effect already has — it cannot
    //    add one. A slot that isn't there is 422:
    //      "Updating loading : MemberId:1 - Position:Begin was not found in internal
    //       forces of Load effect 1 ... Available forces BeamId:2, IsBegin:False"
    //    (and a member with no internal forces in the model, e.g. the bearing member of a
    //    simple joint, has no slot at all). So take the slots from the target itself and
    //    rewrite their magnitudes; use POST to introduce a new set.
    JsonObject target = existing.Count > 0 ? (JsonObject)existing[0]! : created!;
    var targetLoadings = new JsonArray();
    foreach (var ld in (target["memberLoadings"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
        targetLoadings.Add(new JsonObject
        {
            ["memberId"] = ld["memberId"]!.GetValue<int>(),
            ["position"] = ld["position"]!.GetValue<string>(),
            ["sectionLoad"] = new JsonObject
            {
                ["n"] = 100000.0, ["vy"] = 0.0, ["vz"] = 50000.0,
                ["mx"] = 0.0, ["my"] = 25000.0, ["mz"] = 0.0,
            },
        });
    // An omitted `active` is true, so a PUT without it re-activates the load effect: send the
    // target's own flag unless you mean to change it.
    var updateBody = new JsonObject
    {
        ["id"] = target["id"]!.GetValue<int>(),
        ["name"] = "API LE1 updated",
        ["active"] = target["active"]!.GetValue<bool>(), // keep the flag: omitted, it would be true
        ["isPercentage"] = false,
        ["memberLoadings"] = targetLoadings,
    };
    var updateResp = await http.PutAsJsonAsync($"{cbase}/load-effects", updateBody);
    updateResp.EnsureSuccessStatusCode();
    var updated = await updateResp.Content.ReadFromJsonAsync<JsonObject>();
    Console.WriteLine($"Updated load effect id={updated!["id"]} name={updated["name"]}");

    // 5) Set load settings (ConLoadSettings), then run Load Extremes (LEX) reduction.
    var settingsResp = await http.PostAsJsonAsync($"{cbase}/load-effects/set-load-settings",
        new JsonObject { ["loadsInEquilibrium"] = false, ["loadsInPercentage"] = false });
    settingsResp.EnsureSuccessStatusCode();
    var settings = await settingsResp.Content.ReadFromJsonAsync<JsonObject>();
    Console.WriteLine($"Load settings: equilibrium={settings!["loadsInEquilibrium"]} percentage={settings["loadsInPercentage"]}");

    var lexResp = await http.PostAsync($"{cbase}/load-effects/calculate-load-extremes", null);
    lexResp.EnsureSuccessStatusCode();
    var lex = await lexResp.Content.ReadFromJsonAsync<JsonArray>();
    var active = lex!.Cast<JsonObject>().Where(le => le["active"]!.GetValue<bool>()).Select(le => $"({le["id"]},{le["name"]})");
    Console.WriteLine($"Load extremes -> active: [{string.Join(", ", active)}]");

    // 6) Calculate and print pass/fail (use the preformatted unityCheckMessage).
    Console.WriteLine("Calculating...");
    var calc = await http.PostAsJsonAsync($"{Base}/projects/{projectId}/connections/calculate", new[] { connId });
    calc.EnsureSuccessStatusCode();
    foreach (var s in (await calc.Content.ReadFromJsonAsync<JsonArray>())!.Cast<JsonObject>())
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
}
finally
{
    await http.GetAsync($"{Base}/projects/{projectId}/close");
    Console.WriteLine("Project closed.");
}

// Build ConLoadEffectMemberLoad[] — one section load per active member. A member with
// "active": false is skipped: one loading on an inactive member makes the service refuse the
// whole POST with 422 "ConLoadEffectMemberLoad is defined for member 'N' that is not active".
// The position comes from an existing load effect when there is one (knownSlots); a member no
// load effect has loaded yet accepts either end, so the fallback ("Begin" if continuous, else
// "End") is free. NOTE: this is
// ConLoadEffectPositionEnum, whose wire values are PascalCase ("Begin"/"End") — do not
// confuse with ConMember.connectedBy, which is lowercase ("begin"/"end"); input binding is
// case-insensitive, but emit PascalCase. A wrong end is refused with 422 "Defined member loading
// Member:N, Position:X is not defined in connection M". Section load components
// n/vy/vz/mx/my/mz are N/N·m, a vector in the member LCS at a stub's free end: a positive n is
// tension in a stub on +x of the node (an ended connectedBy "begin" member, or a continuous
// member's "End" loading) and compression on -x (an ended "end" member, or a continuous
// member's "Begin" loading). An ended member's loading acts the same under either position
// label. Members omitted from memberLoadings are NOT an error; GET the load effect back to see
// the rows it stored. Send all six sectionLoad components, spelled exactly. See
// reference/io-shapes.md § LoadEffect.
JsonArray BuildMemberLoadings(JsonArray members, IReadOnlyDictionary<int, string> knownSlots)
{
    var arr = new JsonArray();
    foreach (var m in members.Cast<JsonObject>())
    {
        if (m["active"] is JsonValue a && a.TryGetValue<bool>(out var isActive) && !isActive)
            continue; // an inactive member cannot carry a loading (422)
        int id = m["id"]!.GetValue<int>();
        bool isContinuous = m["isContinuous"] is JsonValue v && v.TryGetValue<bool>(out var b) && b;
        arr.Add(new JsonObject
        {
            ["memberId"] = id,
            ["position"] = knownSlots.TryGetValue(id, out var slot) ? slot : isContinuous ? "Begin" : "End",
            ["sectionLoad"] = new JsonObject
            {
                ["n"] = 100000.0, ["vy"] = 0.0, ["vz"] = 50000.0,
                ["mx"] = 0.0, ["my"] = 25000.0, ["mz"] = 0.0,
            },
        });
    }
    return arr;
}
