from .base import OpenAIAgent
from schemas.base import AgentState
from tools.file_manager import move_filtered_resumes
from typing import Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Coordinator(OpenAIAgent):
    def __init__(self):
        super().__init__(tools=[move_filtered_resumes])
        
    def process(self, state: AgentState) -> AgentState:
        """Score resumes and move qualified candidates"""
        try:
            if not state.jd_content or not state.resumes:
                logger.error("Missing required data for coordination")
                return state

            # Score resumes using LLM evaluation
            scored_resumes = []
            for resume in state.resumes:
                score = self._calculate_score(resume, state.jd_content)
                scored_resumes.append({
                    "file_path": resume.file_path,
                    "score": score,
                    "metadata": resume.metadata.model_dump() if resume.metadata else None
                })
                
                # Move qualified resumes
                if score > 75:
                    output_dir = state.metadata.get("output_dir", "filtered_resumes")
                    self._move_qualified_resume(resume.file_path, score, output_dir)

            return AgentState(
                **state.model_dump(),
                scores={r["file_path"]: r["score"] for r in scored_resumes},
                metadata={
                    **state.metadata,
                    "scoring_results": scored_resumes
                }
            )

        except Exception as e:
            logger.error(f"Coordination failed: {str(e)}")
            return state

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
            """
            
            response = self.llm.invoke(prompt)
            return self._parse_score_from_response(response.content)
        except Exception as e:
            logger.error(f"Score calculation failed: {str(e)}")
            return 0.0

    def _parse_score_from_response(self, response_text: str) -> float:
        """Extract numerical score from LLM response"""
        try:
            return float(response_text.strip().split()[-1])
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