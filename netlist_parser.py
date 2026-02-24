"""
Netlist parser extracted from FYP.ipynb
This module contains the exact parsing logic from the notebook.
"""
import os
import logging
import glob
import shutil
import networkx as nx
from pyverilog.vparser.parser import parse
from pyverilog.vparser.ast import (
    ModuleDef, InstanceList, Instance, PortArg,
    Identifier, Pointer, IntConst
)

# Set up logging
logger = logging.getLogger(__name__)


def _stringify_conn(expr):
    if expr is None:
        return ""
    if isinstance(expr, Identifier):
        return expr.name
    if isinstance(expr, Pointer):     # e.g. data[3]
        base = _stringify_conn(expr.var)
        idx  = _stringify_conn(expr.ptr)
        return f"{base}[{idx}]"
    if isinstance(expr, IntConst):
        return expr.value
    return str(expr)


def _get_portarg_expr(carg):
    # Handle PyVerilog version differences: argname / arg / expr
    # Match notebook exactly - try all three in order
    for attr in ("argname", "arg", "expr"):
        if hasattr(carg, attr) and getattr(carg, attr) is not None:
            return getattr(carg, attr)
    return None


def _get_portarg_name(carg, idx):
    # Named .port(...) vs ordered connection
    if getattr(carg, "portname", None) is not None:
        return str(carg.portname)
    return f"_{idx}"


def build_netlist_graph(verilog_files, top=None, treat_top_ios_as_nets=True):
    """
    Build a bipartite NetworkX graph from Verilog files.
    Exact implementation from FYP.ipynb Cell 4.
    
    Args:
        verilog_files: List of Verilog file paths or single path
        top: Top module name (if None, auto-detect if only one module)
        treat_top_ios_as_nets: Whether to add top I/O ports as net nodes
    
    Returns:
        Tuple of (NetworkX Graph, top_module_name) with nodes labeled as 'instance' or 'net'
    """
    # Ensure files exist and are readable
    current_dir = os.getcwd()
    logger.info(f"Current working directory: {current_dir}")
    
    # PyVerilog expects files relative to current working directory
    # OR absolute paths - but it creates preprocess.output in CWD
    # So we use relative paths from CWD (like notebook does)
    normalized_files = []
    for f in verilog_files:
        # First check if file exists as-is (relative to CWD)
        file_path = None
        if os.path.exists(f):
            file_path = f
            abs_path = os.path.abspath(f)
            logger.info(f"File found (relative): {f} (abs: {abs_path})")
        else:
            # Try absolute path
            abs_path = os.path.abspath(f)
            if os.path.exists(abs_path):
                file_path = abs_path
                logger.info(f"File found (absolute): {abs_path}")
            else:
                raise FileNotFoundError(f"Verilog file not found: {f} (checked: {f} and {abs_path}, CWD: {current_dir})")
        
        # Verify file is not empty and has content
        if file_path:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError(f"Verilog file is empty: {file_path}")
            
            # Try to read first few bytes to verify it's readable
            try:
                with open(file_path, 'rb') as test_file:
                    first_bytes = test_file.read(100)
                    if not first_bytes:
                        raise ValueError(f"Verilog file appears to be empty or unreadable: {file_path}")
                    logger.info(f"File {file_path} verified: {file_size} bytes, starts with: {first_bytes[:50]}")
            except Exception as e:
                raise ValueError(f"Cannot read Verilog file {file_path}: {e}")
            
            normalized_files.append(file_path)
    
    logger.info("Calling PyVerilog parse()...")
    logger.info(f"Working directory before parse: {os.getcwd()}")
    logger.info(f"Files to parse: {normalized_files}")
    
    # Ensure current directory is writable for PyVerilog temp files
    if not os.access(current_dir, os.W_OK):
        raise PermissionError(f"Current directory is not writable: {current_dir}")
    
    # Aggressive cleanup of PyVerilog temp files before parsing
    # This prevents parsing issues from leftover temp files
    temp_patterns = [
        "preprocess.output",
        "preprocess.output.*",
        "parser.out",
        "parsetab.py",
        "parsetab.pyc",
        "__pycache__/parsetab.*",
    ]
    
    logger.info("Cleaning up PyVerilog temp files...")
    for pattern in temp_patterns:
        try:
            # Handle patterns with wildcards
            if "*" in pattern:
                matches = glob.glob(os.path.join(current_dir, pattern))
                for match in matches:
                    try:
                        if os.path.isfile(match):
                            os.remove(match)
                            logger.info(f"Removed temp file: {match}")
                        elif os.path.isdir(match):
                            shutil.rmtree(match)
                            logger.info(f"Removed temp directory: {match}")
                    except Exception as e:
                        logger.warning(f"Could not remove {match}: {e}")
            else:
                # Handle specific files
                temp_path = os.path.join(current_dir, pattern)
                if os.path.exists(temp_path):
                    try:
                        if os.path.isfile(temp_path):
                            os.remove(temp_path)
                            logger.info(f"Removed temp file: {temp_path}")
                        elif os.path.isdir(temp_path):
                            shutil.rmtree(temp_path)
                            logger.info(f"Removed temp directory: {temp_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove {temp_path}: {e}")
        except Exception as e:
            logger.warning(f"Error cleaning up pattern {pattern}: {e}")
    
    # Also clean up any __pycache__ directories that might contain parsetab files
    try:
        pycache_dir = os.path.join(current_dir, "__pycache__")
        if os.path.exists(pycache_dir):
            for item in os.listdir(pycache_dir):
                if "parsetab" in item:
                    item_path = os.path.join(pycache_dir, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                            logger.info(f"Removed cached file: {item_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove {item_path}: {e}")
    except Exception as e:
        logger.warning(f"Error cleaning up __pycache__: {e}")
    
    # Ensure we can write to the directory
    try:
        test_file = os.path.join(current_dir, ".test_write")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        logger.info(f"Directory is writable: {current_dir}")
    except Exception as e:
        raise PermissionError(f"Cannot write to directory {current_dir}: {e}")
    
    # Create empty preprocess.output file - PyVerilog may try to read it before creating it
    # This is a workaround for PyVerilog's preprocessor behavior
    preprocess_file = os.path.join(current_dir, "preprocess.output")
    try:
        # Ensure file doesn't exist first (should have been cleaned up, but double-check)
        if os.path.exists(preprocess_file):
            try:
                os.remove(preprocess_file)
            except:
                pass
        # Create empty file
        with open(preprocess_file, 'w') as f:
            pass  # Create empty file
        # Verify file was created
        if not os.path.exists(preprocess_file):
            raise IOError(f"Failed to create preprocess.output at {preprocess_file}")
        logger.info(f"Created empty preprocess.output: {preprocess_file}")
    except Exception as e:
        logger.error(f"Could not create preprocess.output: {e}")
        raise IOError(f"Failed to create preprocess.output file: {e}")
    
    # Match notebook exactly: ast, directives = parse(verilog_files)
    # PyVerilog will create preprocess.output in the current working directory
    try:
        # Log file contents before parsing for debugging
        for f in normalized_files:
            try:
                with open(f, 'r', encoding='utf-8', errors='ignore') as test_file:
                    content_preview = test_file.read(200)
                    logger.info(f"File {f} content preview (first 200 chars): {repr(content_preview)}")
                    test_file.seek(0)
                    line_count = sum(1 for _ in test_file)
                    logger.info(f"File {f} has {line_count} lines")
            except Exception as read_err:
                logger.warning(f"Could not preview file {f}: {read_err}")
        
        logger.info(f"Calling PyVerilog parse() with {len(normalized_files)} file(s)")
        ast, directives = parse(normalized_files)
        logger.info("PyVerilog parse() completed successfully")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"PyVerilog parse() failed: {error_msg}", exc_info=True)
        
        # Provide more context for "at end of input" errors
        if "at end of input" in error_msg.lower() or "none" in error_msg.lower():
            logger.error("This error usually means PyVerilog received an empty or incomplete file.")
            for f in normalized_files:
                if os.path.exists(f):
                    file_size = os.path.getsize(f)
                    logger.error(f"File {f}: exists={True}, size={file_size} bytes")
                    try:
                        with open(f, 'r', encoding='utf-8', errors='ignore') as test_file:
                            first_line = test_file.readline()
                            logger.error(f"File {f} first line: {repr(first_line[:100])}")
                    except Exception as read_err:
                        logger.error(f"Could not read file {f}: {read_err}")
                else:
                    logger.error(f"File {f}: DOES NOT EXIST")
        
        # Check if preprocess.output exists and provide more context
        preprocess_file = os.path.join(current_dir, "preprocess.output")
        logger.error(f"preprocess.output path: {preprocess_file}")
        logger.error(f"preprocess.output exists: {os.path.exists(preprocess_file)}")
        logger.error(f"CWD writable: {os.access(current_dir, os.W_OK)}")
        if os.path.exists(preprocess_file):
            logger.error(f"preprocess.output is readable: {os.access(preprocess_file, os.R_OK)}")
            logger.error(f"preprocess.output is writable: {os.access(preprocess_file, os.W_OK)}")
        raise
    logger.info("Parse complete, extracting modules...")
    
    modules = {d.name: d for d in ast.description.definitions if isinstance(d, ModuleDef)}
    logger.info(f"Modules found: {list(modules.keys())}")

    if top is None:
        if len(modules) != 1:
            raise ValueError(f"Specify top. Found modules: {list(modules)}")
        top = next(iter(modules))
    if top not in modules:
        raise ValueError(f"Top {top} not found. Available: {list(modules)}")

    top_mod = modules[top]
    logger.info(f"Building graph for top module: {top}")
    G = nx.Graph()

    # Optional: add top I/O names as net nodes
    logger.info("Adding top I/O ports as nets...")
    if treat_top_ios_as_nets and getattr(top_mod, "portlist", None):
        for p in (top_mod.portlist.ports or []):
            name = getattr(p, "name", None) or getattr(getattr(p, "first", None), "name", None)
            if name and not G.has_node(name):
                G.add_node(name, type="net", name=name, is_top_io=True, bipartite=1)

    # scan instances (one level) - match notebook exactly
    logger.info("Scanning instances...")
    for item in getattr(top_mod, "items", []) or []:
        if not isinstance(item, InstanceList): 
            continue
        child_mod = item.module
        for inst in item.instances or []:
            if not isinstance(inst, Instance): 
                continue
            iname = inst.name
            if not G.has_node(iname):
                G.add_node(iname, type="instance", mod=child_mod, name=iname, bipartite=0, ports={})
            for idx, carg in enumerate(inst.portlist or []):
                if not isinstance(carg, PortArg): 
                    continue
                port = _get_portarg_name(carg, idx)
                expr = _get_portarg_expr(carg)
                net  = _stringify_conn(expr)
                if not net: 
                    continue
                if not G.has_node(net):
                    G.add_node(net, type="net", name=net, is_top_io=False, bipartite=1)
                G.nodes[iname]["ports"][port] = net
                G.add_edge(iname, net, port=port)
    
    logger.info(f"Graph complete: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G, top


def extract_netlist(G, top_module):
    """
    Extract instances and nets from the netlist graph in the required schema.
    Use this output for DEF export and for deterministic downstream steps.

    Args:
        G: NetworkX graph from build_netlist_graph
        top_module: Name of the top module (unused but kept for API consistency)

    Returns:
        Tuple (instances_list, nets_dict):
          - instances_list: list of {"name": str, "type": str} (type = module name)
          - nets_dict: dict mapping net_name -> list of {"inst": str, "pin": str}
                       (only instance pins; constant-only nets may have empty list)
    """
    if G is None:
        raise ValueError("extract_netlist: G must not be None (extraction failed?)")
    instances_list = []
    for node, data in G.nodes(data=True):
        if data.get("type") == "instance":
            mod = data.get("mod", "unknown")
            if isinstance(mod, str):
                m = mod
            else:
                m = getattr(mod, "name", str(mod))
            instances_list.append({"name": node, "type": m})
    nets_dict = {}
    for node, data in G.nodes(data=True):
        if data.get("type") != "net":
            continue
        pins = []
        for neighbor in G.neighbors(node):
            if G.nodes[neighbor].get("type") != "instance":
                continue
            edge_data = G.get_edge_data(node, neighbor)
            if edge_data and "port" in edge_data:
                port = edge_data["port"]
                if isinstance(port, str):
                    p = port
                else:
                    p = getattr(port, "name", str(port))
                pins.append({"inst": neighbor, "pin": p})
        nets_dict[node] = pins
    return instances_list, nets_dict


def graph_to_json(G, top_module):
    """
    Convert NetworkX graph to JSON format matching the expected API response.
    
    Args:
        G: NetworkX graph from build_netlist_graph
        top_module: Name of the top module
    
    Returns:
        Dictionary with instances, nets, and stats
    """
    instances = []
    nets = []
    
    # Extract instances
    for node, data in G.nodes(data=True):
        if data.get("type") == "instance":
            mod = data.get("mod", "unknown")
            m = mod if isinstance(mod, str) else getattr(mod, "name", str(mod))
            instances.append({
                "name": node,
                "type": m
            })
    
    # Extract nets with pins
    for node, data in G.nodes(data=True):
        if data.get("type") == "net":
            pins = []
            # Find all edges connected to this net
            for neighbor in G.neighbors(node):
                edge_data = G.get_edge_data(node, neighbor)
                if edge_data and "port" in edge_data:
                    port = edge_data["port"]
                    p = port if isinstance(port, str) else getattr(port, "name", str(port))
                    pins.append({
                        "inst": neighbor,
                        "pin": p
                    })
            nets.append({
                "name": node,
                "pins": pins
            })
    
    return {
        "top": top_module,
        "instances": instances,
        "nets": nets,
        "stats": {
            "instances": len(instances),
            "nets": len(nets)
        }
    }


def write_lef(lef_path, dbu_per_micron=100, macro_sizes=None, pin_defs=None):
    """
    Write a minimal LEF file for OpenROAD visualization.
    Defines MACROs simple_rom and simple_alu with pins; minimal LAYER M1 and SITE CORE.

    Args:
        lef_path: Output path for the .lef file
        dbu_per_micron: DEF/LEF database units per micron (default 100)
        macro_sizes: dict macro_name -> (width_dbu, height_dbu). Default: 4000 x 4000 for both
        pin_defs: dict macro_name -> list of pin names. Default: simple_rom [addr, data], simple_alu [a, b, op, y]
    """
    import os
    macro_sizes = macro_sizes or {
        "simple_rom": (4000, 4000),
        "simple_alu": (4000, 4000),
    }
    pin_defs = pin_defs or {
        "simple_rom": ["addr", "data"],
        "simple_alu": ["a", "b", "op", "y"],
    }
    os.makedirs(os.path.dirname(lef_path) or ".", exist_ok=True)
    lines = [
        "VERSION 5.8 ;",
        "NAMESCASESENSITIVE ON ;",
        f"UNITS DATABASE MICRONS {dbu_per_micron} ;",
        "",
        "SITE CORE",
        "  CLASS CORE ;",
        "  SIZE 1.000 BY 1.000 ;",
        "END CORE",
        "",
        "LAYER M1",
        "  TYPE ROUTING ;",
        "  DIRECTION HORIZONTAL ;",
        "  PITCH 100 100 ;",
        "  WIDTH 100 ;",
        "END M1",
        "",
    ]
    # LEF numeric values (SIZE, RECT) are in microns
    for macro_name in ("simple_rom", "simple_alu"):
        w_dbu, h_dbu = macro_sizes.get(macro_name, (4000, 4000))
        w_um = w_dbu / dbu_per_micron
        h_um = h_dbu / dbu_per_micron
        pins = pin_defs.get(macro_name, [])
        lines.extend([
            f"MACRO {macro_name}",
            "  CLASS BLOCK ;",
            f"  FOREIGN {macro_name} 0.000 0.000 ;",
            f"  SIZE {w_um:.3f} BY {h_um:.3f} ;",
            "",
        ])
        for i, p in enumerate(pins):
            # Place pin rectangles around perimeter (in DBU then convert to microns)
            if i % 4 == 0:
                x, y = 0, int(h_dbu * (0.2 + 0.2 * (i // 4)))
            elif i % 4 == 1:
                x, y = w_dbu - 100, int(h_dbu * (0.2 + 0.2 * (i // 4)))
            elif i % 4 == 2:
                x, y = int(w_dbu * (0.2 + 0.2 * (i // 4))), 0
            else:
                x, y = int(w_dbu * (0.2 + 0.2 * (i // 4))), h_dbu - 100
            x_um = x / dbu_per_micron
            y_um = y / dbu_per_micron
            x2_um = (x + 100) / dbu_per_micron
            y2_um = (y + 100) / dbu_per_micron
            lines.extend([
                f"  PIN {p}",
                "    DIRECTION INOUT ;",
                "    USE SIGNAL ;",
                "    PORT",
                "      LAYER M1 ;",
                f"      RECT {x_um:.3f} {y_um:.3f} {x2_um:.3f} {y2_um:.3f} ;",
                "    END",
                f"  END {p}",
                "",
            ])
        lines.append("END " + macro_name)
        lines.append("")
    with open(lef_path, "w") as f:
        f.write("\n".join(lines))
    logger.info("Wrote LEF: %s", lef_path)


def write_def(def_path, design_name, H, W, scale, instances, placements, nets):
    """
    Write DEF with COMPONENTS (correct macro masters per instance type) and NETS.
    Scale: grid cell -> DBU = scale; DIEAREA (0,0) to (W*scale, H*scale).
    Include only nets that connect >= 2 instance pins (for ratsnest visibility).

    Args:
        def_path: Output path for .def file
        design_name: DESIGN name (e.g. chip_top)
        H, W: Grid height and width (rows, cols)
        scale: DBU per grid cell (5000 for 50 um per cell with UNITS MICRONS 100)
        instances: list of {"name": str, "type": str} (type = LEF macro name)
        placements: dict inst_name -> [y, x, h, w] (grid coordinates)
        nets: dict net_name -> list of {"inst": str, "pin": str}
    """
    import os
    os.makedirs(os.path.dirname(def_path) or ".", exist_ok=True)
    inst_by_name = {i["name"]: i for i in instances}
    die_w = W * scale
    die_h = H * scale
    lines = [
        "VERSION 5.8 ;",
        'DIVIDERCHAR "/" ;',
        'BUSBITCHARS "[]" ;',
        f"DESIGN {design_name} ;",
        "UNITS DISTANCE MICRONS 100 ;",
        f"DIEAREA ( 0 0 ) ( {die_w} {die_h} ) ;",
        "",
        f"COMPONENTS {len(placements)} ;",
    ]
    for inst_name, box in placements.items():
        inst_info = inst_by_name.get(inst_name, {})
        master = inst_info.get("type", "macro")
        if not isinstance(master, str):
            master = getattr(master, "name", "macro")
        y, x, h, w = box
        x_def = x * scale
        y_def = y * scale
        lines.append(f"  - {inst_name} {master} + PLACED ( {x_def} {y_def} ) N ;")
    lines.append("END COMPONENTS")
    lines.append("")

    # NETS: only nets with >= 2 unique instance pins (skip constant-only)
    nets_to_write = []
    for net_name, pins in (nets or {}).items():
        # Only instance pins (inst must be in placements)
        conns = [p for p in pins if isinstance(p, dict) and p.get("inst") in placements]
        if len(conns) >= 2:
            nets_to_write.append((net_name, conns))
    lines.append(f"NETS {len(nets_to_write)} ;")
    for net_name, conns in nets_to_write:
        parts = [f"  - {net_name}"]
        for c in conns:
            parts.append(f" ( {c['inst']} {c['pin']} )")
        parts.append(" ;")
        lines.append("".join(parts))
    lines.append("END NETS")
    lines.append("")
    lines.append("END DESIGN")

    with open(def_path, "w") as f:
        f.write("\n".join(lines))
    logger.info("Wrote DEF: %s (components=%d, nets=%d)", def_path, len(placements), len(nets_to_write))

