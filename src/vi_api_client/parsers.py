"""Parsers for CLI arguments and other string inputs."""

import json
from typing import Any, Dict, List

def parse_cli_params(params_list: List[str]) -> Dict[str, Any]:
    """Parse a list of CLI parameter strings into a dictionary.
    
    Supports two formats:
    1. Single JSON string: '{"slope": 1.0, "shift": 0}'
    2. Key-Value pairs: 'slope=1.0' 'shift=0' 'mode=active'
    
    Performs basic type inference for numbers and booleans.
    
    Args:
        params_list: List of strings from the command line (e.g. argparse nargs='*').
        
    Returns:
        Dictionary of parsed parameters.
    """
    params = {}
    
    if not params_list:
        return params

    # Case 1: Single argument that looks like JSON
    if len(params_list) == 1 and params_list[0].strip().startswith("{"):
         try:
             return json.loads(params_list[0])
         except json.JSONDecodeError:
             # Fallback: maybe it's just a weird key=value that starts with {? 
             # No, let's treat it as an error or try key=value parsing if it fails?
             # For now, print error logic is handled by caller, but we can just raise or return empty/partial
             # The original code caught it. Let's start clean.
             # If it looks like JSON but fails, we probably shouldn't try key=value interpretation 
             # unless the user accidentally put spaces in a JSON string?
             # Let's assume strict JSON if it looks like JSON.
             raise ValueError("Example appears to be JSON but could not be parsed.")

    # Case 2: Key=Value pairs
    for item in params_list:
        if "=" not in item:
            raise ValueError(f"Invalid argument format '{item}'. Expected key=value.")
            
        key, val_str = item.split("=", 1)
        
        # Type inference
        value = val_str
        if val_str.lower() == "true":
            value = True
        elif val_str.lower() == "false":
            value = False
        else:
            try:
                value = int(val_str)
            except ValueError:
                try:
                    value = float(val_str)
                except ValueError:
                    # Try parsing as JSON (e.g. for nested objects or lists)
                    if val_str.startswith("[") or val_str.startswith("{"):
                         try:
                             value = json.loads(val_str)
                         except json.JSONDecodeError:
                             pass # Keep as string
        
        params[key] = value
        
    return params
