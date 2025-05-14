from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import tool
import re
import logging
from typing import Dict, List, Any
from logger.logger import log_error, log_warn  # Use custom logger

logger = logging.getLogger(__name__)

COMMON_SKILLS = [
    "Python", "Java", "JavaScript", "SQL", "AWS",
    "Docker", "Kubernetes", "Machine Learning", "React",
    "TensorFlow", "PyTorch", "Azure", "GCP", "Node.js"
]

class JDParsingInput(BaseModel):
    jd_content: str = Field(..., description="Raw job description text")
    parse_mode: str = Field(
        default="full",
        description="Detail level: full, skills, or responsibilities"
    )

    @field_validator('parse_mode')
    def validate_parse_mode(cls, v):
        allowed = ["full", "skills", "responsibilities"]
        if v not in allowed:
            raise ValueError(f"Invalid parse_mode. Allowed: {allowed}")
        return v

class JDParsingResult(BaseModel):
    job_title: str
    required_skills: Dict[str, int]
    responsibilities: List[str]
    qualifications: List[str]
    parse_mode: str

@tool(args_schema=JDParsingInput)
def parse_job_description_content(params: JDParsingInput) -> Dict[str, Any]:
    """Parse job descriptions into structured data with skill requirements"""
    try:
        text = params.jd_content
        result = {
            "job_title": "Undefined Role",
            "required_skills": {},
            "responsibilities": [],
            "qualifications": [],
            "parse_mode": params.parse_mode
        }

        # 1. Extract Job Title
        title_patterns = [
            r"^#?\s*(Job Title|Position|Role):?\s*([^\n]+)",
            r"^(.*?)\s+-\s+(?:Job|Position|Role)",
            r"([A-Z][a-z]+)\s+Developer(?:\s+\(.*\))?"
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["job_title"] = match.group(-1).strip()
                break
        else:
            first_line = text.strip().split('\n')[0]
            if len(first_line) < 100:
                result["job_title"] = first_line

        # 2. Extract Skills with Experience
        skill_patterns = [
            r"(\w+(?:\s+\w+)*)\s*:\s*(\d+\+?)",
            r"(\d+\+?)\s+years?\s+of\s+([\w\s]+)",
            r"Expertise in (.*?)\s?\((.*?)\)"
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    skill, years = match[::-1] if match[0].isdigit() else match
                    skill = skill.strip().title()
                    try:
                        years = int(years.replace('+', '')) if years else 1
                    except ValueError:
                        years = 1
                        
                    if skill not in result["required_skills"] or years > result["required_skills"][skill]:
                        result["required_skills"][skill] = years

        # Fallback to common skills
        if not result["required_skills"]:
            for skill in COMMON_SKILLS:
                if re.search(rf'\b{re.escape(skill)}\b', text, re.IGNORECASE):
                    result["required_skills"][skill] = 1

        # 3. Extract Responsibilities & Qualifications
        section_patterns = {
            "responsibilities": (
                r'(Responsibilities|Duties):?\s*([\s\S]*?)(?=(?:Requirements|Qualifications|$))',
                r'(?:•|\*|\-|\d+\.)\s*(.*)'
            ),
            "qualifications": (
                r'(Requirements|Qualifications):?\s*([\s\S]*?)(?=(?:Benefits|Compensation|$))',
                r'(?:•|\*|\-|\d+\.)\s*(.*)'
            )
        }

        for section, (section_re, item_re) in section_patterns.items():
            section_match = re.search(section_re, text, re.IGNORECASE)
            if section_match:
                content = section_match.group(2)
                items = re.findall(item_re, content)
                result[section] = [item.strip() for item in items if item.strip()]

        # Handle parse modes
        if params.parse_mode != "full":
            filtered_result = {}
            if params.parse_mode == "skills":
                filtered_result = {"required_skills": result["required_skills"]}
            elif params.parse_mode == "responsibilities":
                filtered_result = {
                    "responsibilities": result["responsibilities"],
                    "qualifications": result["qualifications"]
                }
            
            return {
                "status": "success",
                "result": JDParsingResult(**{**filtered_result, "parse_mode": params.parse_mode}).model_dump(),
                "parse_mode": params.parse_mode
            }

        # Validate and return full result
        parsed_result = JDParsingResult(**result)
        return {
            "status": "success",
            "result": parsed_result.model_dump(),
            "parse_mode": params.parse_mode
        }

    except Exception as e:
        log_error("JD parsing failed", error=str(e), jd_snippet=text[:100])
        return {
            "status": "error",
            "message": f"JD parsing failed: {str(e)}",
            "parse_mode": params.parse_mode
        }

jd_parser_tools = [parse_job_description_content]
__all__ = ["jd_parser_tools"]