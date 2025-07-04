import os
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain_openai import OpenAIEmbeddings
# Assuming src.langchain_custom.graph_qa.cypher.GraphCypherQAChain is available
# If not, you might need to adjust this import or use the standard one from langchain_community
from src.langchain_custom.graph_qa.cypher import GraphCypherQAChain

# --- Environment Variable Setup ---
# Ensure these are set in your environment
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password") # Standardized variable name

BANK_QA_MODEL = os.getenv("BANK_QA_MODEL", "gpt-3.5-turbo") # Default if not set
BANK_CYPHER_MODEL = os.getenv("BANK_CYPHER_MODEL", "gpt-3.5-turbo") # Default if not set

# Environment variables for example query retriever (optional but kept from original)
NEO4J_CYPHER_EXAMPLES_INDEX_NAME = os.getenv("NEO4J_CYPHER_EXAMPLES_INDEX_NAME", "cypher-examples")
NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY = os.getenv("NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY", "text")
# NEO4J_CYPHER_EXAMPLES_NODE_NAME = os.getenv("NEO4J_CYPHER_EXAMPLES_NODE_NAME") # Not directly used in this revised example retrieval logic
# NEO4J_CYPHER_EXAMPLES_METADATA_NAME = os.getenv("NEO4J_CYPHER_EXAMPLES_METADATA_NAME") # Not directly used

# --- Neo4j Graph Connection ---
graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
)

try:
    graph.refresh_schema()
except Exception as e:
    print(f"Error refreshing Neo4j schema: {e}")
    print("Please ensure your Neo4j instance is running and credentials are correct.")
    # Potentially exit or handle error appropriately
    graph.schema = "Failed to load schema. Placeholder schema: Node properties are the following: customer {name: STRING, id: STRING}" # Provide a fallback or ensure exit


# --- Example Cypher Query Retriever (Optional, kept from original structure) ---
# This part is useful if you have a Neo4j index of example Cypher queries.
# For specific customer verification, its utility depends on having relevant examples.
try:
    cypher_example_index = Neo4jVector.from_existing_graph(
        embedding=OpenAIEmbeddings(), # Requires OPENAI_API_KEY
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        index_name=NEO4J_CYPHER_EXAMPLES_INDEX_NAME,
        # Ensure this node_label matches how your example query nodes are labelled.
        # NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY.capitalize() might be e.g., "Text"
        node_label=NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY.capitalize(),
        text_node_properties=[
            NEO4J_CYPHER_EXAMPLES_TEXT_NODE_PROPERTY,
        ],
        embedding_node_property="embedding",
    )
    cypher_example_retriever = cypher_example_index.as_retriever(search_kwargs={"k": 3}) # Reduced k for focused examples
except Exception as e:
    print(f"Warning: Could not initialize Neo4jVector for example queries: {e}")
    print("Proceeding without example query retrieval. Ensure your OpenAI API key is set if using OpenAIEmbeddings.")
    cypher_example_retriever = None


# --- New Prompt Templates for Customer Verification ---

customer_verification_cypher_template = """
Task:
Generate a Cypher query to find a customer in the Neo4j graph database
based on their name. The node label for customer is 'customer'.

Instructions:
Use only the provided relationship types and properties in the schema.
The query should look for a 'customer' node.
The customer's name will be provided in the question. You must use the name from
the question to filter customer nodes. Assume the property for the customer's name
on the 'customer' node is 'name' unless the schema indicates otherwise.
If the schema shows a different property for the customer's name (e.g., 'customerName', 'fullName'),
use that specific property.
Return the customer node or specific properties that help confirm their existence (e.g., name, customerId, or other relevant identifiers).
When filtering on the customer's name, an exact match is preferred, but consider case-insensitivity
if appropriate for your database setup (e.g., using toLower() on both property and input if names are stored in mixed case).

Schema:
{schema}

Relevant Examples (if any retrieved, otherwise this might be empty):
{example_queries}

Note:
Do not include any explanations or apologies in your responses.
Only output the Cypher query.
Do not run any queries that would add to or delete from the database.
Make sure the query returns properties that can be used to confirm the customer's identity.

The question is:
{question}
"""

customer_verification_cypher_prompt = PromptTemplate(
    input_variables=["schema", "example_queries", "question"],
    template=customer_verification_cypher_template,
)

customer_verification_qa_template = """You are an assistant that interprets the results
of a Neo4j Cypher query designed to verify a customer's identity.

The system attempted to verify a customer based on the following input:
{question}

A Cypher query was run and generated these results:
{context}

If the provided information (context) is empty or indicates no records found (e.g., []),
it means the customer was not found. Respond with "Customer not found."

If the query results are not empty, it means a matching customer record was found.
Respond with "Customer verified." and you can list some of the non-sensitive details
returned by the query if available in the context (e.g., customer name or ID).

Helpful Answer:
"""

customer_verification_qa_prompt = PromptTemplate(
    input_variables=["context", "question"], template=customer_verification_qa_template
)

# --- GraphCypherQAChain for Customer Verification ---
# This chain will first generate a Cypher query, then execute it, then formulate an answer.
customer_verification_chain = GraphCypherQAChain.from_llm(
    cypher_llm=ChatOpenAI(model=BANK_CYPHER_MODEL, temperature=0),
    qa_llm=ChatOpenAI(model=BANK_QA_MODEL, temperature=0),
    cypher_example_retriever=cypher_example_retriever, # Can be None if not initialized
    node_properties_to_exclude=["embedding"], # Exclude embedding properties from QA context
    graph=graph,
    verbose=True,
    qa_prompt=customer_verification_qa_prompt,
    cypher_prompt=customer_verification_cypher_prompt,
    validate_cypher=True, # Good practice to validate generated Cypher
    top_k=10, # Max results from graph query for QA
)

# --- Function to Generate Cypher and Optionally Verify Customer ---
def generate_customer_verification_cypher_and_verify(customer_name: str):
    """
    Takes a customer's name, generates a Cypher query to verify their identity,
    and optionally runs the full chain to get a verification message.
    """
    # Frame the question for the LLM to generate the Cypher query
    # It's important that the schema (from graph.refresh_schema()) accurately reflects
    # the 'customer' node and its name property (e.g., 'name', 'customerName').
    question = (
        f"Find and verify customer with the name '{customer_name}'. "
        f"The node label for customers is 'customer'. "
        f"The property for the customer's name on the 'customer' node is likely 'name' or a similar field as per the schema."
    )

    print(f"\nAttempting to generate Cypher for: {customer_name}")

    # 1. Generate the Cypher query using the chain's internal mechanism
    # The generate_query method is part of the base GraphCypherQAChain
    try:
        # Ensure the schema is available to the chain if not implicitly handled well.
        # Typically, the graph object passed during chain initialization handles this.
        # If schema is stale or needs explicit refresh visibility for this call:
        # current_schema = graph.schema
        # (though generate_query in standard Langchain should use the graph schema)

        generated_query = customer_verification_chain.generate_query(question)
        print("\nGenerated Cypher Query:")
        print(generated_query)
    except Exception as e:
        print(f"Error generating Cypher query: {e}")
        generated_query = None

    # 2. Optionally, run the full chain to get the QA result (verification message)
    if generated_query: # Only proceed if query generation was successful
        print("\nRunning full verification chain...")
        try:
            # The invoke method will run the generated_query (or regenerate one)
            # and then pass results to the QA LLM.
            # To ensure *this* specific query is used, one might need to customize the chain
            # or trust its internal query generation from the same question.
            # For this example, we'll re-invoke with the question, assuming it's consistent.
            result = customer_verification_chain.invoke({"query": question})
            print("\nVerification Result (from QA LLM):")
            print(result.get("result", "No result from QA chain."))
            return generated_query, result.get("result")
        except Exception as e:
            print(f"Error running full verification chain: {e}")
            return generated_query, "Error during QA processing."
    else:
        return None, "Could not generate Cypher query."

# --- Main Execution Example ---
if __name__ == "__main__":
    # This is an example of how to use the function.
    # In a real application, customer_name would come from user input or another source.

    # Check if essential components are available
    if not graph.schema or "Failed to load schema" in graph.schema:
        print("Exiting due to Neo4j schema load failure. Please check your Neo4j connection and configuration.")
    elif 'ChatOpenAI' not in globals() or 'OpenAIEmbeddings' not in globals():
        print("Exiting. OpenAI models/embeddings seem unavailable. Ensure langchain_openai is installed and OPENAI_API_KEY is set.")
    else:
        customer_name_to_verify = input("Enter the customer's full name to verify: ")
        if customer_name_to_verify:
            retrieved_cypher_query, verification_message = generate_customer_verification_cypher_and_verify(customer_name_to_verify)
            # The generated_query and verification_message can then be used as needed.
        else:
            print("No customer name provided.")