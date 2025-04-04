# Update package list and install Ghostscript
apt-get update && apt-get install -y ghostscript

# (Optional) Print Ghostscript version to verify
gs --version

# Start your FastAPI app
uvicorn main:app --host=0.0.0.0 --port=$PORT