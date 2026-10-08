import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
import psycopg 
from pgvector.psycopg import register_vector
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from dotenv import load_dotenv




#updated later to fit final format from front end team
def load_documents(doc_path="testdocs"):
    print(f"loading all documents from directory {doc_path}...")

    # check if directory exists
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"The directory {doc_path} does not exist")

    # now we can access directory and load all documents using langchain function
    loader = DirectoryLoader(
        path = doc_path,
        # only focusing on txt files for right now 
        glob = "*.txt",
        loader_cls = TextLoader
    )

    #invoke load method
    documents = loader.load()

    # ensure documents actually contains documents
    if len(documents) == 0:
        raise FileNotFoundError(f"No files found in {doc_path} directory. Add files first.")

    # output checks, shows first 2 docs
    for i, doc in enumerate(documents[:2]):
        print(f"Document{i+1}")
        print(f" Source {doc.metadata['source']}")


def main():
    print("this is the main function")
    #loading documents
    documents = load_documents(doc_path="testdocs")
    #chunking text
    
    #embeddings and store andstore in vector db
main()
# might need this later on
# ensures that this file only runs when it is ran directly not when imported by another file
#if __name__ == "__main__":
#    main()
    


