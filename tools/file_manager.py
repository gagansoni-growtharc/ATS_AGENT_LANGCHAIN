from pydantic import BaseModel, Field
from langchain_core.tools import tool
from pathlib import Path
import fitz  # PyMuPDF
import shutil
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class FileMoveInput(BaseModel):
    """Schema for move_filtered_resumes input parameters"""
    source: str = Field(..., description="Source file path")
    dest: str = Field(..., description="Destination directory")
    score: float = Field(..., description="Resume score")
    create_dirs: bool = Field(default=True, description="Create directories if needed")

@tool(args_schema=FileMoveInput)
def move_filtered_resumes(source: str, dest: str, score: float, create_dirs: bool = True) -> Dict[str, Any]:
    """Move resumes with score-based filename to destination directory"""
    try:
            
        # Create validated input object
        validated_input = FileMoveInput(
            source=source,
            dest=dest,
            score=score,
            create_dirs=create_dirs
        )
        
        source_path = Path(validated_input.source)
        dest_dir = Path(dest)
        score = score
        create_dirs = create_dirs
        
        # Validate PDF using PyMuPDF
        with fitz.open(source_path) as doc:
            if len(doc) == 0:
                return {"status": "error", "message": "Empty PDF file"}
        
        # Create directories if needed
        if create_dirs:
            dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Format destination filename
        score_str = f"{score:.1f}".replace('.', '_')
        dest_path = dest_dir / f"{score_str}_{source_path.name}"
        
        # Perform the move operation
        shutil.copy2(str(source_path), str(dest_path))
        
        return {
            "status": "success",
            "source": str(source_path),
            "destination": str(dest_path),
            "score": score
        }
    except Exception as e:
        logger.error(f"File move error: {str(e)}")
        return {"status": "error", "message": str(e)}

# Export all tools
file_manager_tools = [
    move_filtered_resumes
]

__all__ = ["file_manager_tools"]