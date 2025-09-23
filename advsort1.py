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

def display_sorted_functions(filename, sort_key='name'):
    """
    Display functions sorted by various criteria
    """
    functions = extract_all_functions(filename)
    
    sort_options = {
        'name': lambda x: x['name'].lower(),
        'full_name': lambda x: x['full_name'].lower(),
        'line': lambda x: x['line'],
        'type': lambda x: (x['type'], x['name'].lower())
    }
    
    if sort_key in sort_options:
        functions.sort(key=sort_options[sort_key])
    
    print(f"Functions sorted by {sort_key}:")
    print("=" * 60)
    
    for func in functions:
        type_indicator = "[M]" if func['type'] == 'method' else "[F]"
        class_info = f" (Class: {func['class']})" if func['class'] else ""
        decorator_info = f" [Decorators: {', '.join(func['decorators'])}]" if func['decorators'] else ""
        
        print(f"\n{type_indicator} {func['full_name']}{class_info}{decorator_info}")
        print(f"Line {func['line']}:")
        print(func['code'])
        print("-" * 60)

# Example usage
filename = 'example.py'

# Different sorting options
display_sorted_functions(filename, 'name')      # Sort by function name
display_sorted_functions(filename, 'line')      # Sort by line number
display_sorted_functions(filename, 'type')      # Sort by type (function/method)
