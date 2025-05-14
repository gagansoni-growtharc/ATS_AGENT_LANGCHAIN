from langchain_community.vectorstores.pgvector import PGVector
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

class KnowledgeBaseConfig(BaseModel):
    pg_connection: str = Field(..., description="PostgreSQL connection string")
    collection_name: str = Field(..., description="Vector collection name")
    openai_key: str = Field(..., description="OpenAI API key")

class PDFKnowledgeBase:
    def __init__(self, config: KnowledgeBaseConfig):
        self.vector_store = PGVector(
            connection_string=config.pg_connection,
            embedding_function=OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=config.openai_key
            ),
            collection_name=config.collection_name
        )
        
    def load_documents(self, documents):
        """Store documents in vector database"""
        return self.vector_store.add_documents(documents)