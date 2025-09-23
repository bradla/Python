import ast

def sort_functions_by_line_number(filename):
    """
    Read a Python file and sort functions by their line numbers
    """
    functions = []
    
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    tree = ast.parse(content)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            start_line = node.lineno - 1
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
            
            lines = content.split('\n')
            function_code = '\n'.join(lines[start_line:end_line])
            
            functions.append({
                'name': node.name,
                'code': function_code,
                'line': node.lineno
            })
    
    # Sort functions by line number
    functions.sort(key=lambda x: x['line'])
    
    return functions

# Example usage
filename = 'example.py'
sorted_functions = sort_functions_by_line_number(filename)

print("Functions sorted by line number:")
for func in sorted_functions:
    #print(f"\nLine {func['line']}: {func['name']}")
    print(func['code'])
    #print("-" * 40)
