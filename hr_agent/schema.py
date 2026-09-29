from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import date

class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['answered', 'not_in_policy', 'pending_approval', 'applied', 'rejected']
    answer: str
    citations: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)

class LeaveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: date
    end: date

    @model_validator(mode='after')
    def ordered(self):
        if self.end < self.start or (self.end - self.start).days > 31:
            raise ValueError('Use an ordered date range of at most 32 calendar days.')
        return self
