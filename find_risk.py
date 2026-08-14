"""
Find all f-string format operations in Python files and check if any variable 
that gets formatted with a numeric spec (:.1f, :,.2f, :,) could potentially 
receive a string value that isn't a number.
"""
import ast, sys

files = [
    "mcp_server/server.py",
    "mcp_server/gam_client.py",
    "mcp_server/email_service.py",
    "mcp_server/services/network_analytics.py",
    "mcp_server/services/query_engine.py",
    "mcp_server/services/bedrock_service.py",
]

NUMERIC_SPECS = {'.1f', '.2f', '.4f', '.6f', '.0f', ',.2f', ',.1f', '+,.2f', ','}

for filepath in files:
    try:
        with open(filepath) as f:
            src = f.read()
        tree = ast.parse(src, filename=filepath)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        continue
    
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for val in node.values:
                if not isinstance(val, ast.FormattedValue):
                    continue
                if not val.format_spec:
                    continue
                # Extract format spec text
                spec_parts = []
                if isinstance(val.format_spec, ast.JoinedStr):
                    for part in val.format_spec.values:
                        if isinstance(part, ast.Constant):
                            spec_parts.append(str(part.value))
                spec = ''.join(spec_parts)
                
                if any(s in spec for s in NUMERIC_SPECS):
                    # Get the expression being formatted
                    expr = ast.unparse(val.value)
                    print(f"  {filepath}:{node.lineno}: f'{{...{spec}...}}' where expr={expr!r}")
