// Call the free Jithox MCP tools from C#. No account, no token.
// Runs: initialize -> tools/call (check_payment_change); never pays or changes a vendor record.
// .NET Framework 4.x: csc /nologo /r:System.Net.Http.dll /r:System.Runtime.Serialization.dll Program.cs
// Offline checks: Program.exe --self-test. Live example: Program.exe.
using System;
using System.IO;
using System.Net.Http;
using System.Runtime.Serialization.Json;
using System.Text;
using System.Threading.Tasks;
using System.Xml;

class Program
{
    const string Url = "https://jithox.com/api/mcp";
    static HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(15) };

    static async Task<string> Rpc(string json)
    {
        using (var request = new HttpRequestMessage(HttpMethod.Post, Url))
        {
            request.Content = new StringContent(json, Encoding.UTF8, "application/json");
            request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream");
            request.Headers.UserAgent.ParseAdd("jithox-mcp-csharp-example/1.0");
            using (var response = await Http.SendAsync(request))
            {
                response.EnsureSuccessStatusCode();
                return await response.Content.ReadAsStringAsync();
            }
        }
    }

    static async Task Run()
    {
        var initialized = RpcResult(await Rpc(
            "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{" +
            "\"protocolVersion\":\"2025-06-18\",\"capabilities\":{}," +
            "\"clientInfo\":{\"name\":\"jithox-mcp-csharp-example\",\"version\":\"1.0.0\"}}}"), "1");
        string server = Text(Need(initialized["serverInfo"], "object")["name"]);

        // Fictitious inputs, preserved exactly. A valid IBAN does not identify its owner.
        string summary = ToolSummary(await Rpc(
            "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{" +
            "\"name\":\"check_payment_change\",\"arguments\":{" +
            "\"newIban\":\"BE71096123456769\",\"ibanOnFile\":\"BE68539007547034\",\"supplierCountry\":\"BE\"}}}"));
        Console.WriteLine("server: " + server);
        Console.Write(summary);
    }

    static string ToolSummary(string json)
    {
        var result = RpcResult(json, "2");
        if (result["isError"] != null && Need(result["isError"], "boolean").InnerText != "false")
            throw new InvalidDataException("MCP tool error; no usable result.");
        var content = Need(result["content"], "array");
        if (content.ChildNodes.Count != 1) throw new InvalidDataException("Expected one tool payload.");
        var item = Need(content.FirstChild as XmlElement, "object");
        if (Text(item["type"]) != "text") throw new InvalidDataException("Expected text payload.");
        var payload = Parse(Text(item["text"]));
        if (Text(payload["kind"]) != "payment_change_check") throw new InvalidDataException("Unexpected tool payload kind.");
        var data = Need(payload["data"], "object");
        var verdict = Text(data["verdict"]);
        if (verdict != "no_change" && verdict != "verify_first" && verdict != "stop" && verdict != "invalid_new_account")
            throw new InvalidDataException("Unknown payment-change verdict.");
        var output = new StringBuilder();
        output.Append("verdict: " + verdict + "\n");
        output.Append("reason: " + Text(data["summary"]) + "\n");
        // This tool calls its human actions requiredSteps (not humanStep).
        var steps = Need(data["requiredSteps"], "array");
        if (steps.ChildNodes.Count == 0) throw new InvalidDataException("Missing human step.");
        foreach (XmlElement step in steps.ChildNodes)
            output.Append("humanStep: " + Text(step) + "\n");
        output.Append("doesNotProve: " + Text(data["doesNotProve"]) + "\n");
        if (payload["billing"] != null)
            output.Append("charged: " + Need(Need(payload["billing"], "object")["charged"], "boolean").InnerText + "\n");
        return output.ToString();
    }

    static XmlElement Need(XmlElement value, string type)
    {
        if (value == null || value.GetAttribute("type") != type)
            throw new InvalidDataException("Missing or invalid " + type + " field.");
        return value;
    }

    static XmlElement RpcResult(string json, string id)
    {
        var root = Parse(json);
        if (root["error"] != null) throw new InvalidDataException("JSON-RPC error; no usable result.");
        if (Text(root["jsonrpc"]) != "2.0" || Need(root["id"], "number").InnerText != id)
            throw new InvalidDataException("Unexpected JSON-RPC version or response id.");
        return Need(root["result"], "object");
    }

    static string Text(XmlElement value)
    {
        string text = Need(value, "string").InnerText;
        if (String.IsNullOrWhiteSpace(text)) throw new InvalidDataException("Empty text field.");
        return text;
    }

    static XmlElement Parse(string json)
    {
        try
        {
            using (var reader = JsonReaderWriterFactory.CreateJsonReader(Encoding.UTF8.GetBytes(json), new XmlDictionaryReaderQuotas()))
            {
                var document = new XmlDocument();
                document.Load(reader);
                return Need(document.DocumentElement, "object");
            }
        }
        catch (XmlException e) { throw new InvalidDataException("Invalid JSON.", e); }
    }

    static void Reject(string name, string json)
    {
        try { ToolSummary(json); }
        catch (InvalidDataException) { Console.WriteLine("PASS " + name); return; }
        throw new Exception("FAIL " + name + ": accepted an error response");
    }

    static void SelfTest()
    {
        if (Http.Timeout != TimeSpan.FromSeconds(15)) throw new Exception("FAIL HTTP timeout: expected 15 seconds");
        Console.WriteLine("PASS HTTP timeout");
        Reject("retired tool", "{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"isError\":true,\"content\":[{\"type\":\"text\",\"text\":\"tool_retired\"}]}}");
        Reject("top-level RPC error", "{\"jsonrpc\":\"2.0\",\"id\":2,\"error\":{\"code\":-32602,\"message\":\"Invalid params\"}}");
        var summary = ToolSummary(Envelope(FixturePayload));
        if (summary != "verdict: verify_first\nreason: Fixture summary\nhumanStep: Fixture call-back\ndoesNotProve: Fixture boundary\n")
            throw new Exception("FAIL normal result: expected compact fields from nested payload, got " + summary);
        Console.WriteLine("PASS normal result");
        Reject("wrong RPC version", Envelope(FixturePayload).Replace("2.0", "1.0"));
        Reject("wrong response id", Envelope(FixturePayload).Replace("\"id\":2", "\"id\":1"));
        Reject("string response id", Envelope(FixturePayload).Replace("\"id\":2", "\"id\":\"2\""));
        Reject("unknown verdict", Envelope(FixturePayload.Replace("verify_first", "safe")));
        Reject("missing verdict", Envelope(FixturePayload.Replace("\"verdict\":\"verify_first\",", "")));
        Reject("missing human step", Envelope(FixturePayload.Replace("[\"Fixture call-back\"]", "[]")));
        Reject("missing boundary", Envelope(FixturePayload.Replace("Fixture boundary", "")));
        Reject("wrong field type", Envelope(FixturePayload.Replace("\"Fixture boundary\"", "false")));
        Reject("input validation failure", Envelope("{\"ok\":false,\"error\":{\"code\":\"invalid_payment_change_input\"}}"));
        Reject("malformed JSON", "not JSON");
        Reject("non-object payload", Envelope("null"));
        var billed = FixturePayload.Replace("\"kind\":", "\"billing\":{\"charged\":false},\"kind\":");
        if (!ToolSummary(Envelope(billed)).Contains("charged: false\n"))
            throw new Exception("FAIL optional billing: missing server charged:false");
        Console.WriteLine("PASS optional billing");
        Reject("invalid billing type", Envelope(billed.Replace("\"charged\":false", "\"charged\":\"false\"")));
        TestRun("HTTP journey", Envelope(FixturePayload), 0,
            "server: fixture-server\n" + summary, 2);
        TestRun("tool error exit", "{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"isError\":true}}", 1, "", 2);
        TestRun("RPC error exit", "{\"jsonrpc\":\"2.0\",\"id\":2,\"error\":{\"code\":-32602}}", 1, "", 2);
        TestRun("schema failure exit", Envelope("{\"ok\":false,\"error\":{\"code\":\"invalid_payment_change_input\"}}"), 1, "", 2);
        TestRun("missing verdict exit", Envelope(FixturePayload.Replace("\"verdict\":\"verify_first\",", "")), 1, "", 2);
        TestRun("missing human step exit", Envelope(FixturePayload.Replace("[\"Fixture call-back\"]", "[]")), 1, "", 2);
        TestRun("missing boundary exit", Envelope(FixturePayload.Replace("Fixture boundary", "")), 1, "", 2);
        TestRun("initialization error exit", "{\"jsonrpc\":\"2.0\",\"id\":1,\"error\":{\"code\":-32603}}", 1, "", 1);
        TestRun("HTTP failure exit", "http-error", 1, "", 1);
        TestRun("timeout exit", "timeout", 1, "", 1);
    }

    // The only mocked boundary is HTTP; exercise the real Main/Rpc/parser path.
    static void TestRun(string name, string reply, int expectedExit, string expectedOutput, int expectedCalls)
    {
        var original = Http;
        var stdout = Console.Out;
        var stderr = Console.Error;
        var handler = new FixtureHandler { Reply = reply, FailInitialize = expectedCalls == 1 };
        using (var client = new HttpClient(handler))
        using (var output = new StringWriter())
        using (var error = new StringWriter())
        {
            try
            {
                Http = client;
                Console.SetOut(output);
                Console.SetError(error);
                int exit = Main(new string[0]);
                if (exit != expectedExit || handler.Calls != expectedCalls ||
                    output.ToString().Replace(((char)13).ToString(), "") != expectedOutput ||
                    (exit == 0 ? error.ToString().Length != 0 : error.ToString().Length == 0))
                    throw new Exception("FAIL " + name + ": exit/output/call count mismatch");
            }
            finally { Http = original; Console.SetOut(stdout); Console.SetError(stderr); }
        }
        Console.WriteLine("PASS " + name);
    }

    class FixtureHandler : HttpMessageHandler
    {
        public int Calls;
        public string Reply;
        public bool FailInitialize;
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, System.Threading.CancellationToken token)
        {
            Calls++;
            if (request.Method != HttpMethod.Post || request.RequestUri.AbsoluteUri != Url ||
                request.Headers.Accept.ToString() != "application/json, text/event-stream" ||
                request.Headers.UserAgent.ToString() != "jithox-mcp-csharp-example/1.0" ||
                request.Headers.Authorization != null || request.Content.Headers.ContentType.MediaType != "application/json")
                throw new Exception("FAIL request URL, method or headers");
            var rpc = Parse(await request.Content.ReadAsStringAsync());
            if (Text(rpc["jsonrpc"]) != "2.0" || Need(rpc["id"], "number").InnerText != Calls.ToString())
                throw new Exception("FAIL request envelope");
            string response;
            if (Calls == 1 && Text(rpc["method"]) == "initialize")
            {
                if (Reply == "timeout") throw new TaskCanceledException("Fixture timeout");
                if (Reply == "http-error") return new HttpResponseMessage(System.Net.HttpStatusCode.ServiceUnavailable);
                if (FailInitialize) return new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent(Reply) };
                response = "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"serverInfo\":{\"name\":\"fixture-server\"}}}";
            }
            else
            {
                var parameters = Need(rpc["params"], "object");
                var input = Need(parameters["arguments"], "object");
                if (Calls != 2 || Text(rpc["method"]) != "tools/call" ||
                    Text(parameters["name"]) != "check_payment_change" || input.ChildNodes.Count != 3 ||
                    Text(input["newIban"]) != "BE71096123456769" || Text(input["ibanOnFile"]) != "BE68539007547034" ||
                    Text(input["supplierCountry"]) != "BE")
                    throw new Exception("FAIL tool request: expected check_payment_change and the exact three inputs");
                response = Reply;
            }
            return new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent(response) };
        }
    }

    // Synthetic fixtures, NOT live evidence or fallback answers.
    const string FixturePayload = "{\"kind\":\"payment_change_check\",\"data\":{\"verdict\":\"verify_first\",\"summary\":\"Fixture summary\",\"requiredSteps\":[\"Fixture call-back\"],\"doesNotProve\":\"Fixture boundary\"}}";

    static string Envelope(string payload)
    {
        using (var stream = new MemoryStream())
        {
            new DataContractJsonSerializer(typeof(string)).WriteObject(stream, payload);
            return "{\"jsonrpc\":\"2.0\",\"id\":2,\"result\":{\"isError\":false,\"content\":[{\"type\":\"text\",\"text\":" + Encoding.UTF8.GetString(stream.ToArray()) + "}]}}";
        }
    }

    static int Main(string[] args)
    {
        try
        {
            if (args.Length == 1 && args[0] == "--self-test") SelfTest();
            else
            {
                // .NET Framework 4.x does not always offer TLS 1.2 by default.
                System.Net.ServicePointManager.SecurityProtocol |= System.Net.SecurityProtocolType.Tls12;
                Run().GetAwaiter().GetResult();
            }
            return 0;
        }
        catch (Exception e) { Console.Error.WriteLine("Failed: " + e.Message); return 1; }
    }
}
