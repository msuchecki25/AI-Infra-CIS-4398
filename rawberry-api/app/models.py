from typing import Any

from pydantic import BaseModel, Field

#this overall class is used to define the data models for the API, 
# including request and response models for various endpoints.
#this helps with data validation, serialization, and documentation of 
# the API's expected inputs and outputs.

class HealthResponse(BaseModel):
    status: str = "healthy"

# Represents one piece of text ingested by the API.
# In the future, this may represent a document chunk stored in a vector database.
class ItemRecord(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RootResponse(BaseModel):
    message: str
    available_endpoints: list[str]


class GetItemsResponse(BaseModel):
    items: list[ItemRecord]
    count: int

#information about the user's session, gives context
class InstanceData(BaseModel):
    window: int
    agent: str

#push a new query to the AI
class QueryRequest(BaseModel):
    userid: int
    data: InstanceData
    message: str = Field(..., min_length=1)

#whether or not the user's query was received and being processed 0/1/2 received/not received
class QueryResponse(BaseModel):
    status: int

#sees if the chat response has been completed
class ChatRequest(BaseModel):
    userid: int
    data: InstanceData
    message: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    reply: str
    recent_items: list[ItemRecord]


class IngestRequest(BaseModel):
    userid: int
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    message: str
    item: ItemRecord
    count: int

#for signing in (not robust but meets features)
class AuthenticationRequest(BaseModel):
    username: str
    password: str

#conf 0/1 success/fail ... auth 0/1/2 user/admin/other ... userid identifier
class AuthenticationRespone(BaseModel):
    conf: int
    auth: int
    userid: int
