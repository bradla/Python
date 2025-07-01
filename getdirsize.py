import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_directory_size(path):
    """
    Calculates the total size of a directory in bytes.
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # Skip symbolic links that point to non-existent files to avoid errors
            if not os.path.islink(fp) or os.path.exists(fp):
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    # Handle cases where file might be inaccessible
                    pass
    return total_size

def format_size(size_in_bytes):
    """
    Formats a size in bytes into a human-readable string (e.g., KB, MB, GB).
    """
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024**2:
        return f"{size_in_bytes / 1024:.2f} KB"
    elif size_in_bytes < 1024**3:
        return f"{size_in_bytes / (1024**2):.2f} MB"
    else:
        return f"{size_in_bytes / (1024**3):.2f} GB"

def list_home_subdirectory_sizes():
    """
    Lists the sizes of all subdirectories in the user's home directory.
    """
    home_dir = os.path.expanduser('~')
    print(f"Scanning subdirectories in: {home_dir}\n")

    try:
        with os.scandir(home_dir) as entries:
            for entry in entries:
                if entry.is_dir() and not entry.name.startswith('.'): # Exclude hidden directories
                    subdir_path = entry.path
                    print(f"Calculating size for: {subdir_path}")
                    size = get_directory_size(subdir_path)
                    print(f"  Size: {format_size(size)}\n")
    except OSError as e:
        print(f"Error accessing home directory: {e}")

def list_home_subdirectory_sizes_parallel():
    """
    Lists the sizes of all subdirectories in the user's home directory
    in parallel, including timing for each calculation and total execution time.
    """
    #script_start_time = time.time()
    home_dir = os.path.expanduser('~')
    print(f"Scanning subdirectories in: {home_dir}\n")

    subdirectories = []
    try:
        with os.scandir(home_dir) as entries:
            for entry in entries:
                if entry.is_dir() and not entry.name.startswith('.'): # Exclude hidden directories
                    subdirectories.append(entry.path)
    except OSError as e:
        print(f"Error accessing home directory: {e}")
        return

    # Using ThreadPoolExecutor for parallel processing
    # The ideal max_workers depends on your system and the nature of the task.
    # For I/O-bound tasks, a higher number than CPU cores can sometimes be beneficial.
    # We'll use a default of 4, but you can adjust it.
    max_workers = os.cpu_count() * 2 if os.cpu_count() else 4 
    print(f"Using a ThreadPoolExecutor with {max_workers} workers.\n")

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit each subdirectory size calculation as a separate task
        future_to_subdir = {executor.submit(get_directory_size, subdir): subdir for subdir in subdirectories}

        for future in as_completed(future_to_subdir):
            subdir_path = future_to_subdir[future]
            try:
                start_time = time.time() # This timing is for the *completion* of the task
                size = future.result()
                end_time = time.time()
                results[subdir_path] = (size, end_time - start_time)
            except Exception as exc:
                print(f"  {subdir_path} generated an exception: {exc}")
                results[subdir_path] = (0, 0) # Indicate an error or 0 size

    # Print results in a structured way
    print("\n--- Subdirectory Sizes and Times ---")
    for subdir_path in sorted(results.keys()):
        size, time_taken = results[subdir_path]
        print(f"  Directory: {subdir_path}")
        print(f"    Size: {format_size(size)}")
        print(f"    Time taken: {time_taken:.4f} seconds\n")

    #script_end_time = time.time()
    #print(f"Total script execution time: {script_end_time - script_start_time:.4f} seconds")

if __name__ == "__main__":
    script_start_time = time.time()
    list_home_subdirectory_sizes_parallel()
    #list_home_subdirectory_sizes() 
    script_end_time = time.time()
    print(f"Total script execution time: {script_end_time - script_start_time:.4f} seconds")