from pydantic import BaseModel, Field

class JDParsingInput(BaseModel):
    jd_content: str = Field(..., description="Raw job description content")
    parse_mode: str = Field(
        "full",
        enum=["full", "skills", "responsibilities"],
        description="Level of detail to extract"
    )