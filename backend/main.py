"""
Minimal FastAPI backend for netlist parsing.
Uses the exact parsing functions from FYP.ipynb via netlist_parser.py
"""
import os
import json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the exact parsing functions from the notebook
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from netlist_parser import build_netlist_graph, graph_to_json

app = FastAPI(title="Netlist Builder API")

# Enable CORS for frontend - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Ensure output directory exists
OUTPUT_DIR = Path(__file__).parent.parent / "out"
OUTPUT_DIR.mkdir(exist_ok=True)


@app.post("/api/netlist")
async def parse_netlist(
    files: List[UploadFile] = File(...),
    topModule: Optional[str] = Form(None),
    specs: Optional[str] = Form(None)
):
    """
    Parse Verilog files and generate netlist JSON.
    
    Args:
        files: List of Verilog files (.v or .sv)
        topModule: Optional top module name
        specs: Optional specs.json as string (will be attached to response)
    
    Returns:
        JSON with instances, nets, stats, and optionally specs
    """
    # Save uploaded files temporarily - match notebook approach exactly
    temp_files = []
    original_cwd = os.getcwd()
    backend_dir = Path(__file__).parent
    
    try:
        # Set working directory to backend folder (like notebook runs from project root)
        # This is critical for PyVerilog to create preprocess.output in the right place
        os.chdir(backend_dir)
        logger.info(f"Changed working directory to: {os.getcwd()}")
        
        # Ensure backend directory is writable (for PyVerilog temp files)
        if not os.access(backend_dir, os.W_OK):
            raise HTTPException(
                status_code=500,
                detail=f"Backend directory is not writable: {backend_dir}"
            )
        
        # Save files to current directory (like notebook does)
        for file in files:
            if not file.filename.endswith(('.v', '.sv')):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not a Verilog file (.v or .sv)"
                )
            
            # Save to current working directory (backend folder) - like notebook
            temp_path = backend_dir / file.filename
            logger.info(f"Saving file: {temp_path}")
            
            # Read file content
            content = await file.read()
            if not content:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is empty"
                )
            
            # Write file content
            with open(temp_path, "wb") as f:
                f.write(content)
            
            # Verify file was saved correctly
            if not temp_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save file: {file.filename}"
                )
            
            file_size = temp_path.stat().st_size
            if file_size == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} was saved but is empty (0 bytes)"
                )
            
            # Verify file content is readable
            try:
                with open(temp_path, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                    logger.info(f"File {file.filename} first line: {first_line[:50] if first_line else '(empty)'}")
            except Exception as e:
                logger.warning(f"Could not read file {file.filename} as text: {e}")
            
            logger.info(f"File saved successfully: {temp_path}, size: {file_size} bytes")
            # Use relative path like notebook does (from current working directory)
            temp_files.append(file.filename)
        
        # Build netlist graph using exact function from notebook
        # Match notebook: build_netlist_graph(["chip_top.v", "blocks.v"], top="chip_top")
        logger.info(f"Starting parse with files: {temp_files}, top: {topModule}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.info(f"Files exist: {[os.path.exists(f) for f in temp_files]}")
        
        try:
            G, top_name = build_netlist_graph(temp_files, top=topModule)
            logger.info(f"Parse complete. Top: {top_name}, Instances: {sum(1 for n,d in G.nodes(data=True) if d.get('type')=='instance')}, Nets: {sum(1 for n,d in G.nodes(data=True) if d.get('type')=='net')}")
        except Exception as parse_err:
            logger.error(f"Parse error: {parse_err}", exc_info=True)
            raise
        
        # Convert to JSON format
        result = graph_to_json(G, top_name)
        
        # Add specs if provided
        if specs:
            try:
                result["specs"] = json.loads(specs)
            except json.JSONDecodeError:
                result["specs"] = specs  # Keep as string if invalid JSON
        
        # Save to output directory (same location notebook expects)
        output_path = OUTPUT_DIR / "netlist.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        
        return JSONResponse(content=result)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")
    
    finally:
        # Restore original working directory
        try:
            os.chdir(original_cwd)
        except:
            pass
        # Clean up uploaded files
        for filename in temp_files:
            try:
                file_path = backend_dir / filename
                if file_path.exists():
                    file_path.unlink()
            except:
                pass
        # Clean up PyVerilog temp files (preprocess.output, etc.)
        try:
            for temp_file in backend_dir.glob("preprocess.*"):
                try:
                    temp_file.unlink()
                except:
                    pass
            # Also clean parser.out and parsetab.py if created
            for temp_file in ["parser.out", "parsetab.py"]:
                try:
                    temp_path = backend_dir / temp_file
                    if temp_path.exists():
                        temp_path.unlink()
                except:
                    pass
        except:
            pass


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}

