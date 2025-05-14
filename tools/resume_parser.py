# Fix for tools/resume_parser.py

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from pathlib import Path
from typing import Dict, Any, List
import fitz  # PyMuPDF
import logging
from logger.logger import log_error, log_debug, log_warn  # Use your custom logger

logger = logging.getLogger(__name__)

class ResumeProcessInput(BaseModel):
    file_path: str = Field(..., description="Absolute path to resume PDF file")
    extract_metadata: bool = Field(
        default=False, 
        description="Whether to extract metadata from the PDF"
    )

@tool(args_schema=ResumeProcessInput)
def process_resume_pdf(params: Dict[str, Any]) -> Dict[str, Any]:
    """Parse resume PDF and extract text content with optional metadata"""
    try:
        path = Path(params["file_path"])
        if not path.exists():
            log_error("File not found", path=str(path))
            return {"status": "error", "message": "File not found"}
            
        # Validate PDF structure
        with fitz.open(path) as doc:
            if len(doc) == 0:
                log_error("Empty PDF file", path=str(path))
                return {"status": "error", "message": "Empty PDF file"}
            
            text = "\n".join([page.get_text() for page in doc])
            metadata = {}
            
            if params.get("extract_metadata", False):
                metadata = {
                    "author": doc.metadata.get("author", ""),
                    "title": doc.metadata.get("title", ""),
                    "creation_date": doc.metadata.get("creationDate", "")
                }
                log_debug("Extracted PDF metadata", metadata=metadata)

        return {
            "status": "success",
            "content": text,
            "metadata": metadata,
            "file_path": str(path),
            "page_count": len(doc)
        }
        
    except Exception as e:
        log_error("PDF processing failed", error=str(e))
        return {"status": "error", "message": str(e)}

class BatchProcessInput(BaseModel):
    folder_path: str = Field(..., description="Path to directory containing resumes")
    extension: str = Field(
        default="pdf", 
        description="File extension to process"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        description="Number of files to process at once"
    )

@tool(args_schema=BatchProcessInput)
def batch_process_resume_folder(params: Dict[str, Any]) -> Dict[str, Any]:
    """Batch process resumes with progress tracking and error handling"""
    try:
        folder = Path(params["folder_path"])
        if not folder.exists():
            log_error("Folder not found", path=str(folder))
            return {"status": "error", "message": "Folder not found"}
            
        pdf_files = list(folder.glob(f"*.{params.get('extension', 'pdf')}"))
        if not pdf_files:
            log_warn("No PDF files found", path=str(folder))
            return {"status": "error", "message": "No PDF files found"}

        processed = []
        errors = []
        
        batch_size = params.get("batch_size", 100)
        
        for i, pdf_file in enumerate(pdf_files):
            try:
                result = process_resume_pdf({
                    "file_path": str(pdf_file),
                    "extract_metadata": True
                })
                
                if result["status"] == "success":
                    processed.append({
                        "file_name": pdf_file.name,
                        "content_length": len(result["content"]),
                        "metadata": result["metadata"]
                    })
                else:
                    errors.append({
                        "file": str(pdf_file),
                        "error": result["message"]
                    })
                    
                # Batch processing control
                if (i+1) % batch_size == 0:
                    log_debug(f"Processed {i+1}/{len(pdf_files)} files")

            except Exception as e:
                error_msg = f"Failed to process {pdf_file.name}: {str(e)}"
                log_error(error_msg)
                errors.append({"file": str(pdf_file), "error": str(e)})

        return {
            "status": "success",
            "processed": len(processed),
            "errors": len(errors),
            "sample_content": processed[:3],  # Return first 3 for verification
            "error_details": errors if errors else None
        }
        
    except Exception as e:
        log_error("Batch processing failed", error=str(e))
        return {"status": "error", "message": str(e)}

resume_parser_tools = [
    process_resume_pdf,
    batch_process_resume_folder
]

__all__ = ["resume_parser_tools"]