
import ast
import os
import hashlib
import sys

def get_function_hash(func_node):
    """
    Generates a hash for a function node.
    """
    # Exclude function name to catch functions with the same body but different names
    func_node_copy = func_node.__class__()
    for field in func_node._fields:
        if field != 'name':
            setattr(func_node_copy, field, getattr(func_node, field))

    func_bytes = ast.dump(func_node_copy).encode('utf-8')
    return hashlib.md5(func_bytes).hexdigest()

def extract_functions(file_path):
    """
    Extracts all function definitions from a Python file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        print(f"Syntax error in file {file_path}: {e}")
        return []

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append((node, file_path))
    return functions

def main(directory):
    # Collect all .py files in the directory
    python_files = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.py'):
                python_files.append(os.path.join(root, filename))

    # Extract functions from files
    function_hashes = {}
    function_locations = {}

    for file_path in python_files:
        functions = extract_functions(file_path)
        for func_node, file in functions:
            func_hash = get_function_hash(func_node)
            if func_hash in function_hashes:
                function_hashes[func_hash].append((func_node.name, file))
            else:
                function_hashes[func_hash] = [(func_node.name, file)]

    # Identify duplicates
    duplicates = {h: locs for h, locs in function_hashes.items() if len(locs) > 1}

    if not duplicates:
        print("No duplicate functions found.")
        return

    print("Duplicate functions found:")
    for h, funcs in duplicates.items():
        print(f"\nDuplicate Functions (Hash: {h}):")
        for func_name, file in funcs:
            print(f" - Function '{func_name}' in file '{file}'")

    # Remove duplicates (keep one copy)
    for h, funcs in duplicates.items():
        # Keep the first occurrence
        _, keep_file = funcs[0]
        files_to_modify = [f for _, f in funcs[1:]]  # All other files

        for file_path in files_to_modify:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Re-parse the file to find exact location of the function
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source, filename=file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if get_function_hash(node) == h:
                        # Remove the function from the source code
                        start_line = node.lineno - 1  # Line numbers start at 1
                        # Find the end line of the function
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else None
                        if end_line is None:
                            # Fallback if end_lineno is not available (Python < 3.8)
                            end_line = find_end_line(node)
                        # Remove lines from start_line to end_line
                        for i in range(start_line, end_line):
                            lines[i] = ''  # Remove line

                        # Optionally, add a comment indicating removal
                        lines[start_line] = f"# Duplicate function '{node.name}' removed\n"
                        break  # Assume one function per hash per file

            # Write the modified file back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

    print("\nDuplicate functions removed. Please verify your codebase.")

def find_end_line(node):
    """
    Fallback method to estimate the end line number of a function node.
    """
    max_lineno = node.lineno
    for child in ast.iter_child_nodes(node):
        child_end_lineno = getattr(child, 'end_lineno', child.lineno)
        if child_end_lineno > max_lineno:
            max_lineno = child_end_lineno
    return max_lineno

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python remove_duplicates.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    main(directory)
