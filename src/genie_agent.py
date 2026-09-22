"""
Foundry agent that calls the Databricks Genie MCP endpoint over the private path.

Network prerequisites (infra/):
  - Foundry account is VNet-injected in West Europe.
  - West Europe VNet is peered to the North Europe Databricks VNet.
  - privatelink.azuredatabricks.net is linked to the West Europe VNet.

Run this from inside the VNet (jump box, Bastion, or VPN). The Foundry endpoint has
public network access disabled, so it is not reachable from a normal workstation.
"""

import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")

# https://<workspace-host>.azuredatabricks.net/api/2.0/mcp/genie/<space-id>
GENIE_MCP_URL = os.environ["GENIE_MCP_URL"]

# Project connection of type "Custom keys" holding Authorization = "Bearer <databricks-token>".
# Create it in the Foundry portal under Project details > Connected resources so the
# Databricks credential is never stored in code or passed at runtime.
GENIE_CONNECTION_ID = os.environ["GENIE_CONNECTION_ID"]


def main() -> None:
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(credential=credential, endpoint=PROJECT_ENDPOINT) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        genie_tool = MCPTool(
            server_label="databricks_genie",
            server_url=GENIE_MCP_URL,
            project_connection_id=GENIE_CONNECTION_ID,
            require_approval="never",
        )

        agent = project_client.agents.create_version(
            agent_name="genie-agent",
            definition=PromptAgentDefinition(
                model=MODEL_NAME,
                instructions=(
                    "You answer questions about Vandemoortele business data. "
                    "Use the Databricks Genie tool for anything requiring data; "
                    "never guess at figures."
                ),
                tools=[genie_tool],
            ),
        )
        print(f"Created agent {agent.name} (id: {agent.id})")

        conversation = openai_client.conversations.create()
        response = openai_client.responses.create(
            conversation=conversation.id,
            input="Ask Genie for total sales volume by product category for last quarter.",
            extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        )
        print(response.output_text)


if __name__ == "__main__":
    main()
