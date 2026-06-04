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
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the exact parsing functions from the notebook
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from netlist_parser import build_netlist_graph, graph_to_json

# Backend demo pipeline (parse -> saved placement -> metrics -> DEF/LEF -> PNG).
# Imported as a package so its relative imports (from . import metrics) resolve.
from backend.pipeline.full_pipeline import run_pipeline

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

# Pipeline artifacts directory (placement.png, placement.def, macros.lef, metrics.json)
OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# Whitelist of files servable via /api/outputs/{filename} and their media types.
SERVABLE_OUTPUTS = {
    "placement.png": "image/png",
    "placement.def": "text/plain",
    "macros.lef": "text/plain",
    "metrics.json": "application/json",
}


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


@app.post("/api/place")
async def place_design(
    files: List[UploadFile] = File(...),
    top_module: Optional[str] = Form(None),
):
    """
    Run the floorplanning pipeline on uploaded Verilog files.

    This is the backend-API milestone: it reuses the current saved-placement flow
    (no live PPO inference yet). It parses the netlist, loads the saved placement,
    computes metrics, and writes placement.png / placement.def / macros.lef /
    metrics.json into backend/outputs, then returns a JSON summary with URLs.

    Args:
        files: List of Verilog files (.v or .sv)
        top_module: Optional top module name (defaults to "chip_top")

    Returns:
        JSON with status, top module, instance/net counts, metrics, artifact URLs,
        and the live_ppo_inference flag.
    """
    top = (top_module or "").strip() or "chip_top"
    backend_dir = Path(__file__).parent
    upload_dir = backend_dir / "temp"
    upload_dir.mkdir(exist_ok=True)

    saved_paths: List[Path] = []
    try:
        # Save uploaded Verilog files temporarily (absolute paths for the pipeline).
        for file in files:
            if not file.filename or not file.filename.endswith((".v", ".sv")):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename!r} is not a Verilog file (.v or .sv)",
                )
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"File {file.filename} is empty")
            # Strip any directory components from the client-provided name.
            dest = upload_dir / Path(file.filename).name
            with open(dest, "wb") as f:
                f.write(content)
            saved_paths.append(dest)

        if not saved_paths:
            raise HTTPException(status_code=400, detail="No Verilog files were provided.")

        # Run the demo pipeline. Keep errors clean for the frontend (no tracebacks).
        try:
            summary = run_pipeline(
                verilog_files=[str(p) for p in saved_paths],
                top_module=top,
                output_dir=str(OUTPUTS_DIR),
            )
        except FileNotFoundError as e:
            # e.g. placement_results.json missing (saved-placement flow prerequisite).
            raise HTTPException(status_code=400, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # noqa: BLE001
            logger.error(f"Placement pipeline failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Placement pipeline failed: {e}")

        # Prefer the metrics persisted in metrics.json; fall back to the summary.
        metrics_data = {}
        metrics_path = OUTPUTS_DIR / "metrics.json"
        if metrics_path.exists():
            try:
                metrics_data = json.loads(metrics_path.read_text())
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not read metrics.json: {e}")

        netlist = summary.get("netlist", {})
        response = {
            "status": "ok",
            "top_module": summary.get("top_module", top),
            "instance_count": netlist.get("instances"),
            "net_count": netlist.get("nets"),
            "placement_method": summary.get("placement_method"),
            "live_ppo_inference": summary.get("live_ppo_inference", False),
            "metrics": metrics_data.get("metrics", summary.get("metrics")),
            "placement_image_url": "/api/outputs/placement.png",
            "def_url": "/api/outputs/placement.def",
            "lef_url": "/api/outputs/macros.lef",
            "metrics_url": "/api/outputs/metrics.json",
        }
        return JSONResponse(content=response)

    finally:
        # Clean up uploaded files.
        for p in saved_paths:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        # Clean up PyVerilog temp files that may be created in the CWD.
        for cwd in {Path.cwd(), backend_dir, Path(__file__).parent.parent}:
            for temp_file in list(cwd.glob("preprocess.*")) + [cwd / "parser.out", cwd / "parsetab.py"]:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass


@app.get("/api/outputs/{filename}")
async def get_output(filename: str):
    """
    Serve a generated pipeline artifact from backend/outputs.

    Only files in the SERVABLE_OUTPUTS whitelist are served, and the filename is
    validated to prevent path traversal (no slashes, no '..').
    """
    # Reject anything that isn't a bare filename (blocks path traversal).
    if filename != Path(filename).name or filename not in SERVABLE_OUTPUTS:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = (OUTPUTS_DIR / filename).resolve()
    # Defense in depth: ensure the resolved path stays inside OUTPUTS_DIR.
    if OUTPUTS_DIR.resolve() not in file_path.parents:
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found. Run POST /api/place first to generate it.",
        )

    return FileResponse(file_path, media_type=SERVABLE_OUTPUTS[filename], filename=filename)


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}

