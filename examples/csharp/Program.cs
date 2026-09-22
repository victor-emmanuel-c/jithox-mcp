// Call the free Jithox MCP tools from C#. No account, no token.
// Runs: initialize -> tools/call (check_vat_list_format).
// Works with .NET 6+ (`dotnet run`) and with the .NET Framework 4.x compiler (csc Program.cs).
using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

class Program
{
    const string Url = "https://jithox.com/api/mcp";
    static readonly HttpClient Http = new HttpClient();

    static async Task<string> Rpc(string json)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, Url);
        request.Content = new StringContent(json, Encoding.UTF8, "application/json");
        request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream");
        var response = await Http.SendAsync(request);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStringAsync();
    }

    static async Task Run()
    {
        Console.WriteLine(await Rpc(
            "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{" +
            "\"protocolVersion\":\"2025-06-18\",\"capabilities\":{}," +
            "\"clientInfo\":{\"name\":\"jithox-mcp-csharp-example\",\"version\":\"1.0.0\"}}}"));

        // Free, offline format check for a list of EU VAT numbers.
        // A well-formed number is NOT a registered one: `register` stays `not_run`.
        Console.WriteLine(await Rpc(
            "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{" +
            "\"name\":\"check_vat_list_format\",\"arguments\":{\"rows\":[" +
            "{\"reference\":\"acme\",\"vatId\":\"BE0400378485\"}," +
            "{\"vatId\":\"BE0400378486\"}]}}}"));
    }

    static void Main()
    {
        // .NET Framework 4.x does not always offer TLS 1.2 by default; .NET 6+ ignores this line.
        System.Net.ServicePointManager.SecurityProtocol |= System.Net.SecurityProtocolType.Tls12;
        Run().GetAwaiter().GetResult();
    }
}
