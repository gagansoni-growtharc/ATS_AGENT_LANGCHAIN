from pydantic import BaseModel, Field, field_validator, ValidationError
from langchain_core.tools import tool
import re
from typing import Dict, List, Any
from collections import defaultdict
from logger.logger import log_error, log_warn, log_debug, log_info

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
            log_error("Invalid parse_mode", 
                     attempted_value=v, 
                     allowed_values=allowed,
                     stack_trace=True)
            raise ValueError(f"Invalid parse_mode. Allowed: {allowed}")
        return v

class JDParsingResult(BaseModel):
    job_title: str = "Undefined Role"
    required_skills: Dict[str, int] = Field(default_factory=dict)
    mentioned_terms: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    tech_stack: Dict[str, List[str]] = Field(default_factory=dict)
    parse_mode: str

def clean_text(text: str) -> str:
    """Normalize text for reliable parsing with detailed logging"""
    log_info("Starting text normalization")
    log_debug(f"Input text length: {len(text)} characters")
    
    replacements = {
        '\uf0b7': '-', '\u2022': '-', '\u25cf': '-', '\u200b': '',
        '\u2013': '-', '\u2014': '--', '\u2018': "'", '\u2019': "'"
    }
    
    for old, new in replacements.items():
        original_count = text.count(old)
        if original_count > 0:
            text = text.replace(old, new)
            log_debug(f"Replaced {original_count} instances of {hex(ord(old))} with '{new}'")
    
    cleaned = re.sub(r'\s+', ' ', text).strip()
    log_info(f"Text cleaning completed. Final length: {len(cleaned)} characters")
    log_debug(f"Cleaned text sample: {cleaned[:200]}...")
    return cleaned

def split_sections(text: str) -> Dict[str, str]:
    """Split JD into sections with detailed section logging"""
    log_info("Starting section segmentation")
    sections = {}
    headers = [
        "JOB TITLE:", "LOCATION:", "EMPLOYMENT TYPE:", "COMPANY DESCRIPTION:",
        "KEY RESPONSIBILITIES:", "REQUIRED QUALIFICATIONS:", "PREFERRED SKILLS:",
        "TECH STACK:", "BENEFITS:", "HOW TO APPLY:"
    ]
    pattern = r"(?P<header>" + "|".join(re.escape(h) for h in headers) + r")"

    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    log_debug(f"Found {len(matches)} section headers in JD")
    
    expected_headers = {h.strip().rstrip(":").lower() for h in headers}
    found_headers = set()

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        header = match.group("header").strip().rstrip(":").lower()
        content = text[start:end].strip()
        sections[header] = content
        found_headers.add(header)
        log_debug(f"Section '{header}' extracted ({len(content)} characters)")

    # Log missing sections
    missing_sections = expected_headers - found_headers
    if missing_sections:
        log_warn(f"Missing expected sections: {', '.join(missing_sections)}")
    
    log_info(f"Section segmentation completed. Found {len(sections)} sections")
    return sections

def parse_section_from_text(text: str) -> List[str]:
    """Parse section content with item-level logging"""
    log_info("Parsing section content")
    lines = text.splitlines()
    items = []
    log_debug(f"Processing {len(lines)} lines in section")
    
    for idx, line in enumerate(lines, 1):
        line_clean = line.strip()
        if line_clean.startswith(('-', '•')):
            clean_item = re.sub(r'^[-•]\s*', '', line_clean)
            items.append(clean_item)
            log_debug(f"Line {idx}: Found list item - {clean_item[:50]}...")
        elif line_clean:
            items.append(line_clean)
            log_debug(f"Line {idx}: Found text block - {line_clean[:50]}...")
    
    log_info(f"Section parsing completed. Found {len(items)} items")
    return items

def extract_tech_stack(text: str) -> Dict[str, List[str]]:
    """Extract tech stack with detailed component logging"""
    log_info("Starting tech stack extraction")
    tech_stack = defaultdict(list)
    category_pattern = re.compile(r'(backend|frontend|devops):\s*(.+)', re.IGNORECASE)
    lines = text.splitlines()
    current_category = None
    log_debug(f"Processing {len(lines)} tech stack lines")

    for line_num, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean:
            continue

        if cat_match := category_pattern.match(line_clean):
            current_category = cat_match.group(1).lower()
            items = [t.strip() for t in cat_match.group(2).split(',')]
            tech_stack[current_category].extend(items)
            log_info(f"Line {line_num}: Found {current_category} category with {len(items)} items")
            log_debug(f"{current_category} items: {', '.join(items)}")
            continue

        if current_category and line_clean.startswith('-'):
            items = [t.strip() for t in line_clean[1:].split(',')]
            tech_stack[current_category].extend(items)
            log_debug(f"Line {line_num}: Added {len(items)} items to {current_category}")
    
    log_info(f"Tech stack extraction completed. Found {sum(len(v) for v in tech_stack.values())} total items")
    return dict(tech_stack)

@tool(args_schema=JDParsingInput)
def parse_job_description_content(jd_content: str, parse_mode: str = "full") -> Dict[str, Any]:
    """Parse job descriptions into structured data with comprehensive logging"""
    log_info("Starting JD parsing workflow", parse_mode=parse_mode)
    try:
        log_debug("Initializing parsing context")
        text = clean_text(jd_content)
        sections = split_sections(text)
        
        result = {
            "job_title": sections.get("job title", "Undefined Role").strip(),
            "required_skills": defaultdict(int),
            "mentioned_terms": [],
            "responsibilities": parse_section_from_text(sections.get("key responsibilities", "")),
            "qualifications": parse_section_from_text(sections.get("required qualifications", "")),
            "tech_stack": extract_tech_stack(sections.get("tech stack", "")),
            "parse_mode": parse_mode
        }
        
        log_info("Job title extracted", job_title=result["job_title"])
        log_debug(f"Initial parsing results: {result}")

        log_info("Starting skill extraction process")
        skill_pattern = re.compile(
            r'\b('
            r'python|java|javascript|typescript|go|rust|c\+\+|c#|ruby|php|scala|swift|'
            r'tensorflow|keras|pytorch|scikit-learn|xgboost|lightgbm|'
            r'numpy|pandas|matplotlib|seaborn|plotly|dash|streamlit|'
            r'sql|nosql|mysql|postgresql|mongodb|redis|'
            r'aws|azure|gcp|docker|kubernetes|terraform|ansible|jenkins|'
            r'git|github|gitlab|bitbucket|'
            r'nlp|llm|transformers|bert|gpt|huggingface|'
            r'computer vision|opencv|cnn|rnn|gan|'
            r'linux|bash|shell|'
            r'react|angular|vue|svelte|next\.js|node\.js|express|flask|django'
            r')\b',
            re.IGNORECASE
        )


        skill_counts = defaultdict(int)
        for qual in result["qualifications"]:
            if matches := skill_pattern.findall(qual.lower()):
                for skill in set(matches):
                    skill_counts[skill] += 1
                    result["required_skills"][skill.title()] = 0
                    log_debug(f"Skill match: {skill.title()} in qualification '{qual[:50]}...'")

        log_info(f"Identified {len(skill_counts)} unique skills in qualifications")
        log_debug(f"Skill frequency: {dict(skill_counts)}")
        
        result["mentioned_terms"] = list(result["required_skills"].keys())
        log_info("Finalizing parsed results")
        
        log_debug("Starting Pydantic validation")
        parsed_result = JDParsingResult(**result)
        log_info("Validation succeeded")
        
        log_info("JD parsing completed successfully")
        log_debug("Final output structure", 
                 job_title=parsed_result.job_title,
                 skills_count=len(parsed_result.required_skills),
                 responsibilities_count=len(parsed_result.responsibilities),
                 tech_stack_categories=list(parsed_result.tech_stack.keys()))
        
        return {
            "status": "success",
            "result": parsed_result.model_dump(),
            "parse_mode": parse_mode
        }

    except ValidationError as e:
        log_error("Validation failed", 
                 errors=e.errors(), 
                 input_data=result,
                 stack_trace=True)
        return {
            "status": "error",
            "message": f"Validation failed: {e.errors()}",
            "parse_mode": parse_mode
        }
    except Exception as e:
        log_error("Critical parsing failure", 
                 error=str(e), 
                 stack_trace=True,
                 parse_mode=parse_mode,
                 jd_sample=jd_content[:200])
        return {
            "status": "error",
            "message": f"JD parsing failed: {str(e)}",
            "parse_mode": parse_mode
        }

jd_parser_tools = [parse_job_description_content]
__all__ = ["jd_parser_tools"]