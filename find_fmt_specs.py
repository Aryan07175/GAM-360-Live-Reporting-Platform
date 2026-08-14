import ast, os

def find_fstrings(dir_path):
    for root, _, files in os.walk(dir_path):
        for file in files:
            if not file.endswith('.py'): continue
            if 'venv' in root: continue
            
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            try:
                tree = ast.parse(content, filename=path)
            except SyntaxError:
                continue
                
            for node in ast.walk(tree):
                if isinstance(node, ast.FormattedValue):
                    if node.format_spec:
                        if isinstance(node.format_spec, ast.JoinedStr):
                            for v in node.format_spec.values:
                                if isinstance(v, ast.Constant):
                                    print(f"Format specifier in {file} line {node.lineno}: '{v.value}'")
                                elif isinstance(v, ast.FormattedValue):
                                    print(f"DYNAMIC format specifier in {file} line {node.lineno}")

find_fstrings('/Users/aryan/Desktop/GAM-360-Live-Reporting-Platform/GAM-360-Live-Reporting-Platform/mcp_server')
