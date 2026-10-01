from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
import psycopg 
from pgvector.psycopg import register_vector
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv


def main():
    print("this is the main function")


#loading documents
#updated later to fit final format from front end team
def load_documents(doc_path'"testdocs"):
    print(f"loading all documents from directory {doc_path}...")
    
#chunking text
#embeddings and store andstore in vector db

