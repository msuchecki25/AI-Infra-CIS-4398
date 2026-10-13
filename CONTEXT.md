# RAG Retrieval

This context describes the language used to find relevant material in the project's uploaded school files.

## Language

**Document**:
A user-uploaded source file in the knowledge corpus.
_Avoid_: Source, resource

**Chunk**:
A text segment derived from a Document and treated as one searchable unit.
_Avoid_: Passage, section

**Query**:
Text expressing the information a user wants to find in the corpus.
_Avoid_: Prompt, question

**Retrieval Result**:
A Chunk matched to a Query, including its Document identity and a normalized similarity score.
_Avoid_: Search result, hit
