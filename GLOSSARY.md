# RAWBerry document retrieval

RAWBerry answers questions using documents uploaded by the current user.

## Language

**Source document**: A file uploaded by a user as reference material for answers. Conversation messages are history rather than source documents.

**Chunk**: A passage taken from a source document, retaining its document identity and available page location.

**Embedding**: A numeric representation of a chunk or question that supports matching passages by meaning.

**Vector store**: The collection of stored chunk embeddings used to find passages relevant to a question.

**Retrieval result**: A matching chunk, its source identity, and a similarity score. Similarity measures the match to a question, not answer truthfulness.
