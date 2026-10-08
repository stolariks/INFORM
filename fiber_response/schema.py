from pydantic import BaseModel
from typing import List

class ComputeRequest(BaseModel):
    amplitudes: List[float] = None

