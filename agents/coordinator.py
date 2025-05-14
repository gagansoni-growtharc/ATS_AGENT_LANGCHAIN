# Fix for agents/coordinator.py

from .base import OpenAIAgent
from schemas.base import AgentState
from tools.file_manager import move_filtered_resumes
from typing import Dict, Any
import logging
from pathlib import Path
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain.agents.output_parsers import JSONAgentOutputParser

logger = logging.getLogger(__name__)

class Coordinator(OpenAIAgent):
    def __init__(self):
        # Initialize LLM
        llm = ChatGroq(api_key="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",model="llama3-70b-8192", temperature=0)

        
        # Setup tools
        tools = [move_filtered_resumes]
        
        # Create prompt
        prompt = self.create_prompt(tools)
        
        # Initialize LLM chain
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        
        # Create output parser
        output_parser = JSONAgentOutputParser()
        
        # Call parent constructor
        super().__init__(
            llm_chain=llm_chain,
            allowed_tools=[tool.name for tool in tools],
            tools=tools,
            output_parser=output_parser
        )
        
        # Store LLM for direct usage
        self._llm = llm
        
    def create_prompt(self, tools) -> PromptTemplate:
        return PromptTemplate(
            template="""
            You are a resume evaluation assistant. Analyze the resume against the job requirements 
            and provide a numerical score from 0-100.
            
            Job Requirements:
            {jd_content}
            
            Resume:
            {resume_content}
            
            Score (0-100):
            Agent Scratchpad :{agent_scratchpad}
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
        try:
            if not state.jd_content or not state.resumes:
                logger.error("Missing required data for coordination")
                # Initialize with empty scores to prevent AttributeError later
                # Fix: Create a proper copy of the state and add scores
                state_dict = state.model_dump()
                state_dict["scores"] = {}  # Add empty scores dict
                return AgentState(**state_dict)

            # Score resumes using LLM evaluation
            scored_resumes = []
            scores_dict = {}  # Separate dictionary for final scores
            
            for resume in state.resumes:
                score = self._calculate_score(resume, state.jd_content)
                scores_dict[resume.file_path] = score  # Add to scores dictionary
                
                scored_resumes.append({
                    "file_path": resume.file_path,
                    "score": score,
                    "metadata": resume.metadata.model_dump() if resume.metadata else None
                })
                
                # Move qualified resumes
                if score > 75:
                    output_dir = state.metadata.get("output_dir", "filtered_resumes")
                    self._move_qualified_resume(resume.file_path, score, output_dir)

            # Build updated state with scores in both places
            # Fix: Create a properly structured copy avoiding double-scores
            state_dict = state.model_dump()
            state_dict["scores"] = scores_dict  # Add scores dict
            state_dict["metadata"] = {
                **state.metadata,
                "scoring_results": scored_resumes
            }
            return AgentState(**state_dict)

        except Exception as e:
            logger.error(f"Coordination failed: {str(e)}")
            # Return state with empty scores to prevent AttributeError
            # Fix: Create a proper copy of the state and add scores
            state_dict = state.model_dump()
            state_dict["scores"] = {}  # Add empty scores dict
            return AgentState(**state_dict)

    def _calculate_score(self, resume, jd_content: str) -> float:
        """Calculate resume score using LLM evaluation"""
        try:
            prompt = f"""
            Job Requirements:
            {jd_content}

            Resume Content:
            {resume.text}

            Metadata:
            {resume.metadata.model_dump() if resume.metadata else "No metadata"}
            
            On a scale of 0-100, score how well this resume matches the job requirements.
            Provide only the numerical score.
            """
            
            response = self._llm.invoke(prompt)
            return self._parse_score_from_response(response.content)
        except Exception as e:
            logger.error(f"Score calculation failed: {str(e)}")
            return 0.0

    def _parse_score_from_response(self, response_text: str) -> float:
        """Extract numerical score from LLM response"""
        try:
            # Look for any number in the response
            import re
            numbers = re.findall(r'\d+', response_text)
            if numbers:
                score = float(numbers[0])
                # Ensure score is within 0-100 range
                return max(0, min(100, score))
            return 0.0
        except (IndexError, ValueError):
            logger.warning("Failed to parse score from LLM response")
            return 0.0

    def _move_qualified_resume(self, file_path: str, score: float, output_dir: str = "filtered_resumes"):
        """Move qualified resume to filtered directory"""
        try:
            move_filtered_resumes.invoke({
                "source": file_path,
                "dest": output_dir,
                "score": score
            })
        except Exception as e:
            logger.error(f"Failed to move resume {file_path}: {str(e)}")