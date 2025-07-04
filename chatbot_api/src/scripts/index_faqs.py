import os
import logging
import pandas as pd
from dotenv import load_dotenv
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Configuration ---
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FAQS_CSV_PATH = os.getenv("FAQS_CSV_PATH", "./data/faqs.csv") # Default path if not set

def clear_existing_faqs():
    """
    Connects to Neo4j and deletes all nodes with the 'FAQs' label to prevent
    the ConstraintError on subsequent runs.
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session(database="neo4j") as session:
            logger.info("Clearing all existing FAQ nodes from the database...")
            # This Cypher query finds all FAQ nodes and removes them and their relationships
            session.run("MATCH (n:FAQs) DETACH DELETE n")
            logger.info("Successfully cleared existing FAQ nodes.")
        driver.close()
    except Exception as e:
        logger.error(f"Failed to clear existing FAQs from Neo4j. Error: {e}")
        # We raise the exception to stop the script if we can't clear the DB
        raise e

def index_faqs():
    """
    Reads the FAQ CSV file and indexes the questions and answers into a
    Neo4j vector store for Retrieval-Augmented Generation (RAG).
    """
    if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, OPENAI_API_KEY]):
        logger.error("Missing required environment variables. Please check your .env file.")
        return

    # --- Step 1: Clear existing data (The Fix) ---
    clear_existing_faqs()

    # --- Step 2: Read the corrected CSV file ---
    logger.info(f"Reading FAQ data from {FAQS_CSV_PATH}")
    try:
        # Use pandas to read the CSV, which is robust
        df = pd.read_csv(FAQS_CSV_PATH, quotechar='"', skip_blank_lines=True)
        # Ensure the required columns exist
        required_columns = ['question', 'answer']
        if not all(col in df.columns for col in required_columns):
            logger.error(f"CSV file must contain the following columns: {required_columns}")
            return
    except FileNotFoundError:
        logger.error(f"The FAQ file was not found at path: {FAQS_CSV_PATH}")
        return
    except Exception as e:
        logger.error(f"Failed to read or parse the CSV file. Error: {e}")
        return

    # --- Step 3: Create LangChain Document objects ---
    # We combine the question and answer for better semantic search results.
    # The 'metadata' holds the original fields for reference.
    documents = []
    for _, row in df.iterrows():
        doc = Document(
            page_content=f"Question: {row['question']}\nAnswer: {row['answer']}",
            metadata={
                'faq_id': str(row.get('faq_id', '')),
                'question': row['question'],
                'answer': row['answer'],
                'related_topics': str(row.get('related_topics', ''))
            }
        )
        documents.append(doc)

    logger.info(f"Prepared {len(documents)} documents for indexing.")

    # --- Step 4: Index documents into Neo4jVector ---
    logger.info("Starting indexing process into Neo4jVector...")
    try:
        # This command connects to OpenAI to create embeddings and then saves
        # them to your Neo4j database.
        _ = Neo4jVector.from_documents(
            documents=documents,
            embedding=OpenAIEmbeddings(),
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            index_name="faqs",          # Name of the vector index in Neo4j
            node_label="FAQs",          # Label for the nodes created in Neo4j
            embedding_node_property="embedding", # Property to store the vector
        )
        logger.info("Successfully indexed all FAQs into Neo4j.")
    except Exception as e:
        logger.error(f"An error occurred during the Neo4jVector indexing process. Error: {e}")
        logger.error("Please check your Neo4j credentials, OpenAI API key, and network connection.")

if __name__ == "__main__":
    index_faqs()

