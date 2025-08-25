import os
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole
from dotenv import load_dotenv
load_dotenv()


def main() -> None:
    # Required environment variables:
    #   PROJECT_ENDPOINT              -> Azure AI Foundry project endpoint
    #   PLAYWRIGHT_CONNECTION_NAME    -> Name of the Browser Automation (Playwright) connection you created
    #   MODEL_DEPLOYMENT_NAME         -> Name of the model deployment to back the agent
    project_endpoint = os.environ["PROJECT_ENDPOINT"]
    playwright_connection_name = os.environ["PLAYWRIGHT_CONNECTION_NAME"]
    model_name = os.environ["MODEL_DEPLOYMENT_NAME"]

    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )

    with project_client:
        # Resolve the Playwright (browser automation) connection
        playwright_connection = project_client.connections.get(
            name=playwright_connection_name
        )
        print(f"Playwright connection ID: {playwright_connection.id}")

        # Create agent with browser automation tool
        agent = project_client.agents.create_agent(
            model=model_name,
            name="my-agent",
            instructions="Use the browser automation tool to answer user questions.",
            tools=[
                {
                    "type": "browser_automation",
                    "browser_automation": {
                        "connection": {"id": playwright_connection.id}
                    },
                }
            ],
        )
        print(f"Created agent, ID: {agent.id}")

        # Create a thread
        thread = project_client.agents.threads.create()
        print(f"Created thread, ID: {thread.id}")

        # User message
        user_query = os.getenv("PLAYWRIGHT_TEST_QUERY", "Open the Synapxe website and summarize its mission.")
        message = project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_query,
        )
        print(f"Created message: {message.id}")

        # Run the agent
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent.id,
        )
        print(f"Run finished with status: {run.status}")

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
            return

        # Inspect run steps
        run_steps = project_client.agents.run_steps.list(thread_id=thread.id, run_id=run.id)
        for step in run_steps:
            step_id: Optional[str] = getattr(step, "id", None) or step.get("id") if isinstance(step, dict) else None
            step_status: Optional[str] = getattr(step, "status", None) or step.get("status") if isinstance(step, dict) else None
            print(f"Step {step_id} status: {step_status}")

            step_details = getattr(step, "step_details", None) or (step.get("step_details") if isinstance(step, dict) else None)
            if not step_details:
                continue

            tool_calls = getattr(step_details, "tool_calls", None) or step_details.get("tool_calls", []) if isinstance(step_details, dict) else []
            if tool_calls:
                print("  Tool calls:")
                for call in tool_calls:
                    call_id = call.get("id")
                    call_type = call.get("type")
                    print(f"    Tool Call ID: {call_id}")
                    print(f"    Type: {call_type}")
                    fn = call.get("function", {})
                    if fn:
                        print(f"    Function name: {fn.get('name')}")

        # Fetch last agent response
        response_message = project_client.agents.messages.get_last_message_by_role(
            thread_id=thread.id,
            role=MessageRole.AGENT,
        )
        if response_message:
            for text_message in response_message.text_messages:
                print(f"Agent response: {text_message.text.value}")
            for annotation in response_message.url_citation_annotations:
                print(f"URL Citation: [{annotation.url_citation.title}]({annotation.url_citation.url})")

        # Clean up (optional)
        delete_after = os.getenv("DELETE_AGENT_AFTER_RUN", "true").lower() == "true"
        if delete_after:
            project_client.agents.delete_agent(agent.id)
            print("Deleted agent")


if __name__ == "__main__":
    main()