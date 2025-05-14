from pydantic import BaseModel, Field
from langchain_core.tools import tool
from pathlib import Path
import fitz  # PyMuPDF
import shutil
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# --------------------------
# List Files Tool
# --------------------------
class ListFilesInput(BaseModel):
    folder_path: str = Field(..., description="Path to directory")
    extension: str = Field("pdf", description="File extension filter")

@tool(args_schema=ListFilesInput)
def list_resume_files(params: ListFilesInput) -> Dict[str, Any]:
    """List files in directory with specified extension"""
    try:
        folder = Path(params.folder_path)
        if not folder.exists():
            return {"status": "error", "message": f"Directory not found: {params.folder_path}"}
            
        files = list(folder.glob(f"*.{params.extension}"))
        return {
            "status": "success",
            "files": [str(file) for file in files],
            "count": len(files)
        }
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return {"status": "error", "message": str(e)}

# --------------------------
# Move File Tool (Generic)
# --------------------------
class MoveFileInput(BaseModel):
    source_path: str = Field(..., description="Source file path")
    destination_path: str = Field(..., description="Destination path")
    create_dirs: bool = Field(True, description="Create missing directories")

@tool(args_schema=MoveFileInput)
def move_file(params: MoveFileInput) -> Dict[str, Any]:
    """Move file from source to destination"""
    try:
        source = Path(params.source_path)
        dest = Path(params.destination_path)
        
        if not source.exists():
            return {"status": "error", "message": "Source file not found"}
            
        if params.create_dirs:
            dest.parent.mkdir(parents=True, exist_ok=True)
            
        shutil.move(str(source), str(dest))
        return {"status": "success", "source": str(source), "destination": str(dest)}
    except Exception as e:
        logger.error(f"Error moving file: {str(e)}")
        return {"status": "error", "message": str(e)}

# --------------------------
# Copy File Tool
# --------------------------
class CopyFileInput(BaseModel):
    source_path: str = Field(..., description="Source file path")
    destination_path: str = Field(..., description="Destination path")
    create_dirs: bool = Field(True, description="Create missing directories")

@tool(args_schema=CopyFileInput)
def copy_file(params: CopyFileInput) -> Dict[str, Any]:
    """Copy file to destination"""
    try:
        source = Path(params.source_path)
        dest = Path(params.destination_path)
        
        if not source.exists():
            return {"status": "error", "message": "Source file not found"}
            
        if params.create_dirs:
            dest.parent.mkdir(parents=True, exist_ok=True)
            
        shutil.copy2(source, dest)
        return {"status": "success", "source": str(source), "destination": str(dest)}
    except Exception as e:
        logger.error(f"Error copying file: {str(e)}")
        return {"status": "error", "message": str(e)}

# --------------------------
# Rename File Tool
# --------------------------
class RenameFileInput(BaseModel):
    file_path: str = Field(..., description="Path to file")
    new_name: str = Field(..., description="New filename")

@tool(args_schema=RenameFileInput)
def rename_file(params: RenameFileInput) -> Dict[str, Any]:
    """Rename a file"""
    try:
        path = Path(params.file_path)
        if not path.exists():
            return {"status": "error", "message": "File not found"}
            
        new_path = path.parent / params.new_name
        path.rename(new_path)
        return {"status": "success", "original": str(path), "new": str(new_path)}
    except Exception as e:
        logger.error(f"Error renaming file: {str(e)}")
        return {"status": "error", "message": str(e)}

# --------------------------
# Create Directory Tool
# --------------------------
class CreateDirInput(BaseModel):
    dir_path: str = Field(..., description="Path of directory to create")

@tool(args_schema=CreateDirInput)
def create_directory(params: CreateDirInput) -> Dict[str, Any]:
    """Create directory structure"""
    try:
        path = Path(params.dir_path)
        path.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "path": str(path)}
    except Exception as e:
        logger.error(f"Error creating directory: {str(e)}")
        return {"status": "error", "message": str(e)}

# --------------------------
# Filtered Resume Move Tool (Special Case)
# --------------------------
class FileMoveInput(BaseModel):
    source: str = Field(..., description="Source file path")
    dest: str = Field(..., description="Destination directory")
    score: float = Field(..., description="Score for filename formatting")
    create_dirs: bool = Field(True, description="Create missing directories")

@tool(args_schema=FileMoveInput)
def move_filtered_resumes(params: FileMoveInput) -> Dict[str, Any]:
    """Move resumes with score-based filename to destination directory"""
    try:
        source_path = Path(params.source)
        dest_dir = Path(params.dest)
        
        # Validate PDF using PyMuPDF
        with fitz.open(source_path) as doc:
            if len(doc) == 0:
                return {"status": "error", "message": "Empty PDF file"}
        
        # Create directories if needed
        if params.create_dirs:
            dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Format destination filename
        score_str = f"{params.score:.1f}".replace('.', '_')
        dest_path = dest_dir / f"{score_str}_{source_path.name}"
        
        # Perform the move operation
        shutil.move(str(source_path), str(dest_path))
        
        return {
            "status": "success",
            "source": str(source_path),
            "destination": str(dest_path),
            "score": params.score
        }
    except Exception as e:
        logger.error(f"File move error: {str(e)}")
        return {"status": "error", "message": str(e)}

# Export all tools
file_manager_tools = [
    list_resume_files,
    move_file,
    copy_file,
    rename_file,
    create_directory,
    move_filtered_resumes
]

__all__ = ["file_manager_tools"]