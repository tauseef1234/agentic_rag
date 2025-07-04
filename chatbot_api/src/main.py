from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware # prevent unpredictable browers blocks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.agents.bank_rag_agent import bank_rag_agent_executor
from src.models.bank_rag_query import BankQueryInput, BankQueryOutput
from src.utils.async_utils import async_retry
from neo4j import GraphDatabase   # add user verification
import os
from src.memory_manager import MemoryManager

# Initialize memory
memory = MemoryManager()

# Create FastAPI app
app = FastAPI(
    title="Retail Bank Chatbot",
    description="Endpoints for a banking system graph RAG chatbot",
)

# add CORS Middleware (needed if frontend and backend are on different ports/domains)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use ["http://localhost:8501"] for more secure setting
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Neo4j credentials from .env or hardcoded for local testing
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Checking NEO4J_URL

print("NEO4J_URI =", os.getenv("NEO4J_URI"))
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# -----------------------------
# Step 1: Customer Verification 
# -----------------------------

class CustomerVerificationRequest(BaseModel):
    first_name: str
    last_name: str
    zip_code: str
    phone: str

# Verify Customer identity endpoint
@app.post("/verify-customer")
def verify_customer(data: CustomerVerificationRequest):
    query = """
    MATCH (c:Customer)
    WHERE toLower(c.first_name) = toLower($first_name)
      AND toLower(c.last_name) = toLower($last_name)
      AND c.zip_code = $zip_code
      AND c.phone_number = $phone
    RETURN c.id AS customer_id, c.email AS email
    """

    with driver.session(database="neo4j") as session:
        result = session.run(query, {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "zip_code": data.zip_code,
            "phone": data.phone
        })
        record = result.single()

    print("✅ Neo4j raw record:", record)

    if record and record.get("customer_id") is not None:
        customer_id = str(record["customer_id"])  # ✅ Ensure string conversion
        return {
            "verified": True,
            "customer_id": customer_id,
            "email": record.get("email", "")
        }
    else:
        print("❌ Verification failed: No matching customer found or missing customer_id.")
        return {"verified": False}


# ------------------------------
# Step 2: Chat Query Input Model （ already import from models
# ------------------------------
# class BankQueryInput(BaseModel):
#     text: str
#     customer_id: str = None  # This is optional but required for customer-restricted queries


# -------------------------------------
# Step 3: Protected Chat Agent Endpoint
# -------------------------------------
@async_retry(max_retries=10, delay=1)
async def invoke_agent_with_retry(input_payload:dict):
    """
    Retry the agent if a tool fails to run. This can help when there
    are intermittent connection issues to external APIs.
    """

    return await bank_rag_agent_executor.ainvoke(input_payload)



# -------------------------------------
# Step 4: Protected Chat Agent Endpoint 
# -------------------------------------

@app.post("/bank-rag-agent")
async def ask_bank_agent(query: BankQueryInput, request:Request) -> BankQueryOutput:

    # <added> get role & customer_id
    role = query.role
    customer_id = query.customer_id

    # <added> get memory from history
    history = memory.get_messages(role,customer_id)
    memory.append_message(role, customer_id, f"{role}: {query.input}")

    # <added> prepend history
    full_input = "\n".join(history) + f"\n{role}: {query.input}"


    #  Use dict to pass full input to agent, including optional customer_id
    # input_payload = {
    #     "input": query.input,
    #     "customer_id": query.customer_id,
    #     "role": query.role # add role
    # }

    input_payload = {
        "input": full_input,
        "customer_id": customer_id,
        "role": role
    }

    # debug
    print("📨 Agent input payload:", input_payload)

    #  call ainvoke with full payload
    query_response = await invoke_agent_with_retry(input_payload)

    query_response["intermediate_steps"] = [
        str(s) for s in query_response["intermediate_steps"]
    ]
    print(query_response)

    # <added> Save response to memory
    memory.append_message(role, customer_id, f"bot: {query_response['output']}")

    return query_response


# <added> New reset memory endpoint
@app.post("/reset-conversation") 
async def reset_conversation(request: Request, role: str="Customer"):
    try:
        print(f"Reset request received for role: {role}")
        return JSONResponse(content={"status":"success"})
    except Exception as e:
        print("Reset error: ",str(e))
        return JSONResponse(status_code=500, content = {"status": "error", "message": str(e)})


@app.get("/")
async def get_status():
    return {"status": "running"}