from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool
from pathlib import Path
from typing import Dict, Any
import json
import logging
from schemas.resume import ResumeMetadata

logger = logging.getLogger(__name__)

class MetadataFindInput(BaseModel):
    resume_name: str = Field(
        ..., 
        description="Resume filename without extension",
        example="john_doe_resume"
    )
    metadata_folder: str = Field(
        ..., 
        description="Path to metadata directory",
        example="./metadata"
    )

@tool(args_schema=MetadataFindInput)
def find_matching_metadata(resume_name: str, metadata_folder: str) -> Dict[str, Any]:
    """Locate metadata JSON file associated with a resume"""
    try:
        meta_dir = Path(metadata_folder)
        
        # Validate metadata directory
        if not meta_dir.exists():
            return {
                "status": "error",
                "message": f"Metadata directory not found: {metadata_folder}"
            }
            
        if not meta_dir.is_dir():
            return {
                "status": "error",
                "message": f"Path is not a directory: {metadata_folder}"
            }

        meta_path = meta_dir / f"{resume_name}.json"
        
        return {
            "status": "success",
            "exists": meta_path.exists(),
            "path": str(meta_path) if meta_path.exists() else None,
            "resume_name": resume_name
        }
        
    except Exception as e:
        logger.error(f"Metadata search failed: {str(e)}", extra={
            "resume": resume_name,
            "metadata_dir": metadata_folder
        })
        return {
            "status": "error",
            "message": f"Metadata search error: {str(e)}",
            "resume": resume_name
        }

class MetadataLoadInput(BaseModel):
    metadata_path: str = Field(
        ..., 
        description="Full path to metadata JSON file",
        example="./metadata/john_doe_resume.json"
    )

@tool(args_schema=MetadataLoadInput)
def load_metadata(metadata_path: str) -> Dict[str, Any]:
    """Load and validate resume metadata from JSON file"""
    try:
        meta_path = Path(metadata_path)

        # File existence check
        if not meta_path.exists():
            return {
                "status": "error",
                "message": f"Metadata file not found: {metadata_path}"
            }

        if not meta_path.is_file():
            return {
                "status": "error",
                "message": f"Path is not a file: {metadata_path}"
            }

        # Read raw JSON
        with open(meta_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

            return {
                "status": "success",
                "metadata": raw_data,
                "path": metadata_path
            }

    except Exception as e:
            logger.error(f"Metadata loading failed: {str(e)}", extra={
                "path": metadata_path
            })
            return {
                "status": "error",
                "message": f"Metadata load error: {str(e)}",
                "path": metadata_path
            }

# Export tools
metadata_tools = [find_matching_metadata, load_metadata]
__all__ = ["metadata_tools"]