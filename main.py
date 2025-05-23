import argparse
from config.settings import get_settings
from workflows.ats_workflow import ATSWorkflow
from schemas.base import AgentState
from logger import LogManager, log_debug, log_info, log_warn
import dotenv
dotenv.load_dotenv()

def main():
    # Load settings
    settings = get_settings()
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="ATS Resume Filtering System")
    parser.add_argument("--folder", required=True, help="Path to resumes folder")
    parser.add_argument("--jd", required=True, help="Path to job description file")
    parser.add_argument("--metadata", help="Path to metadata folder")
    parser.add_argument("--threshold", type=float, default=75.0, 
                        help="Score threshold for selecting qualified resumes (0-100)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Configure logger
    LogManager().configure(debug=args.debug)
    log_info("Starting ATS System", version="1.0")

    threshold = max(0.0, min(100.0, args.threshold))
    if threshold != args.threshold:
        log_warn(f"Threshold value adjusted to valid range: {threshold}")
    if args.debug:
        log_debug("Debug mode enabled", settings=settings.model_dump())

    # Initialize workflow
    workflow = ATSWorkflow()

    # Create initial state
    initial_state = AgentState(
        metadata={
            "resume_folder": args.folder,
            "metadata_folder": args.metadata,
            "jd_path": args.jd,
            "score_threshold": threshold,
            "settings": settings.model_dump()
        }
    )

    # Execute workflow
    result = workflow.invoke(initial_state)
    print("Final scores:", result.scores)

if __name__ == "__main__":
    main()