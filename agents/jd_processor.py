from .base import OpenAIAgent
from tools.jd_parser import parse_job_description_content
from schemas.jd import JDParsingInput
from schemas.base import AgentState
import logging

logger = logging.getLogger(__name__)

class JDProcessor(OpenAIAgent):
    def __init__(self):
        super().__init__(tools=[parse_job_description_content])
        
    def process(self, state: AgentState) -> AgentState:
        try:
            jd_path = state.metadata.get("jd_path")
            with open(jd_path, "r") as f:
                jd_content = f.read()
                
            parsed = parse_job_description_content({
                "jd_content": jd_content,
                "parse_mode": "full"
            })
            
            return AgentState(
                **state.model_dump(),
                jd_content=jd_content,
                metadata={
                    **state.metadata,
                    "parsed_jd": parsed
                }
            )
        except Exception as e:
            logger.error(f"JD processing failed: {str(e)}")
            return state