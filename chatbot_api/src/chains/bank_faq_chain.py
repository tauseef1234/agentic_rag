import os
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain.prompts import (
    PromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
)

from dotenv import load_dotenv
load_dotenv()


BANK_QA_MODEL = os.getenv("BANK_QA_MODEL")

neo4j_vector_index = Neo4jVector.from_existing_graph(
    embedding=OpenAIEmbeddings(),
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
    index_name="faqs",
    node_label="FAQs",
    text_node_properties=[
        "question",
        "answer",
        "related_topics",

    ],
    embedding_node_property="embedding",
)

review_template = """Your job is to use the provided product FAQs 
to answer questions about general mortgage-related queries.Add commentMore actions
Use ONLY the following context to answer questions.
If the answer is not found within the provided context, 
clearly state: "I am sorry, but I cannot find the answer to your question in the provided FAQs." 
Do NOT attempt to provide an answer based on external knowledge.
{context}
"""

review_system_prompt = SystemMessagePromptTemplate(
    prompt=PromptTemplate(input_variables=["context"], template=review_template)
)

review_human_prompt = HumanMessagePromptTemplate(
    prompt=PromptTemplate(input_variables=["question"], template="{question}")
)
messages = [review_system_prompt, review_human_prompt]

faq_prompt = ChatPromptTemplate(
    input_variables=["context", "question"], messages=messages
)

faq_vector_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model=BANK_QA_MODEL, temperature=0),
    chain_type="stuff",
    retriever=neo4j_vector_index.as_retriever(k=12),
)
faq_vector_chain.combine_documents_chain.llm_chain.prompt = faq_prompt
