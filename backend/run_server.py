#!/usr/bin/env python
"""Start the FastAPI server with error handling"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import uvicorn
    from main import app
    
    print("Starting server on http://127.0.0.1:8000")
    print("Press Ctrl+C to stop")
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
except Exception as e:
    print(f"Error starting server: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

