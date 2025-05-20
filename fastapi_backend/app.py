import os
import shutil
import threading
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import uvicorn
import uuid
from schemas.base import AgentState
from workflows.ats_workflow import ATSWorkflow
from dotenv import load_dotenv
from logger.logger import LogManager, log_info, log_debug, log_error, log_warn
import zipfile
import io
from fastapi.responses import StreamingResponse
from datetime import datetime
import time
# Load environment variables
load_dotenv()

CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))  # Default 24 hours
CLEANUP_FREQUENCY = 3600

# Initialize logger
LogManager().configure(debug=True)

app = FastAPI(title="ATS Resume Screening API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
    expose_headers=["Content-Disposition"]
)

# Class to store job status
class JobStatus:
    def __init__(self):
        self.jobs = {}

    def create_job(self, job_id):
        self.jobs[job_id] = {"status": "pending", "results": None}
        return job_id

    def update_job(self, job_id, status, results=None):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            if results:
                self.jobs[job_id]["results"] = results

    def get_job(self, job_id):
        if job_id in self.jobs:
            return self.jobs[job_id]
        return None

job_status = JobStatus()

# Create temp directories for uploads
TEMP_DIR = Path("temp").absolute()
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Create output directory for filtered resumes
OUTPUT_DIR = Path("./filtered_resumes")
OUTPUT_DIR.mkdir(exist_ok=True)

class ProcessRequest(BaseModel):
    job_id: str
    threshold: float = 75.0

class FolderPathRequest(BaseModel):
    job_id: str
    folder_path: str

class JobResponse(BaseModel):
    job_id: str
    status: str
    results: Optional[Dict[str, Any]] = None

def cleanup_old_directories():
    """Delete directories older than CLEANUP_INTERVAL_HOURS in temp and output folders"""
    current_time = datetime.now().timestamp()
    
    # Clean temp directory
    for job_dir in TEMP_DIR.iterdir():
        if job_dir.is_dir():
            dir_age = current_time - job_dir.stat().st_mtime
            if dir_age > CLEANUP_INTERVAL_HOURS * 3600:
                try:
                    shutil.rmtree(job_dir)
                    print(f"Cleaned temp directory: {job_dir}")
                except Exception as e:
                    print(f"Error cleaning {job_dir}: {str(e)}")

    # Clean output directory
    for job_dir in OUTPUT_DIR.iterdir():
        if job_dir.is_dir():
            dir_age = current_time - job_dir.stat().st_mtime
            if dir_age > CLEANUP_INTERVAL_HOURS * 3600:
                try:
                    shutil.rmtree(job_dir)
                    print(f"Cleaned output directory: {job_dir}")
                except Exception as e:
                    print(f"Error cleaning {job_dir}: {str(e)}")

def run_cleanup_task():
    """Background task to run cleanup periodically"""
    while True:
        cleanup_old_directories()
        time.sleep(CLEANUP_FREQUENCY)

@app.get("/")
async def root():
    return {"message": "ATS Resume Screening API"}

@app.post("/upload/jd", response_model=JobResponse)
async def upload_jd(jd_file: UploadFile = File(...)):
    """Upload a job description file"""
    job_id = str(uuid.uuid4())
    session_id = LogManager.set_session_id(job_id)

    # Create job directories
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize job status
    job_status.create_job(job_id)
    
    try:
        # Save uploaded JD file
        jd_path = job_dir / jd_file.filename
        with open(jd_path, "wb") as f:
            shutil.copyfileobj(jd_file.file, f)
        
        log_info(f"Job description uploaded: {jd_path}", session_id= session_id)
        job_status.update_job(job_id, "jd_uploaded", {"jd_path": str(jd_path)})
        
        return {"job_id": job_id, "status": "jd_uploaded"}
    
    except Exception as e:
        log_error(f"Failed to upload JD: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

# Keep the original method for backward compatibility
@app.post("/upload/resumes", response_model=JobResponse)
async def upload_resumes(job_id: str = Form(...), resumes: List[UploadFile] = File(...)):
    """Upload multiple resume files for processing"""
    job_info = job_status.get_job(job_id)
    session_id = LogManager.set_session_id(job_id)

    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dir = TEMP_DIR / job_id
    resume_dir = job_dir / "resumes"
    resume_dir.mkdir(exist_ok=True)
    
    try:
        uploaded_files = []
        for resume in resumes:
            resume_path = resume_dir / resume.filename
            with open(resume_path, "wb") as f:
                shutil.copyfileobj(resume.file, f)
            uploaded_files.append(str(resume_path))
        
        log_info(f"Uploaded {len(uploaded_files)} resumes for job {job_id}",session_id=session_id)
        job_info["results"] = job_info.get("results", {})
        job_info["results"]["resume_folder"] = str(resume_dir)
        job_info["results"]["resume_count"] = len(uploaded_files)
        job_status.update_job(job_id, "resumes_uploaded", job_info["results"])
        
        return {"job_id": job_id, "status": "resumes_uploaded", "results": job_info["results"]}
    
    except Exception as e:
        log_error(f"Failed to upload resumes: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{job_id}/qualified_resumes")
async def download_qualified_resumes(job_id: str):
    """Download qualified resumes as a zip file"""
    job_info = job_status.get_job(job_id)
    session_id = LogManager.set_session_id(job_id)

    
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job processing not completed")
    
    try:
        results = job_info.get("results", {})
        output_dir = results.get("output_dir")
        
        if not output_dir or not Path(output_dir).exists():
            raise HTTPException(status_code=404, detail="Output directory not found")
        
        # Create a zip file in memory
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            output_path = Path(output_dir)
            for file_path in output_path.glob('*.pdf'):
                # Add file to zip with just the filename (not the full path)
                zip_file.write(file_path, arcname=file_path.name)
        
        # Seek to the beginning of the stream
        zip_io.seek(0)
        
        # Return the zip file as a streaming response
        return StreamingResponse(
            zip_io, 
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=qualified_resumes_{job_id}.zip"}
        )
    
    except Exception as e:
        log_error(f"Failed to create zip file: {str(e)}",session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))

# Add a new endpoint for specifying a folder path instead of uploading files
@app.post("/set/resume_folder", response_model=JobResponse)
async def set_resume_folder(request: FolderPathRequest):
    """Set a folder path for resumes instead of uploading files"""
    job_id = request.job_id
    session_id = LogManager.set_session_id(job_id)

    folder_path = request.folder_path
    
    job_info = job_status.get_job(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Validate that the folder exists
        resume_folder = Path(folder_path)
        if not resume_folder.exists() or not resume_folder.is_dir():
            raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")
        
        # Count resumes (PDF files) in the folder
        resume_files = list(resume_folder.glob("*.pdf"))
        resume_count = len(resume_files)
        
        if resume_count == 0:
            log_warn(f"No PDF files found in folder: {folder_path}",session_id=session_id)
        
        log_info(f"Set resume folder: {folder_path} with {resume_count} PDF files for job {job_id}",session_id=session_id)
        
        # Update job info
        job_info["results"] = job_info.get("results", {})
        job_info["results"]["resume_folder"] = str(resume_folder)
        job_info["results"]["resume_count"] = resume_count
        job_status.update_job(job_id, "resumes_uploaded", job_info["results"])
        
        return {"job_id": job_id, "status": "resumes_uploaded", "results": job_info["results"]}
    
    except Exception as e:
        log_error(f"Failed to set resume folder: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

# Keep the original method for backward compatibility
@app.post("/upload/metadata", response_model=JobResponse)
async def upload_metadata(job_id: str = Form(...), metadata_files: List[UploadFile] = File(...)):
    """Upload metadata files (optional)"""
    job_info = job_status.get_job(job_id)
    session_id = LogManager.set_session_id(job_id)

    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dir = TEMP_DIR / job_id
    metadata_dir = job_dir / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    
    try:
        uploaded_files = []
        for metadata in metadata_files:
            metadata_path = metadata_dir / metadata.filename
            with open(metadata_path, "wb") as f:
                shutil.copyfileobj(metadata.file, f)
            uploaded_files.append(str(metadata_path))
        
        log_info(f"Uploaded {len(uploaded_files)} metadata files for job {job_id}",session_id=session_id)
        job_info["results"] = job_info.get("results", {})
        job_info["results"]["metadata_folder"] = str(metadata_dir)
        job_status.update_job(job_id, "metadata_uploaded", job_info["results"])
        
        return {"job_id": job_id, "status": "metadata_uploaded", "results": job_info["results"]}
    
    except Exception as e:
        log_error(f"Failed to upload metadata: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

# Add a new endpoint for specifying a metadata folder path
@app.post("/set/metadata_folder", response_model=JobResponse)
async def set_metadata_folder(request: FolderPathRequest):
    """Set a folder path for metadata instead of uploading files"""
    job_id = request.job_id
    session_id = LogManager.set_session_id(job_id)

    folder_path = request.folder_path
    
    job_info = job_status.get_job(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Validate that the folder exists
        metadata_folder = Path(folder_path)
        if not metadata_folder.exists() or not metadata_folder.is_dir():
            raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")
        
        # Count metadata files (JSON files) in the folder
        metadata_files = list(metadata_folder.glob("*.json"))
        metadata_count = len(metadata_files)
        
        log_info(f"Set metadata folder: {folder_path} with {metadata_count} JSON files for job {job_id}",session_id=session_id)
        
        # Update job info
        job_info["results"] = job_info.get("results", {})
        job_info["results"]["metadata_folder"] = str(metadata_folder)
        job_status.update_job(job_id, "metadata_uploaded", job_info["results"])
        
        return {"job_id": job_id, "status": "metadata_uploaded", "results": job_info["results"]}
    
    except Exception as e:
        log_error(f"Failed to set metadata folder: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/set/output_dir", response_model=JobResponse)
async def set_output_dir(request: FolderPathRequest):
    """Set a folder path for storing filtered resumes"""
    job_id = request.job_id
    session_id = LogManager.set_session_id(job_id)

    folder_path = request.folder_path
    
    job_info = job_status.get_job(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Validate that the folder exists or create it
        output_folder = Path(folder_path)
        output_folder.mkdir(parents=True, exist_ok=True)
        
        log_info(f"Set output directory: {folder_path} for job {job_id}",session_id=session_id)
        
        # Update job info
        job_info["results"] = job_info.get("results", {})
        job_info["results"]["output_dir"] = str(output_folder)
        job_status.update_job(job_id, job_info["status"], job_info["results"])
        
        return {"job_id": job_id, "status": job_info["status"], "results": job_info["results"]}
    
    except Exception as e:
        log_error(f"Failed to set output directory: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

def process_ats_job(job_id: str, threshold: float):
    """Background task to process ATS job"""
    try:
        job_info = job_status.get_job(job_id)
        session_id = LogManager.set_session_id(job_id)

        if not job_info or not job_info.get("results"):
            log_error(f"Invalid job data for processing: {job_id}",session_id=session_id)
            job_status.update_job(job_id, "error", {"error": "Invalid job data"})
            return
        
        results = job_info["results"]
        job_status.update_job(job_id, "processing")
        
        if "output_dir" in results:
            job_output_dir = Path(results["output_dir"])
        else:
            # Create output directory for this job
            job_output_dir = OUTPUT_DIR / job_id
            job_output_dir.mkdir(exist_ok=True)
        
        # Initialize workflow
        workflow = ATSWorkflow()
        
        # Create initial state
        initial_state = AgentState(
            metadata={
                "resume_folder": results.get("resume_folder"),
                "metadata_folder": results.get("metadata_folder"),
                "jd_path": results.get("jd_path"),
                "score_threshold": threshold,
                "output_dir": str(job_output_dir)
            }
        )
        
        log_info(f"Starting ATS processing for job {job_id}",session_id=session_id)
        result = workflow.invoke(initial_state)
        
        # Update job status with results
        job_status.update_job(job_id, "completed", {
            "scores": result.scores,
            "qualified_count": sum(1 for score in result.scores.values() if score >= threshold),
            "total_count": len(result.scores),
            "output_dir": str(job_output_dir),
            "threshold": threshold,
            "scoring_results": result.metadata.get("scoring_results", [])
        })
        
        log_info(f"Completed ATS processing for job {job_id}",session_id=session_id)
    
    except Exception as e:
        log_error(f"ATS processing failed: {str(e)}",session_id=session_id)
        job_status.update_job(job_id, "error", {"error": str(e)})

@app.post("/process", response_model=JobResponse)
async def process_job(request: ProcessRequest, background_tasks: BackgroundTasks):
    """Start ATS processing job"""
    job_id = request.job_id

    job_info = job_status.get_job(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_info["status"] in ["processing", "completed"]:
        return {"job_id": job_id, "status": job_info["status"], "results": job_info.get("results")}
    
    # Validate required data
    results = job_info.get("results", {})
    if not results.get("jd_path") or not results.get("resume_folder"):
        raise HTTPException(status_code=400, detail="Missing required data (JD or resumes)")
    
    # Start background processing
    background_tasks.add_task(process_ats_job, job_id, request.threshold)
    
    job_status.update_job(job_id, "queued")
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Get current job status"""
    job_info = job_status.get_job(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"job_id": job_id, "status": job_info["status"], "results": job_info.get("results")}


@app.on_event("startup")
def startup_event():
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=run_cleanup_task, daemon=True,name="CleanupThread")
    cleanup_thread.start()
    log_info("Cleanup task started", session_id="SYSTEM")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)