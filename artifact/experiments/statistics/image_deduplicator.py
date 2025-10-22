import os
import hashlib
import shutil

from PIL import Image

# Do not remove this import, it's required for AVIF support
# Install via `pip install pillow-avif-plugin`
import pillow_avif

# For websites like eventbrite, spotify, apartmenttherapy, goop, their valid images may not have extensions
# For rottentomatoes, such images don't exist in the dataset, but downloaded images may not have extensions
def is_without_extension_special(website_prefix, filename):
    match website_prefix:
        case "eventbrite":
            return filename.startswith("https___cdn.evbuc.com")
        case "spotify":
            return len(filename) == len("ab67616d000048515e052325a596b719c3f9e694")
        case "apartmenttherapy":
            return filename.startswith("at_")
        case "goop":
            return filename.startswith("open-uri")
        case "rottentomatoes":
            if len(filename) <= 4: return False
            return filename[3] == "." and filename[-1] == "="
        case "rakuten":
            return filename.__contains__('-swatch') or filename.endswith('-pdp')
        case _:
            return False

def is_file_calculated(website_prefix, file):
    extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.avif']
    return any(file.lower().endswith(ext) for ext in extensions) or is_without_extension_special(website_prefix, file)


def get_file_hash(file_path):
    """Calculate MD5 hash of file"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_image_hash(image_path, hash_size=8):
    """
    Calculate perceptual hash of image, effective for similar images of different sizes
    """
    try:
        with Image.open(image_path) as img:
            # Convert to grayscale
            img = img.convert('L')
            # Resize to fixed size so images of different dimensions can be compared
            img = img.resize((hash_size, hash_size), Image.LANCZOS)
            # Calculate average value
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            # Generate hash value
            bits = ''.join(['1' if pixel >= avg else '0' for pixel in pixels])
            # Convert to integer
            return int(bits, 2)
    except Exception as e:
        print(f"Error when processing {image_path}: {e}")
        return None

def hamming_distance(hash1, hash2):
    """
    Calculate Hamming distance between two hash values
    """
    return bin(hash1 ^ hash2).count('1')

def find_duplicate_images(test_id, directory, move_duplicates=False, similarity_threshold=0.01):
    """Find duplicate images, optionally move duplicates to separate folder"""
    print('-'*30)
    print(f"current dir: {directory}")

    # Current website name
    website_prefix = test_id.split('_')[0]
    
    # Create directory for saving duplicate images
    if move_duplicates:
        duplicates_dir = os.path.join(directory, "duplicate_images")
        os.makedirs(duplicates_dir, exist_ok=True)
    
    # Collect all image files
    image_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if is_file_calculated(website_prefix, file):
                image_files.append(os.path.join(root, file))
    
    print(f"Found {len(image_files)} images")
    
    # Store image hash values
    images_by_hash = {}
    exact_duplicates = {}  # Exact duplicates based on file hash
    
    # First pass: check for identical files (based on file hash)
    for img_path in image_files:
        file_hash = get_file_hash(img_path)
        if file_hash in exact_duplicates:
            exact_duplicates[file_hash].append(img_path)
        else:
            exact_duplicates[file_hash] = [img_path]
    
    # Process identical files
    exact_dup_count = 0
    for file_hash, paths in exact_duplicates.items():
        if len(paths) > 1:
            exact_dup_count += len(paths) - 1
            # Keep the first one, move or print the rest
            for dup_path in paths[1:]:
                if move_duplicates:
                    dest = os.path.join(duplicates_dir, os.path.basename(dup_path))
                    shutil.move(dup_path, dest)
                    print(f"Move duplicate file {dup_path} -> {dest}")
                else:
                    print(f"Duplicate files: {paths[0]} and {dup_path}")
    
    print(f"Discovered {exact_dup_count} exact duplicate files")
    
    # Second pass: check for visually similar images (for already processed files)
    content_dup_count = 0
    # Re-collect images that haven't been moved
    remaining_images = []
    for root, _, files in os.walk(directory):
        if "duplicate_images" in root:
            continue
        for file in files:
            if is_file_calculated(website_prefix, file):
                remaining_images.append(os.path.join(root, file))
    
    for img_path in remaining_images:
        img_hash = get_image_hash(img_path)
        if img_hash is None: continue
            
        # Check if there are similar images
        is_similar = False
        similar_img = None
        
        for existing_hash, existing_path in images_by_hash.items():
            if existing_hash is None: continue

            # Calculate distance between hash values, smaller distance means more similar
            distance = hamming_distance(img_hash, existing_hash)
            if distance <= similarity_threshold:
                is_similar = True
                similar_img = existing_path
                print('--similar--', distance)
                break
                
        if is_similar:
            content_dup_count += 1
            if move_duplicates:
                dest = os.path.join(duplicates_dir, os.path.basename(img_path))
                shutil.move(img_path, dest)
                print(f"Move content similar file {img_path} -> {dest} (similar with {similar_img})")
            else:
                print(f"Similar files: {similar_img} and {img_path}")
        else:
            images_by_hash[img_hash] = img_path
    
    print(f"Discovered {content_dup_count} similar files based on content")
    print(f"Totally {exact_dup_count + content_dup_count} similar files found")
    print('-'*30)