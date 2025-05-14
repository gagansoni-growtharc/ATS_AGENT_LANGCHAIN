from pydantic import BaseModel, Field
from typing import Optional, Dict, List

class ResumeMetadata(BaseModel):
    experience_years: Optional[Dict[str, float]] = Field(
        None, 
        description="Key-value pairs of skills with years of experience"
    )
    certifications: Optional[List[str]] = Field(
        None,
        description="List of professional certifications"
    )

class ResumeContent(BaseModel):
    text: str = Field(..., description="Extracted resume text")
    file_path: str = Field(..., description="Original file path")
    metadata: Optional[ResumeMetadata] = Field(
        None,
        description="Optional structured metadata"
    )