import re

def extract_functions_with_regex(filename):
    """
    Extract functions using regex pattern matching
    """
    functions = []
    
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Regex pattern to match function definitions
    pattern = r'def\s+(\w+)\s*\([^)]*\)\s*:\s*\n(?:.*\n)*?(?=\n\S|\Z)'
    
    matches = re.finditer(pattern, content, re.MULTILINE)
    
    for match in matches:
        function_name = match.group(1)
        function_code = match.group(0)
        
        # Count lines to find starting line
        lines_before = content[:match.start()].count('\n')
        line_number = lines_before + 1
        
        functions.append({
            'name': function_name,
            'code': function_code,
            'line': line_number
        })
    
    return functions

def sort_and_display_functions(filename, sort_by='name'):
    """
    Main function to extract and sort functions
    """
    functions = extract_functions_with_regex(filename)
    
    if sort_by == 'name':
        functions.sort(key=lambda x: x['name'].lower())
        sort_description = "alphabetically by name"
    elif sort_by == 'line':
        functions.sort(key=lambda x: x['line'])
        sort_description = "by line number"
    else:
        sort_description = "alphabetically by name"
        functions.sort(key=lambda x: x['name'].lower())
    
    print(f"Functions sorted {sort_description}:")
    print("=" * 50)
    
    for i, func in enumerate(functions, 1):
        #print(f"\n{i}. {func['name']} (line {func['line']}):")
        print(func['code'])
        #print("-" * 40)

# Example usage
filename = 'example.py'

# Sort by name
sort_and_display_functions(filename, sort_by='name')

# Sort by line number
#sort_and_display_functions(filename, sort_by='line')
