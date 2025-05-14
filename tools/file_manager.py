# Fix for tools/file_manager.py - move_filtered_resumes function

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from pathlib import Path
import fitz  # PyMuPDF
import shutil
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# This is the corrected version of the move_filtered_resumes function
# It now accepts a dictionary rather than expecting a FileMoveInput object

@tool
def move_filtered_resumes(params: Dict[str, Any]) -> Dict[str, Any]:
    """Move resumes with score-based filename to destination directory"""
    try:
        source_path = Path(params["source"])
        dest_dir = Path(params["dest"])
        score = params["score"]
        create_dirs = params.get("create_dirs", True)
        
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
        shutil.move(str(source_path), str(dest_path))
        
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