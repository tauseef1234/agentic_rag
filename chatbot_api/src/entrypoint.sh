#!/bin/bash

# Run any setup steps or pre-processing tasks here
echo "Starting Banking System Chatbot RAG FastAPI service..."

# NEW: Run FAQ embedding indexing script
echo "Running FAQ vector indexer..."
python scripts/index_faqs.py

# Start the main application
uvicorn main:app --host 0.0.0.0 --port 8000
