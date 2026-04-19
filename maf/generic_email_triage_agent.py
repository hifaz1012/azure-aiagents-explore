"""Generic email triage workflow using Azure Agent Framework.

This script expands on the basic spam/not-spam example by having the
triage agent classify incoming mail into multiple business categories and
routing to specialized handlers or responders based on that label.

Categories supported out of the box:
- spam              -> short-circuited with a spam notice
- customer_support  -> drafts an empathetic support response
- sales             -> drafts a sales-oriented follow-up
- billing           -> drafts a billing/accounting response
- general_inquiry   -> drafts a general professional reply

You can extend ``CATEGORY_CONFIG`` with additional categories or tune the
instructions for your use case.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, List

from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    ChatMessage,
    Role,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field
from typing_extensions import Never

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryConfig:
    name: str
    instructions: str


CATEGORY_CONFIG: Dict[str, CategoryConfig] = {
    "customer_support": CategoryConfig(
        name="customer_support",
        instructions=(
            "You are a customer support specialist. Craft a helpful, empathetic response "
            "that acknowledges the customer's concern, provides clear next steps, and uses a reassuring tone. "
            "Respond in JSON with fields 'reply' (string) and 'actions' (array of follow-up steps)."
        ),
    ),
    "sales": CategoryConfig(
        name="sales",
        instructions=(
            "You are a sales representative preparing a persuasive reply. Highlight product value, "
            "offer next steps, and ask an open question to keep the conversation moving. "
            "Respond in JSON with fields 'reply' and 'actions'."
        ),
    ),
    "billing": CategoryConfig(
        name="billing",
        instructions=(
            "You are a billing specialist. Provide a clear, professional response that references account details "
            "when needed and suggests precise follow-up steps. "
            "Respond in JSON with fields 'reply' and 'actions'."
        ),
    ),
    "general_inquiry": CategoryConfig(
        name="general_inquiry",
        instructions=(
            "You handle general inquiries. Provide a concise, professional reply summarizing the email and "
            "indicating how you'll follow up. "
            "Respond in JSON with fields 'reply' and 'actions'."
        ),
    ),
}

TRIAGE_LABELS: List[str] = ["spam", *CATEGORY_CONFIG.keys()]

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TriageResult(BaseModel):
    """Structured output from the triage agent."""

    category: str = Field(description=f"One of: {', '.join(TRIAGE_LABELS)}")
    confidence: float = Field(ge=0.0, le=1.0)
    priority: str  # Example: "low", "medium", "high"
    summary: str
    reason: str
    email_content: str


class FollowUpResponse(BaseModel):
    """Structured output from category-specific responders."""

    reply: str
    actions: List[str] = Field(default_factory=list, description="Suggested follow-up steps")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_category_condition(expected_category: str):
    """Create an edge predicate for a specific triage category."""

    def predicate(message: Any) -> bool:
        if not isinstance(message, AgentExecutorResponse):
            return False
        try:
            result = TriageResult.model_validate_json(message.agent_run_response.text)
            return result.category == expected_category
        except Exception:
            return False

    return predicate


def get_non_spam_condition(message: Any) -> bool:
    """Allow routing when the category is not spam and is recognized."""
    if not isinstance(message, AgentExecutorResponse):
        return False
    try:
        result = TriageResult.model_validate_json(message.agent_run_response.text)
        return result.category in CATEGORY_CONFIG
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


@executor(id="handle_spam_triage")
async def handle_spam_triage(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    result = TriageResult.model_validate_json(response.agent_run_response.text)
    await ctx.yield_output(
        "Email classified as spam with reason: "
        f"{result.reason} (confidence {result.confidence:.2f})."
    )


@executor(id="to_category_follow_up")
async def to_category_follow_up(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    result = TriageResult.model_validate_json(response.agent_run_response.text)
    config = CATEGORY_CONFIG.get(result.category)
    if not config:
        raise RuntimeError(f"No handler configured for category '{result.category}'.")

    system_text = (
        f"Category: {result.category}\nPriority: {result.priority}\n"
        f"Summary: {result.summary}\nReasoning: {result.reason}\n\n"
        f"Instructions: {config.instructions}"
    )
    system_msg = ChatMessage(Role.SYSTEM, text=system_text)
    user_msg = ChatMessage(
        Role.USER,
        text=(
            "Here is the email that needs a response. Draft the reply in JSON as instructed.\n\n"
            f"{result.email_content}"
        ),
    )
    await ctx.send_message(AgentExecutorRequest(messages=[system_msg, user_msg], should_respond=True))


@executor(id="deliver_follow_up")
async def deliver_follow_up(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    follow_up = FollowUpResponse.model_validate_json(response.agent_run_response.text)
    action_lines = "\n".join(f"- {step}" for step in follow_up.actions) or "(no additional actions)"
    await ctx.yield_output(
        "Drafted reply:\n"
        f"{follow_up.reply}\n\nNext actions:\n{action_lines}"
    )


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------


async def main() -> None:
    chat_client = AzureOpenAIChatClient(credential=DefaultAzureCredential())

    triage_instructions = (
        "You are an email triage assistant. Analyze the incoming email and classify it into one of the "
        f"following categories: {', '.join(TRIAGE_LABELS)}.\n"
        "Return JSON with fields: category, confidence (0-1), priority (low/medium/high), summary, reason,"
        " and email_content (the original email)."
    )
    triage_agent = AgentExecutor(
        chat_client.create_agent(
            instructions=triage_instructions,
            response_format=TriageResult,
        ),
        id="triage_agent",
    )

    follow_up_agent = AgentExecutor(
        chat_client.create_agent(
            instructions=(
                "You are a versatile email responder that adapts to the provided system context. Always return JSON "
                "with 'reply' (string) and 'actions' (array of strings)."
            ),
            response_format=FollowUpResponse,
        ),
        id="follow_up_agent",
    )

    workflow = (
        WorkflowBuilder()
        .set_start_executor(triage_agent)
        .add_edge(triage_agent, handle_spam_triage, condition=get_category_condition("spam"))
        .add_edge(triage_agent, to_category_follow_up, condition=get_non_spam_condition)
        .add_edge(to_category_follow_up, follow_up_agent)
        .add_edge(follow_up_agent, deliver_follow_up)
        .build()
    )

    email_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "maf", "email.txt")
    with open(email_path) as fh:  # noqa: ASYNC230
        email_body = fh.read()

    request = AgentExecutorRequest(messages=[ChatMessage(Role.USER, text=email_body)], should_respond=True)
    events = await workflow.run(request)
    outputs = events.get_outputs()
    if outputs:
        print("Workflow output:\n" + outputs[0])


if __name__ == "__main__":
    asyncio.run(main())
