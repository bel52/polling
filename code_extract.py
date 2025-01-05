import os

def extract_code(directory, output_file):
    """
    Recursively extracts code from all files in a directory and sub-directories,
    excluding database files (.db), and writes it to a .txt file.
    """
    with open(output_file, 'w', encoding='utf-8') as out_file:
        for root, dirs, files in os.walk(directory):
            for file in files:
                # Skip database files or other binary-like files
                if file.endswith('.db'):
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        out_file.write(f"--- Start of {file_path} ---\n")
                        out_file.write(f.read())
                        out_file.write(f"\n--- End of {file_path} ---\n\n")
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")

if __name__ == "__main__":
    # Specify the directory to scan and the output file
    directory_to_scan = '.'  # Current directory
    output_file_name = 'all_code.txt'
    
    extract_code(directory_to_scan, output_file_name)
    print(f"Code from all files (excluding .db) has been saved to {output_file_name}")
