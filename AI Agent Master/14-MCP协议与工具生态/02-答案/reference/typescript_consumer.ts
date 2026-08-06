/** TypeScript MCP contract client：启动本目录 Python stdio server 并调用只读工具。 */
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: "python",
  args: ["mcp_server.py"],
  env: { ...process.env, MCP_DEMO_TENANT: "demo", MCP_DEMO_USER: "contract-test" },
});
const client = new Client({ name: "ticket-contract-test", version: "1.0.0" });

await client.connect(transport);
try {
  const tools = await client.listTools();
  if (!tools.tools.some((tool) => tool.name === "read_ticket")) {
    throw new Error("read_ticket contract missing");
  }
  const result = await client.callTool({ name: "read_ticket", arguments: { ticket_id: "t-100" } });
  console.log(JSON.stringify(result, null, 2));
} finally {
  await client.close();
}

