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
st.markdown("Upload a job description and provide folder paths to get AI-powered resume screening results.")

# Create tabs for workflow
tab1, tab2, tab3 = st.tabs(["Upload Files", "Process", "Results"])

with tab1:
    st.header("Step 1: Upload Job Description & Provide Paths")
    
    # Upload Job Description
    st.subheader("Upload Job Description")
    jd_file = st.file_uploader("Upload Job Description (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
    
    # Resume Folder Path
    st.subheader("Resume Folder Path")
    resume_folder = st.text_input(
        "Enter the folder path containing all resumes (PDF format recommended)",
        help="Provide the full path to the folder containing your resume files"
    )
    
    # Metadata Folder Path
    st.subheader("Optional: Metadata Folder Path")
    metadata_folder = st.text_input(
        "Enter the folder path containing metadata files (JSON)",
        help="Provide the full path to the folder containing your metadata JSON files. File names should match resume names."
    )
    
    # Output Directory Path
    st.subheader("Output Directory Path")
    output_dir = st.text_input(
        "Enter the folder path where qualified resumes should be saved",
        value="./filtered_resumes",
        help="Provide the full path to the folder where qualified resumes will be copied. The folder will be created if it doesn't exist."
    )
    
    # Submit button
    if st.button("Submit Paths", key="submit_paths_btn"):
        if not jd_file:
            st.error("Please upload a job description file.")
        elif not resume_folder:
            st.error("Please enter a resume folder path.")
        else:
            with st.spinner("Processing paths..."):
                try:
                    # Step 1: Upload JD
                    jd_response = requests.post(
                        f"{API_URL}/upload/jd",
                        files={"jd_file": (jd_file.name, jd_file.getvalue(), "application/octet-stream")}
                    )
                    jd_response.raise_for_status()
                    job_id = jd_response.json()["job_id"]
                    st.session_state.job_id = job_id
                    
                    # Step 2: Set Resume Folder
                    resume_folder_response = requests.post(
                        f"{API_URL}/set/resume_folder",
                        json={"job_id": job_id, "folder_path": resume_folder}
                    )
                    resume_folder_response.raise_for_status()
                    
                    # Step 3: Set Metadata Folder (optional)
                    if metadata_folder:
                        metadata_folder_response = requests.post(
                            f"{API_URL}/set/metadata_folder",
                            json={"job_id": job_id, "folder_path": metadata_folder}
                        )
                        metadata_folder_response.raise_for_status()
                    
                    # Step 4: Set Output Directory
                    output_dir_response = requests.post(
                        f"{API_URL}/set/output_dir",
                        json={"job_id": job_id, "folder_path": output_dir}
                    )
                    output_dir_response.raise_for_status()
                    
                    st.session_state.job_status = "uploaded"
                    st.success(f"Paths processed successfully! Job ID: {job_id}")
                    st.session_state.processing_started = False
                    
                except Exception as e:
                    st.error(f"Error processing paths: {str(e)}")

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
        st.warning("Please provide paths in the first tab to start processing.")

with tab3:
    st.header("Step 3: View Results")
    
    if st.session_state.job_status == "completed" and st.session_state.results:
        results = st.session_state.results
        
        # Display summary
        st.subheader("Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Resumes", results.get("total_count", 0))
        with col2:
            st.metric("Qualified Resumes", results.get("qualified_count", 0))
        with col3:
            st.metric("Score Threshold", f"{results.get('threshold', 75.0)}%")
        
        # Display output directory
        output_dir = results.get("output_dir", "")
        if output_dir:
            with col4:
                st.metric("Output Directory", str(Path(output_dir).name))
            
            # Add a button to open the output directory
            if os.path.exists(output_dir):
                st.success(f"✅ Qualified resumes have been copied to: {output_dir}")
                if st.button("Open Output Directory"):
                    # This won't work in cloud deployment, but works in local setup
                    try:
                        import webbrowser
                        output_path = Path(output_dir).resolve()
                        webbrowser.open(f"file://{output_path}")
                    except Exception as e:
                        st.error(f"Could not open directory: {str(e)}")
            else:
                st.warning(f"⚠️ Output directory not found: {output_dir}")
        
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