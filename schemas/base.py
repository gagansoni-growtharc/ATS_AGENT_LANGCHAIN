from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class AgentState(BaseModel):
    jd_content: Optional[str] = Field(None, description="Job description content")
    resumes: List[Dict[str, Any]] = Field(default_factory=list, description="Processed resumes")
    scores: Dict[str, float] = Field(default_factory=dict, description="Resume scores")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="System metadata")

class BaseToolInput(BaseModel):
    params: Dict[str, Any]