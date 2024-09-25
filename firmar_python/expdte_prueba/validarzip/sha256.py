import hashlib
import os
import glob

def sha256_file(file_path):
    # Create a SHA-256 hash object
    sha256_hash = hashlib.sha256()
    
    # Open the file in binary mode
    with open(file_path, "rb") as f:
        # Read the file in chunks
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    
    # Return the hexadecimal digest of the hash
    return sha256_hash.hexdigest()

def sha256_files_in_folder(folder_path):
    # List all PDF files in the folder
    file_paths = glob.glob(os.path.join(folder_path, "*.pdf"))
    
    hashes = {}
    for file_path in file_paths:
        hashes[file_path] = sha256_file(file_path)
    return hashes

# Example usage
folder_path = "./pdfs"
hashes = sha256_files_in_folder(folder_path)
for file_path, md5_hash in hashes.items():
    print(f"MD5 hash of {file_path}: \n {md5_hash}")