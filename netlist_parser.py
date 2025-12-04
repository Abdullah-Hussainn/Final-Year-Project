"""
Netlist parser extracted from FYP.ipynb
This module contains the exact parsing logic from the notebook.
"""
import os
import logging
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
        if os.path.exists(f):
            normalized_files.append(f)
            logger.info(f"File found (relative): {f} (abs: {os.path.abspath(f)})")
        else:
            # Try absolute path
            abs_path = os.path.abspath(f)
            if os.path.exists(abs_path):
                # If absolute path works, use it
                normalized_files.append(abs_path)
                logger.info(f"File found (absolute): {abs_path}")
            else:
                raise FileNotFoundError(f"Verilog file not found: {f} (checked: {f} and {abs_path}, CWD: {current_dir})")
    
    logger.info("Calling PyVerilog parse()...")
    logger.info(f"Working directory before parse: {os.getcwd()}")
    logger.info(f"Files to parse: {normalized_files}")
    
    # Ensure current directory is writable for PyVerilog temp files
    if not os.access(current_dir, os.W_OK):
        raise PermissionError(f"Current directory is not writable: {current_dir}")
    
    # Clean up any existing preprocess.output from previous runs
    preprocess_file = os.path.join(current_dir, "preprocess.output")
    try:
        if os.path.exists(preprocess_file):
            os.remove(preprocess_file)
            logger.info(f"Removed existing preprocess.output: {preprocess_file}")
    except Exception as e:
        logger.warning(f"Could not remove existing preprocess.output: {e}")
    
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
    try:
        with open(preprocess_file, 'w') as f:
            pass  # Create empty file
        logger.info(f"Created empty preprocess.output: {preprocess_file}")
    except Exception as e:
        logger.warning(f"Could not create preprocess.output: {e}")
    
    # Match notebook exactly: ast, directives = parse(verilog_files)
    # PyVerilog will create preprocess.output in the current working directory
    try:
        ast, directives = parse(normalized_files)
    except Exception as e:
        logger.error(f"PyVerilog parse() failed: {e}", exc_info=True)
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
            instances.append({
                "name": node,
                "type": data.get("mod", "unknown")
            })
    
    # Extract nets with pins
    for node, data in G.nodes(data=True):
        if data.get("type") == "net":
            pins = []
            # Find all edges connected to this net
            for neighbor in G.neighbors(node):
                edge_data = G.get_edge_data(node, neighbor)
                if edge_data and "port" in edge_data:
                    pins.append({
                        "inst": neighbor,
                        "pin": edge_data["port"]
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

