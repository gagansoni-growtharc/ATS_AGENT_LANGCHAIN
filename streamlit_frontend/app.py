import streamlit as st
import requests
import time
import pandas as pd
import json
import os
from pathlib import Path
import tempfile

# Set page configuration
st.set_page_config(
    page_title="ATS Resume Screening System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API endpoints
API_URL = "http://localhost:8000"

# Session state initialization
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "job_status" not in st.session_state:
    st.session_state.job_status = None
if "processing_started" not in st.session_state:
    st.session_state.processing_started = False
if "results" not in st.session_state:
    st.session_state.results = None

# Sidebar
st.sidebar.title("ATS Resume Screening")
st.sidebar.markdown("---")

# Main content
st.title("📄 ATS Resume Screening System")
st.markdown("Upload a job description and resumes to get AI-powered resume screening results.")

# Create tabs for workflow
tab1, tab2, tab3 = st.tabs(["Upload Files", "Process", "Results"])

with tab1:
    st.header("Step 1: Upload Job Description & Resumes")
    
    # Upload Job Description
    st.subheader("Upload Job Description")
    jd_file = st.file_uploader("Upload Job Description (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
    
    # Upload Resumes
    st.subheader("Upload Resumes")
    resume_files = st.file_uploader("Upload Resumes (PDF format recommended)", type=["pdf"], accept_multiple_files=True)
    
    # Optional: Upload Metadata
    st.subheader("Optional: Upload Metadata")
    st.markdown("Upload JSON files with metadata for resumes. File names should match resume names.")
    metadata_files = st.file_uploader("Upload Metadata (JSON)", type=["json"], accept_multiple_files=True)
    
    # Upload button
    if st.button("Upload Files", key="upload_btn"):
        if not jd_file:
            st.error("Please upload a job description file.")
        elif not resume_files:
            st.error("Please upload at least one resume file.")
        else:
            with st.spinner("Uploading files..."):
                try:
                    # Step 1: Upload JD
                    jd_response = requests.post(
                        f"{API_URL}/upload/jd",
                        files={"jd_file": (jd_file.name, jd_file.getvalue(), "application/octet-stream")}
                    )
                    jd_response.raise_for_status()
                    job_id = jd_response.json()["job_id"]
                    st.session_state.job_id = job_id
                    
                    # Step 2: Upload Resumes
                    resume_files_dict = {
                        f"resumes": [(file.name, file.getvalue(), "application/octet-stream") for file in resume_files]
                    }
                    resume_response = requests.post(
                        f"{API_URL}/upload/resumes",
                        data={"job_id": job_id},
                        files=resume_files_dict
                    )
                    resume_response.raise_for_status()
                    
                    # Step 3: Upload Metadata (optional)
                    if metadata_files:
                        metadata_files_dict = {
                            f"metadata_files": [(file.name, file.getvalue(), "application/json") for file in metadata_files]
                        }
                        metadata_response = requests.post(
                            f"{API_URL}/upload/metadata",
                            data={"job_id": job_id},
                            files=metadata_files_dict
                        )
                        metadata_response.raise_for_status()
                    
                    st.session_state.job_status = "uploaded"
                    st.success(f"Files uploaded successfully! Job ID: {job_id}")
                    st.session_state.processing_started = False
                    
                except Exception as e:
                    st.error(f"Error uploading files: {str(e)}")

with tab2:
    st.header("Step 2: Process Resumes")
    
    if st.session_state.job_id and st.session_state.job_status == "uploaded":
        st.info(f"Job ID: {st.session_state.job_id}")
        
        # Scoring threshold
        threshold = st.slider(
            "Score Threshold for Qualified Resumes (0-100)", 
            min_value=0.0, 
            max_value=100.0, 
            value=75.0, 
            step=5.0
        )
        
        # Process button
        if st.button("Start Processing", key="process_btn"):
            try:
                with st.spinner("Processing resumes..."):
                    # Start processing
                    process_response = requests.post(
                        f"{API_URL}/process",
                        json={"job_id": st.session_state.job_id, "threshold": threshold}
                    )
                    process_response.raise_for_status()
                    
                    # Update status
                    st.session_state.job_status = "processing"
                    st.session_state.processing_started = True
            except Exception as e:
                st.error(f"Error starting processing: {str(e)}")
    
    # Status checking
    if st.session_state.job_id and st.session_state.processing_started:
        status_placeholder = st.empty()
        
        # Auto-refresh status
        try:
            status_response = requests.get(f"{API_URL}/status/{st.session_state.job_id}")
            status_response.raise_for_status()
            status_data = status_response.json()
            
            st.session_state.job_status = status_data["status"]
            
            if status_data["status"] == "completed":
                st.session_state.results = status_data["results"]
                status_placeholder.success("Processing completed!")
            elif status_data["status"] == "error":
                error_msg = status_data.get("results", {}).get("error", "Unknown error")
                status_placeholder.error(f"Processing failed: {error_msg}")
            else:
                status_placeholder.info(f"Status: {status_data['status'].upper()}")
                
                # Only display this if not completed
                if status_data["status"] != "completed":
                    st.button("Refresh Status", key="refresh_status")
                    
        except Exception as e:
            st.error(f"Error checking status: {str(e)}")
    
    # Display if no job started yet
    if not st.session_state.job_id:
        st.warning("Please upload files in the first tab to start processing.")

with tab3:
    st.header("Step 3: View Results")
    
    if st.session_state.job_status == "completed" and st.session_state.results:
        results = st.session_state.results
        
        # Display summary
        st.subheader("Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Resumes", results.get("total_count", 0))
        with col2:
            st.metric("Qualified Resumes", results.get("qualified_count", 0))
        with col3:
            st.metric("Score Threshold", f"{results.get('threshold', 75.0)}%")
        
        # Create DataFrame from results
        if "scoring_results" in results:
            scoring_data = results["scoring_results"]
            
            # Convert to DataFrame
            df = pd.DataFrame(scoring_data)
            
            # Add basic filename extraction
            df["filename"] = df["file_path"].apply(lambda x: Path(x).name)
            
            # Reorder columns
            columns = ["filename", "score", "qualified"]
            if "metadata" in df.columns:
                columns.append("metadata")
            columns.append("file_path")
            
            df = df[columns]
            
            # Sort by score (descending)
            df = df.sort_values("score", ascending=False)
            
            # Style the DataFrame
            st.subheader("Detailed Results")
            
            # Use custom formatting for better display
            def format_row(row):
                if row["qualified"]:
                    return ["background-color: rgba(0, 200, 0, 0.2)"] * len(row)
                else:
                    return [""] * len(row)
            
            # Format metadata column if present
            if "metadata" in df.columns:
                df["metadata"] = df["metadata"].apply(lambda x: json.dumps(x) if x else "None")
            
            # Apply styling and display
            styled_df = df.style.apply(format_row, axis=1)
            st.dataframe(styled_df, use_container_width=True)
            
            # Download button for results
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name="ats_results.csv",
                mime="text/csv",
            )
            
        else:
            st.info("No detailed scoring results available.")
    else:
        st.info("Complete the processing step to view results here.")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("ATS Resume Screening System v1.0")