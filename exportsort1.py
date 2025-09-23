import ast


def extract_all_functions(filename):
    """
    Extract all functions including class methods, with decorator support
    """
    functions = []
    
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    tree = ast.parse(content)
    
    class FunctionExtractor(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None
        
        def visit_ClassDef(self, node):
            # Store current class name
            old_class = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = old_class
        
        def visit_FunctionDef(self, node):
            # Get function source code
            start_line = node.lineno - 1
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
            
            lines = content.split('\n')
            function_code = '\n'.join(lines[start_line:end_line])
            
            # Get decorators
            decorators = [ast.unparse(decorator) for decorator in node.decorator_list]
            
            functions.append({
                'name': node.name,
                'full_name': f"{self.current_class}.{node.name}" if self.current_class else node.name,
                'code': function_code,
                'line': node.lineno,
                'class': self.current_class,
                'decorators': decorators,
                'type': 'method' if self.current_class else 'function'
            })
            
            self.generic_visit(node)
    
    extractor = FunctionExtractor()
    extractor.visit(tree)
    
    return functions

def create_sorted_functions_file(input_filename, output_filename, sort_by='name'):
    """
    Create a new Python file with functions sorted as specified
    """
    functions = extract_all_functions(input_filename)
    
    if sort_by == 'name':
        functions.sort(key=lambda x: x['name'].lower())
    elif sort_by == 'line':
        functions.sort(key=lambda x: x['line'])
    
    # Read original file for imports and other code
    with open(input_filename, 'r', encoding='utf-8') as file:
        original_content = file.read()
    
    # Extract imports and other top-level code
    tree = ast.parse(original_content)
    imports = []
    other_code = []
    
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))
        elif not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            other_code.append(ast.get_source_segment(original_content, node))
    
    # Write to new file
    with open(output_filename, 'w', encoding='utf-8') as file:
        # Write imports
        for imp in imports:
            file.write(imp + '\n')
        file.write('\n')
        
        # Write other code
        for code in other_code:
            file.write(code + '\n\n')
        
        # Write sorted functions
        for func in functions:
            file.write(func['code'] + '\n\n')
    
    print(f"Sorted functions written to {output_filename}")

# Example usage
input_file = 'example.py'
output_file = 'example_sorted.py'

create_sorted_functions_file(input_file, output_file, sort_by='name')
