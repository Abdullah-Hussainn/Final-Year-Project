# Netlist Builder - Front-end for Verilog → Netlist

This front-end UI allows you to upload Verilog files and generate netlist JSON using the exact parsing logic from `FYP.ipynb`.

## Architecture

- **Backend**: FastAPI server (`backend/main.py`) that uses the exact `build_netlist_graph` function from the notebook
- **Frontend**: React + TypeScript + Tailwind UI (`frontend/`)
- **Parser**: Extracted to `netlist_parser.py` for reuse

## Setup

### Backend

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start the backend server:
```bash
# Windows
cd backend
start.bat

# Linux/Mac
cd backend
chmod +x start.sh
./start.sh
```

The backend will run on http://localhost:8000

### Frontend

1. Install Node.js dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend will run on http://localhost:3000

## Usage

1. Open http://localhost:3000 in your browser
2. Upload one or more Verilog files (.v or .sv) via drag-and-drop or file picker
3. (Optional) Specify the top module name
4. (Optional) Paste specs.json content
5. Click "Parse" to generate the netlist
6. View the results (instances and nets tables)
7. Click "Download JSON" to save the netlist

## Output

The parsed netlist is saved to `./out/netlist.json` (same location the notebook expects), containing:
- `top`: Top module name
- `instances`: List of instances with name and type
- `nets`: List of nets with name and connected pins
- `stats`: Summary statistics
- `specs`: Optional specs JSON if provided

## API Endpoint

- `POST /api/netlist`: Accepts multipart form data with:
  - `files[]`: One or more Verilog files
  - `topModule` (optional): Top module name
  - `specs` (optional): Specs JSON as string

Returns JSON with the parsed netlist structure.

