from pydantic import BaseModel

class AgentResponse(BaseModel):
    answer: str
    final_offer: bool
