from pydantic import BaseModel
from typing import Optional

class BankQueryInput(BaseModel):
    input: str
    customer_id: Optional[str] = None
    role: Optional[str] = None  

class BankQueryOutput(BaseModel):
    output: str
    intermediate_steps: list[str]
