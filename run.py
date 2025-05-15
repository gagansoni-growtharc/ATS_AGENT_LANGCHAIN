import subprocess
import os
import time
import threading
import signal
import sys

def run_fastapi():
    print("Starting FastAPI server...")
    fastapi_process = subprocess.Popen(
        ["uvicorn", "fastapi_backend.app:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return fastapi_process

def run_streamlit():
    print("Starting Streamlit server...")
    streamlit_process = subprocess.Popen(
        ["streamlit", "run", "streamlit_frontend/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return streamlit_process

def log_output(process, name):
    for line in iter(process.stdout.readline, ""):
        if line:
            print(f"[{name}] {line.strip()}")

def main():
    # Start FastAPI server
    fastapi_process = run_fastapi()
    fastapi_logger = threading.Thread(target=log_output, args=(fastapi_process, "FastAPI"))
    fastapi_logger.daemon = True
    fastapi_logger.start()
    
    # Give FastAPI time to start
    time.sleep(2)
    
    # Start Streamlit server
    streamlit_process = run_streamlit()
    streamlit_logger = threading.Thread(target=log_output, args=(streamlit_process, "Streamlit"))
    streamlit_logger.daemon = True
    streamlit_logger.start()
    
    def signal_handler(sig, frame):
        print("\nShutting down servers...")
        fastapi_process.terminate()
        streamlit_process.terminate()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print("\nServers are running!")
        print("- FastAPI: http://localhost:8000")
        print("- Streamlit: http://localhost:8501")
        print("\nPress Ctrl+C to stop")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        fastapi_process.terminate()
        streamlit_process.terminate()

if __name__ == "__main__":
    main()