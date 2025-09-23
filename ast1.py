import ast
import re

def sort_functions_alphabetically(filename):
    """
    Read a Python file and sort functions alphabetically by name
    """
    functions = []
    
    # Read the file
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Parse the AST to find function definitions
    tree = ast.parse(content)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Get function source code using line numbers
            start_line = node.lineno - 1  # Convert to 0-based indexing
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
            
            # Extract function code
            lines = content.split('\n')
            function_code = '\n'.join(lines[start_line:end_line])
            
            functions.append({
                'name': node.name,
                'code': function_code,
                'line': node.lineno
            })
    
    # Sort functions alphabetically by name
    functions.sort(key=lambda x: x['name'].lower())
    
    return functions

# Example usage
filename = 'example.py'
sorted_functions = sort_functions_alphabetically(filename)

print("Functions sorted alphabetically:")
for func in sorted_functions:
    #print(f"\n{func['name']} (line {func['line']}):")
    print(func['code'])
    #print("-" * 40)
