# Setup Instructions

## Quick Start

### 1. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Backend Server

```bash
# Windows
cd backend
start.bat

# Linux/Mac
cd backend
chmod +x start.sh
./start.sh
```

Backend will run on http://localhost:8000

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 4. Start Frontend

```bash
npm run dev
```

Frontend will run on http://localhost:3000

## Usage

1. Open http://localhost:3000
2. Upload Verilog files (.v or .sv)
3. Optionally specify top module
4. Optionally paste specs.json
5. Click "Parse"
6. View results and download JSON

## Output

The netlist is saved to `./out/netlist.json` (same location as notebook expects).

## Architecture

- **Parser**: `netlist_parser.py` - Exact functions from FYP.ipynb
- **Backend**: `backend/main.py` - FastAPI server using the parser
- **Frontend**: `frontend/` - React + TypeScript + Tailwind UI

