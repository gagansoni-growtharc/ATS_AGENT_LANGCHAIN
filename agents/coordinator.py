from .base import OpenAIAgent
from schemas.base import AgentState
from tools.file_manager import move_filtered_resumes
from typing import Dict, Any
from logger.logger import log_info, log_debug, log_warn, log_error
from pathlib import Path
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain.agents.output_parsers import JSONAgentOutputParser
import re
import json
class Coordinator(OpenAIAgent):
    def __init__(self):
        log_info("Initializing Coordinator agent")
        try:
            # Initialize LLM with timeout
            llm = ChatGroq(
                api_key="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",
                model="llama3-70b-8192", 
                temperature=0,
                request_timeout=30
            )
            
            # Setup and validate tools
            tools = [move_filtered_resumes]
            log_debug(f"Loaded tools: {[t.name for t in tools]}")

            # Create prompt template
            prompt = self.create_prompt(tools)
            
            # Initialize LLM chain
            llm_chain = LLMChain(llm=llm, prompt=prompt)
            
            # Create output parser
            output_parser = JSONAgentOutputParser()
            
            # Initialize parent class
            super().__init__(
                llm_chain=llm_chain,
                allowed_tools=[t.name for t in tools],
                tools=tools,
                output_parser=output_parser
            )
            
            self._llm = llm
            log_info("Coordinator initialization completed")

        except Exception as e:
            log_error("Coordinator initialization failed", error=str(e))
            raise

    def create_prompt(self, tools) -> PromptTemplate:
        log_debug("Creating evaluation prompt template")
        return PromptTemplate(
            template="""
            You are a professional resume evaluation system. Analyze the resume against 
            the job requirements and provide a numerical score from 0-100 following these rules:
            
            1. Base score (0-60) on technical skills match
            2. Add bonus (0-20) for relevant experience duration
            3. Add bonus (0-20) for certifications/education
            4. Final score must be between 0-100
            
            Format response as: "Score: [NUMBER]/100"
            
            Job Requirements:
            {jd_content}
            
            Resume Content:
            {resume_content}
            
            Agent Scratchpad: {agent_scratchpad}
            """,
            input_variables=["jd_content", "resume_content", "agent_scratchpad"]
        )
    
    @property
    def llm_prefix(self) -> str:
        return "Thought:"
    
    @property
    def observation_prefix(self) -> str:
        return "Observation:"
        
    def process(self, state: AgentState) -> AgentState:
        """Score resumes and move qualified candidates"""
        log_info("Starting coordination process")
        try:
            # Validate input state
            if not state.jd_content or not state.resumes:
                log_error("Missing required data for coordination",
                         jd_present=bool(state.jd_content),
                         resumes_count=len(state.resumes) if state.resumes else 0)
                return state.copy(update={"scores": {}})

            log_info(f"Processing {len(state.resumes)} resumes")

            scores_dict = {}
            processed_count = 0
            error_count = 0

            for resume in state.resumes:
                try:
                    log_debug(f"Scoring resume: {resume.file_path}")
                    score = self._calculate_score(resume, state.jd_content)
                    log_debug(f"score: {score}")
                    scores_dict[resume.file_path] = score
                    processed_count += 1

                    # Move qualified resumes
                    if score > 75:
                        output_dir = state.metadata.get("output_dir", "filtered_resumes")
                        log_info(f"Moving qualified resume: {resume.file_path} (Score: {score})")
                        self._move_qualified_resume(resume.file_path, score, output_dir)

                except Exception as e:
                    error_count += 1
                    log_error("Resume processing failed", 
                             resume=resume.file_path,
                             error=str(e))

            log_info(f"Processed {processed_count} resumes, {error_count} errors")
            log_info(f"Generated scores {scores_dict}")

            return state.model_copy(update={
                "scores": scores_dict,
                "metadata": {
                    **state.metadata,
                    "scoring_results": [{
                        "file_path": resume.file_path,
                        "score": score,
                        "metadata": resume.metadata if resume.metadata else None
                    } for resume, score in zip(state.resumes, scores_dict.values())]
                }
            })

        except Exception as e:
            log_error("Coordination process failed", error=str(e))
            return state.copy(update={"scores": {}})

    def _calculate_score(self, resume, jd_content: str) -> float:
        """Calculate resume score using LLM evaluation"""
        try:
            log_debug(f"Generating score for: {resume.file_path}")
            
            prompt = f"""
            JOB REQUIREMENTS:
            {jd_content}
            
            RESUME CONTENT:
            {resume.text}
            
            METADATA:
            {json.dumps(resume.metadata, indent=2) if resume.metadata else "No metadata"}
            
            FINAL SCORE (0-100):
            """

            log_debug(f"Scoring prompt:\n{prompt}...")
            response = self._llm.invoke(prompt)
            log_debug(f"LLM response: {response.content}...")
            
            score = self._parse_score_from_response(response.content)
            log_info(f"Resume scored: {resume.file_path} - {score}/100")
            
            return score

        except Exception as e:
            log_error("Score calculation failed", 
                     resume=resume.file_path,
                     error=str(e))
            return 0.0

    def _parse_score_from_response(self, response_text: str) -> float:
        """Enhanced score parsing with multiple fallback patterns"""
        try:
            # Try multiple patterns to extract score
            patterns = [
                r"Score:\s*(\d{1,3})/100",  # Explicit score format
                r"\bFinal Score:\s*(\d{1,3})\b",
                r"\b(\d{1,3})\s*out of 100\b",
                r"\b(\d{1,3})\s*/\s*100\b",
                r"\b(\d{1,3})\b(?!.*\d)"  # Last number in response
            ]

            for pattern in patterns:
                match = re.search(pattern, response_text)
                if match:
                    score = float(match.group(1))
                    score = max(0, min(100, score))
                    log_debug(f"Parsed score {score} using pattern: {pattern}")
                    return score

            log_warn("No valid score found in response", 
                     response=response_text[:200])
            return 0.0

        except Exception as e:
            log_error("Score parsing failed", 
                     response=response_text[:200],
                     error=str(e))
            return 0.0

    def _move_qualified_resume(self, file_path: str, score: float, output_dir: str = "filtered_resumes"):
        """Move qualified resume with enhanced error handling"""
        try:
            log_info(f"Attempting to move resume: {file_path} to {output_dir}")
            
            result = move_filtered_resumes.invoke({
                "source": file_path,
                "dest": output_dir,
                "score": score,
                "create_dirs": True
            })

            if result["status"] == "success":
                log_info(f"Moved resume successfully: {file_path}")
            else:
                log_error("Failed to move resume", 
                         file=file_path,
                         error=result.get("message"))

        except Exception as e:
            log_error("Resume move operation failed", 
                     file=file_path,
                     error=str(e))