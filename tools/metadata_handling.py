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
def find_matching_metadata(params: MetadataFindInput) -> Dict[str, Any]:
    """Locate metadata JSON file associated with a resume"""
    try:
        meta_dir = Path(params.metadata_folder)
        
        # Validate metadata directory
        if not meta_dir.exists():
            return {
                "status": "error",
                "message": f"Metadata directory not found: {params.metadata_folder}"
            }
            
        if not meta_dir.is_dir():
            return {
                "status": "error",
                "message": f"Path is not a directory: {params.metadata_folder}"
            }

        meta_path = meta_dir / f"{params.resume_name}.json"
        
        return {
            "status": "success",
            "exists": meta_path.exists(),
            "path": str(meta_path) if meta_path.exists() else None,
            "resume_name": params.resume_name
        }
        
    except Exception as e:
        logger.error(f"Metadata search failed: {str(e)}", extra={
            "resume": params.resume_name,
            "metadata_dir": params.metadata_folder
        })
        return {
            "status": "error",
            "message": f"Metadata search error: {str(e)}",
            "resume": params.resume_name
        }

class MetadataLoadInput(BaseModel):
    metadata_path: str = Field(
        ..., 
        description="Full path to metadata JSON file",
        example="./metadata/john_doe_resume.json"
    )

@tool(args_schema=MetadataLoadInput)
def load_metadata(params: MetadataLoadInput) -> Dict[str, Any]:
    """Load and validate resume metadata from JSON file"""
    try:
        meta_path = Path(params.metadata_path)
        
        # File existence check
        if not meta_path.exists():
            return {
                "status": "error",
                "message": f"Metadata file not found: {params.metadata_path}"
            }
            
        if not meta_path.is_file():
            return {
                "status": "error",
                "message": f"Path is not a file: {params.metadata_path}"
            }

        # Read and validate
        with open(meta_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        validated = ResumeMetadata.model_validate(raw_data)
        
        return {
            "status": "success",
            "metadata": validated.model_dump(),
            "path": params.metadata_path
        }
        
    except ValidationError as e:
        logger.error("Metadata validation failed", extra={
            "path": params.metadata_path,
            "errors": e.errors()
        })
        return {
            "status": "error",
            "message": "Metadata validation failed",
            "errors": e.errors(),
            "path": params.metadata_path
        }
        
    except Exception as e:
        logger.error(f"Metadata loading failed: {str(e)}", extra={
            "path": params.metadata_path
        })
        return {
            "status": "error",
            "message": f"Metadata load error: {str(e)}",
            "path": params.metadata_path
        }

# Export tools
metadata_tools = [find_matching_metadata, load_metadata]
__all__ = ["metadata_tools"]