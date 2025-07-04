import os

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser

from pydantic import BaseModel 
from typing import Any, Optional

from src.chains.bank_faq_chain import faq_vector_chain
from src.chains.bank_cypher_chain import bank_cypher_chain
from src.tools.wait_times import get_current_wait_times, get_most_available_branch

from dotenv import load_dotenv
load_dotenv()

BANK_AGENT_MODEL = os.getenv("BANK_AGENT_MODEL")

agent_chat_model = ChatOpenAI(
    model=BANK_AGENT_MODEL,
    temperature=0,
)




# ✅ NEW: Input schema for bank database tool
class BankCypherInputSchema(BaseModel):
    question: str
    customer_id: Optional[str] = None
    role: Optional[str] = None  # ✅ NEW: include role

# ---- Tools ----
@tool
def explore_product_faqs(question: str) -> str:
    """
    Useful when you need to answer questions about product offerings,
    payment plans and interest rates.
    """

    return faq_vector_chain.invoke(question)

# ✅ REPLACED OLD TOOL WITH ARGS_SCHEMA-BASED TOOL
@tool(args_schema=BankCypherInputSchema)
def explore_bank_database_tool(question: str, customer_id: Optional[str] = None, role: Optional[str] = None) -> str:
    """
    Answers questions about customers and their financial data. 
    If the role is 'Customer', restrict results to the given customer_id.
    """
    return bank_cypher_chain.invoke({
        "question": question,
        "customer_id": customer_id,
        "role": role
    })


@tool
def get_branch_wait_time(branch: str) -> str:
    """
    Use when asked about current wait times at a specific branch.
    """
    return get_current_wait_times(branch)

@tool
def find_most_available_branch(tmp: Any) -> dict[str, float]:
    """
    Finds the branch with the shortest wait time.
    """
    return get_most_available_branch(tmp)

# ✅ UPDATED TOOL REGISTRATION
agent_tools = [
    explore_product_faqs,
    explore_bank_database_tool,
    get_branch_wait_time,
    find_most_available_branch,
]

# ✅ ENHANCED SYSTEM PROMPT
agent_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a helpful banking assistant. Use the user's role and customer_id to determine access:
            - If role is 'Banker', you may access all data.
            - If role is 'Customer', only answer queries related to their customer_id.
            Do not disclose or infer data about other customers for Customers.
            """,
        ),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

agent_llm_with_tools = agent_chat_model.bind_tools(agent_tools)

bank_rag_agent = (
    {
        "input": lambda x: {
            "question": x["input"],
            "customer_id": x.get("customer_id"),
            "role": x.get("role")  #add role
        },
        "agent_scratchpad": lambda x: format_to_openai_tool_messages(
            x["intermediate_steps"]
        ),
    }
    | agent_prompt
    | agent_llm_with_tools
    | OpenAIToolsAgentOutputParser()
)

bank_rag_agent_executor = AgentExecutor(
    agent=bank_rag_agent,
    tools=agent_tools,
    verbose=True,
    return_intermediate_steps=True,
)
