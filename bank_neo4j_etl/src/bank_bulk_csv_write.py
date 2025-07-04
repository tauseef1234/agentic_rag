import os
import logging
from retry import retry
from neo4j import GraphDatabase

# ✅ [NEW] Debug print to verify variables are loaded
print("Using NEO4J_URI:", os.getenv("NEO4J_URI"))
# print("Using NEO4J_USERNAME:", os.getenv("NEO4J_USERNAME"))
# print("Using NEO4J_PASSWORD:", os.getenv("NEO4J_PASSWORD"))

# # Paths to CSV files containing hospital data
BRANCHES_CSV_PATH = os.getenv("BRANCHES_CSV_PATH")
MORTGAGE_CSV_PATH = os.getenv("MORTGAGE_CSV_PATH")
CUSTOMER_CSV_PATH = os.getenv("CUSTOMER_CSV_PATH")
PAYMENTS_MADE_CSV_PATH = os.getenv("PAYMENTS_MADE_CSV_PATH")
PAYMENTS_DUE_CSV_PATH = os.getenv("PAYMENTS_DUE_CSV_PATH")
FEES_CSV_PATH = os.getenv("FEES_CSV_PATH")
FAQS_CSV_PATH = os.getenv("FAQS_CSV_PATH")
EXAMPLE_CYPHER_CSV_PATH = os.getenv("EXAMPLE_CYPHER_CSV_PATH")


# Neo4j config
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Configure the logging module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


LOGGER = logging.getLogger(__name__)

NODES = ["Branch", "Customer", "Mortgage", "Question"]


def _set_uniqueness_constraints(tx, node):
    query = f"""CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node})
        REQUIRE n.id IS UNIQUE;"""
    _ = tx.run(query, {})


@retry(tries=100, delay=10)
def load_bank_graph_from_csv() -> None:
    """Load structured bank CSV data following
    a specific ontology into Neo4j"""

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    # Add a step to clear the database before loading new data
    LOGGER.info("Clearing existing graph data...")
    with driver.session(database="neo4j") as session:
        session.run("MATCH (n) DETACH DELETE n;")
    LOGGER.info("Existing graph data cleared.")

    LOGGER.info("Setting uniqueness constraints on nodes")
    with driver.session(database="neo4j") as session:
        for node in NODES:
            session.execute_write(_set_uniqueness_constraints, node)

    # Load Branch nodes
    LOGGER.info("Loading branch nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{BRANCHES_CSV_PATH}' AS branches
        MERGE (h:Branch {{id: toInteger(branches.branch_id)}})
        SET
            h.name = branches.branch_name,
            h.state_name = branches.branch_state;
        """
        session.run(query, {})

    # Load Customer nodes
    LOGGER.info("Loading customer nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{CUSTOMER_CSV_PATH}' AS customers
        MERGE (p:Customer {{id: customers.customer_id}})
        SET
            p.first_name = customers.first_name,
            p.last_name = customers.last_name,
            p.name = customers.first_name + ' ' + customers.last_name,
            p.email = customers.email,
            p.phone_number = customers.phone_number,
            p.address = customers.address,
            p.city = customers.city,
            p.state = customers.state,
            p.zip_code = customers.zip_code,
            p.country = customers.country;
        """
        session.run(query, {})

    # Load Mortgage nodes
    LOGGER.info("Loading mortgage nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{MORTGAGE_CSV_PATH}' AS mortgage
        MERGE (p:Mortgage {{id: mortgage.loan_number}})
        SET
            p.loan_number = mortgage.loan_number,
            p.amount = toFloat(mortgage.loan_amount),
            p.interest = toFloat(mortgage.interest_rate),
            p.start = mortgage.start_date,
            p.status = mortgage.status,
            p.tenure = mortgage.tenure,
            p.customer_id = mortgage.customer_id;

        """
        session.run(query, {})


    LOGGER.info("Loading payments nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{PAYMENTS_MADE_CSV_PATH}' AS payments
        MERGE (p:Payments {{id: payments.payment_made_id}})
        SET
            p.amount = toFloat(payments.amount),
            p.payment_date = payments.payment_date,
            p.customer_id = payments.customer_id;
        """
        session.run(query, {})
    # Load Payments Due nodes
    LOGGER.info("Loading PaymentsDue nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{PAYMENTS_DUE_CSV_PATH}' AS payments_due
        MERGE (pd:PaymentsDue {{id: payments_due.payment_due_id}})
        SET
            pd.amount = toFloat(payments_due.amount),
            pd.due_date = payments_due.due_date,
            pd.status = payments_due.status,
            pd.customer_id = payments_due.customer_id,
            pd.mortgage_id = payments_due.mortgage_id;

        """
        session.run(query, {})

    # Load Fees nodes
    LOGGER.info("Loading Fees nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{FEES_CSV_PATH}' AS fees
        MERGE (f:Fees {{id: fees.fee_id}})
        SET
            f.type = fees.fee_type,
            f.amount = toFloat(fees.amount),
            f.date_incurred = fees.date_incurred,
            f.status = fees.status,
            f.customer_id = fees.customer_id,
            f.mortgage_id = fees.mortgage_id;
        """
        session.run(query, {})

    # add FAQs
    LOGGER.info("Loading FAQs nodes (assuming a simple structure)")
    # Note: No specific CSV for FAQs was provided, so this assumes a basic structure.
    # You would need to create a 'faqs.csv' file with 'faq_id', 'question', 'answer' columns.
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{FAQS_CSV_PATH}' AS faqs
        MERGE (q:FAQs {{id: faqs.faq_id,
                        question: faqs.question,
                        answer: faqs.answer,
                        topics: faqs.related_topics
                        }});
        """
        session.run(query, {})     

    LOGGER.info("Loading question nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{EXAMPLE_CYPHER_CSV_PATH}' AS questions
        MERGE (Q:Question {{
                         question: questions.question,
                         cypher: questions.cypher
                        }});
        """
        _ = session.run(query, {})

    LOGGER.info("Creating HAS relationships between Customer and Mortgage nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{MORTGAGE_CSV_PATH}' AS mortgage
        MATCH (c:Customer {{id: mortgage.customer_id}})
        MATCH (m:Mortgage {{id: mortgage.loan_number}})
        MERGE (c)-[:HAS]->(m);
        """
        _ = session.run(query, {})

    LOGGER.info("Creating MADE relationships between customer and payments")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{PAYMENTS_MADE_CSV_PATH}' AS payments
        MATCH (c:Customer {{id: payments.customer_id}})
        MATCH (p:Payments {{id: payments.payment_made_id}})
        MERGE (c)-[:MADE]->(p);
        """
        session.run(query, {})

    LOGGER.info("Creating SCHEDULE relationships between mortgage and payments due")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{PAYMENTS_DUE_CSV_PATH}' AS payments_due
        MATCH (m:Mortgage {{id: payments_due.mortgage_id}})
        MATCH (pd:PaymentsDue {{id: payments_due.payment_due_id}})
        MERGE (m)-[:SCHEDULE]->(pd);
        """
        session.run(query, {})

    LOGGER.info("Creating HAS relationships between mortgage and fees nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{FEES_CSV_PATH}' AS fees
        MATCH (m:Mortgage {{id: fees.mortgage_id}})
        MATCH (f:Fees {{id: fees.fee_id}})
        MERGE (m)-[:HAS]->(f);
        """
        session.run(query, {})

    LOGGER.info("Creating MAY INCUR relationships between mortgage and fees nodes")
    with driver.session(database="neo4j") as session:
        query = f"""
        LOAD CSV WITH HEADERS
        FROM '{FEES_CSV_PATH}' AS fees
        MATCH (pd:PaymentsDue {{customer_id: fees.customer_id, mortgage_id: fees.mortgage_id}})
        MATCH (f:Fees {{id: fees.fee_id}})
        WHERE fees.status = 'Due' // Assuming fees are incurred when payment is due and status is 'Due'
        MERGE (pd)-[:MAY_INCUR]->(f);
        """
        # NOTE: This query assumes `payments_due` nodes have `customer_id` and `mortgage_id` properties
        # which they do based on the CSV. It also assumes `fees.csv` has these IDs for linking.
        session.run(query, {})


if __name__ == "__main__":
    load_bank_graph_from_csv()
