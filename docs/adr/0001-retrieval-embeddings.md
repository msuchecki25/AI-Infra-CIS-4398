# Pin text retrieval to Gemini Embedding 001 at 768 dimensions

Use Vertex AI `gemini-embedding-001` with 768 output dimensions for both source chunks and questions, using the `RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY` task types. This keeps the Google Cloud stack while reducing raw vector storage to one quarter of 3072 dimensions and retaining compatibility with a future standard pgvector HNSW index. Generation remains Gemini 2.5 Flash.

Cloud SQL stores each vector with its model ID; retrieval accepts only the pinned model and dimension and scopes results to the current user in SQL. Changing the model or dimensions requires re-embedding source chunks. Existing vectors are preserved; older chunks without compatible vectors are not returned. Exact cosine search is sufficient for the first sprint; add an ANN index after measuring the corpus.

Reference: [Google text embeddings](https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings), [pgvector indexing limits](https://github.com/pgvector/pgvector#hnsw).
