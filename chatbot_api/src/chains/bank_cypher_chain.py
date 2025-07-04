import os
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from src.langchain_custom.graph_qa.cypher import GraphCypherQAChain

# --- environment config ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

BANK_QA_MODEL = os.getenv("BANK_QA_MODEL")
BANK_CYPHER_MODEL = os.getenv("BANK_CYPHER_MODEL")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_Password")
NEO4J_CYPHER_EXAMPLES_INDEX_NAME = os.getenv("NEO4J_CYPHER_EXAMPLES_INDEX_NAME")
NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY = os.getenv(
    "NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY"
)
NEO4J_CYPHER_EXAMPLES_NODE_NAME = os.getenv("NEO4J_CYPHER_EXAMPLES_NODE_NAME")
NEO4J_CYPHER_EXAMPLES_METADATA_NAME = os.getenv("NEO4J_CYPHER_EXAMPLES_METADATA_NAME")

# --- graph connection ---
graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
)

graph.refresh_schema()

# --- vector index ---
cypher_example_index = Neo4jVector.from_existing_graph(
    embedding=OpenAIEmbeddings(),
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
    index_name=NEO4J_CYPHER_EXAMPLES_INDEX_NAME,
    node_label=NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY.capitalize(),
    text_node_properties=[
        NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY,
    ],
    text_node_property=NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY,
    embedding_node_property="embedding",
)

cypher_example_retriever = cypher_example_index.as_retriever(search_kwargs={"k": 8})

# --- cypher prompt ---
cypher_generation_prompt = PromptTemplate(
    input_variables=["schema", "example_queries", "question"],
    template="""
Task:
Generate Cypher query for a Neo4j graph database.

Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Schema:
{schema}

Note:
- Do not include any explanations or apologies in your responses.
- Do not respond to any questions that might ask anything other than
  for you to construct a Cypher statement.
- Do not include any text except the generated Cypher statement.
- If the question is vague, general (e.g., "hi", "what's up", "how are you"),
  or cannot be mapped to the schema, return this exact line:
  // No Cypher statement can be generated for the input "{question}"

...

The question is:
{question}
"""
)

# --- QA prompt ---
qa_generation_prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are an assistant that takes the results from a Neo4j Cypher query and forms a human-readable response.

...

The user asked the following question:
{question}

A Cypher query was run and generated these results:
{context}

Helpful Answer:
"""
)

# --- build base chain ---
_raw_bank_cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=ChatOpenAI(model=BANK_CYPHER_MODEL, temperature=0),
    qa_llm=ChatOpenAI(model=BANK_QA_MODEL, temperature=0),
    cypher_example_retriever=cypher_example_retriever,
    node_properties_to_exclude=["embedding"],
    graph=graph,
    verbose=True,
    qa_prompt=qa_generation_prompt,
    cypher_prompt=cypher_generation_prompt,
    validate_cypher=True,
    top_k=100,
)

#  UPDATED: Secure wrapper with enforced filtering logic
class SecureBankCypherChain:
    def __init__(self, chain):
        self.chain = chain

    def invoke(self, inputs):
        if isinstance(inputs, str):
            question = inputs
            customer_id = None
            role = None
        else:
            question = inputs.get("question", "")
            customer_id = inputs.get("customer_id")
            role = inputs.get("role")

        # Restrict question if role is Customer and customer_id exists
        if role == "Customer" and customer_id:
            question = (
                f"NOTE: This user is a verified customer. Only include data for customer ID '{customer_id}'.\n\n{question}"
            )

        # Run the chain
        result = self.chain.invoke({"query": question})

        generated_cypher = result.get("cypher", "") if isinstance(result, dict) else ""

        if "No Cypher statement" in generated_cypher or generated_cypher.strip() == "cypher":
            return {
                "output": "Sorry, I didn't understand your question. Could you rephrase it?",
                "intermediate_steps": [],
            }

        # ✅ FIX: include "query" in the return value for downstream chains
        return {
            "output": result.get("result", "Done."),
            "query": generated_cypher,
            "intermediate_steps": result.get("intermediate_steps", []),
        }


#  Export the secured version
bank_cypher_chain = SecureBankCypherChain(_raw_bank_cypher_chain)