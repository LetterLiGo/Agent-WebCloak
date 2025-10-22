import os
import json
import re
import shutil
import urllib.parse
import sys
from contextlib import contextmanager
from PIL import Image
import imagehash

# --- Configuration Constants ---
BASE_PROCESSING_DIR = "."
INPUT_JSON_SUBDIR = "json"
INPUT_JSON_DIR = os.path.join(BASE_PROCESSING_DIR, INPUT_JSON_SUBDIR)

SOURCE_DATA_DIR = "../../../dataset"
TARGET_BASE_URI_PREFIX = f"file://{os.path.abspath(SOURCE_DATA_DIR)}/"

OUTPUT_JSON_SUBDIR = "json_transfer"
OUTPUT_JSON_DIR = os.path.join(BASE_PROCESSING_DIR, OUTPUT_JSON_SUBDIR)
OUTPUT_IMAGE_PARENT_DIR = BASE_PROCESSING_DIR

GROUND_TRUTH_DIR = "../../../dataset"

# --- Main Script Logic ---

@contextmanager
def suppress_stdout():
    """A context manager to suppress standard output."""
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout

def prepare_input_json_files(base_dir, json_subdir):
    """
    Moves all '*_image_urls.json' files from the base directory
    into the specified JSON subdirectory, creating it if necessary.
    """
    target_json_path = os.path.join(base_dir, json_subdir)
    if not os.path.exists(target_json_path):
        print(f"Creating directory: {target_json_path}")
        os.makedirs(target_json_path, exist_ok=True)
    elif not os.path.isdir(target_json_path):
        print(f"Error: {target_json_path} exists but is not a directory. Cannot proceed.")
        return False

    moved_count = 0
    print(f"Scanning {base_dir} for JSON files to move to {target_json_path}...")
    for filename in os.listdir(base_dir):
        if filename.endswith("_image_urls.json") and os.path.isfile(os.path.join(base_dir, filename)):
            source_file = os.path.join(base_dir, filename)
            destination_file = os.path.join(target_json_path, filename)
            try:
                shutil.move(source_file, destination_file)
                print(f"  Moved: {filename} to {json_subdir}/")
                moved_count += 1
            except Exception as e:
                print(f"  Error moving {filename}: {e}")

    if moved_count > 0:
        print(f"Successfully moved {moved_count} JSON files to {target_json_path}.")
    else:
        print(f"No '*_image_urls.json' files found directly in {base_dir} to move, or they were already moved.")
    return True

def parse_site_and_id_from_filename(json_filename_basename):
    """
    Parses the site name and document ID from a JSON filename.
    """
    parts = json_filename_basename.split('_', 2)
    if len(parts) >= 2:
        site_name = parts[0]
        doc_id = parts[1]
        if site_name and doc_id:
            return site_name, doc_id

    print(f"Warning: Unable to parse site name and ID from '{json_filename_basename}'.")
    return None, None

def transform_url(original_url, site_name, doc_id):
    """
    Transforms a single URL to a standardized local file URI.
    """
    relative_prefix = "./index_files/"
    if original_url.startswith(relative_prefix):
        filename_part = original_url[len(relative_prefix):]
        if filename_part and not filename_part.startswith('/') and '..' not in filename_part:
            safe_filename = urllib.parse.quote(filename_part)
            return f"{TARGET_BASE_URI_PREFIX}{site_name}/{doc_id}/index_files/{safe_filename}"
        else:
            return original_url

    try:
        parsed_uri = urllib.parse.urlparse(original_url)
    except Exception:
        return original_url

    if parsed_uri.scheme == 'http' and (parsed_uri.hostname in ('localhost', '127.0.0.1')):
        expected_path_prefix = "/index_files/"
        if parsed_uri.path.startswith(expected_path_prefix):
            filename_part = parsed_uri.path[len(expected_path_prefix):]
            if filename_part and not filename_part.startswith('/') and '..' not in filename_part:
                safe_filename = urllib.parse.quote(filename_part)
                return f"{TARGET_BASE_URI_PREFIX}{site_name}/{doc_id}/index_files/{safe_filename}"
            else:
                return original_url

    return original_url

def process_json_file(json_file_path):
    """
    Processes a single JSON file by transforming its URLs and copying local image files.
    """
    print(f"\nProcessing JSON file: {json_file_path}")
    json_full_filename = os.path.basename(json_file_path)
    base_name = os.path.splitext(json_full_filename)[0]
    site_name, doc_id = parse_site_and_id_from_filename(base_name)

    if not site_name or not doc_id:
        print(f"Skipping file {json_full_filename} due to parsing error.")
        return

    image_folder_name = base_name.replace("_image_urls", "")

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            original_urls = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing {json_full_filename}: {e}. Skipped.")
        return

    transformed_urls = [transform_url(url, site_name, doc_id) for url in original_urls if isinstance(url, str)]

    os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)
    output_json_path = os.path.join(OUTPUT_JSON_DIR, json_full_filename)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(transformed_urls, f, indent=4)
    print(f"  Successfully saved transformed URLs to: {output_json_path}")

    destination_image_folder = os.path.join(OUTPUT_IMAGE_PARENT_DIR, image_folder_name)
    os.makedirs(destination_image_folder, exist_ok=True)

    copied_count = 0
    for url_to_copy in transformed_urls:
        if isinstance(url_to_copy, str) and url_to_copy.startswith("file:///"):
            try:
                source_path = urllib.parse.unquote(urllib.parse.urlparse(url_to_copy).path)
                if os.name == 'nt' and source_path.startswith('/'):
                    source_path = source_path[1:]
                
                if os.path.exists(source_path):
                    shutil.copy2(source_path, destination_image_folder)
                    copied_count += 1
            except Exception as e:
                print(f"    Error copying file from URI '{url_to_copy}': {e}")
    print(f"  Copied {copied_count} files to {destination_image_folder}.")

def main():
    """Main execution function."""
    if not os.path.isdir(BASE_PROCESSING_DIR):
        print(f"Error: Base processing directory '{BASE_PROCESSING_DIR}' not found.")
        return

    if not prepare_input_json_files(BASE_PROCESSING_DIR, INPUT_JSON_SUBDIR):
        print("File preparation failed. Terminating.")
        return

    files_to_process = [os.path.join(INPUT_JSON_DIR, f) for f in os.listdir(INPUT_JSON_DIR) if f.endswith("_image_urls.json")]
    for file_path in files_to_process:
        process_json_file(file_path)

    print("\n========================================================")
    print("Starting image statistics calculation...")
    check_html_files_and_image_stats(BASE_PROCESSING_DIR, GROUND_TRUTH_DIR)
    print("\nAll processing completed.")

# =================================================================================
# ===== MERGED IMAGE PROCESSING AND STATISTICS FUNCTIONS (from image_deduplicator & image_counter)
# =================================================================================

def get_image_hash(image_path):
    """Calculates the perceptual hash of an image."""
    try:
        with Image.open(image_path) as img:
            return imagehash.phash(img)
    except Exception:
        return None

def hamming_distance(hash1, hash2):
    """Calculates the Hamming distance between two hashes."""
    if hash1 is None or hash2 is None:
        return float('inf')
    return hash1 - hash2

def is_file_calculated(website_prefix, filename):
    """
    Determines if a file should be treated as an image for statistics.
    This simple version tries to open it as an image.
    """
    # A more robust check could be added here based on website-specific naming conventions.
    common_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    if any(filename.lower().endswith(ext) for ext in common_extensions):
        return True
    # Fallback for files without extensions: try to open them.
    try:
        with Image.open(filename) as img:
            # Verify it's not a tiny pixel, which might be a tracker
            return img.width > 10 and img.height > 10
    except Exception:
        return False

def find_duplicate_images(test_id, directory, move_duplicates=True, threshold=0.01):
    """Finds and optionally moves duplicate images in a directory."""
    hashes = {}
    image_files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    
    for filename in image_files:
        path = os.path.join(directory, filename)
        img_hash = get_image_hash(path)
        if img_hash:
            hashes[filename] = img_hash

    duplicates = set()
    filenames = list(hashes.keys())
    for i in range(len(filenames)):
        for j in range(i + 1, len(filenames)):
            f1 = filenames[i]
            f2 = filenames[j]
            if f1 in duplicates or f2 in duplicates:
                continue
            
            dist = hamming_distance(hashes[f1], hashes[f2])
            if dist <= threshold * 64: # phash is 64-bit, threshold is a percentage
                duplicates.add(f2)

    if move_duplicates and duplicates:
        duplicate_dir = os.path.join(directory, "duplicate_images")
        os.makedirs(duplicate_dir, exist_ok=True)
        print(f"Moving {len(duplicates)} duplicate images to {duplicate_dir}")
        for f in duplicates:
            try:
                shutil.move(os.path.join(directory, f), duplicate_dir)
            except FileNotFoundError:
                pass # Already moved

def check_similar_images(website_prefix, dir1, dir2, threshold=0.01):
    """Counts how many images in dir1 have a similar match in dir2."""
    if not (os.path.isdir(dir1) and os.path.isdir(dir2)):
        return 0

    hashes2 = {f: get_image_hash(os.path.join(dir2, f)) for f in os.listdir(dir2) if f != "duplicate_images"}
    
    similar_count = 0
    for f1 in os.listdir(dir1):
        path1 = os.path.join(dir1, f1)
        if not is_file_calculated(website_prefix, path1):
            continue

        h1 = get_image_hash(path1)
        if h1 is None:
            continue
        
        # Check for similarity
        found_match = False
        for f2, h2 in hashes2.items():
            if f1 == f2 or hamming_distance(h1, h2) <= threshold * 64:
                similar_count += 1
                found_match = True
                break
        
    print(f"Found {similar_count} images in '{os.path.basename(dir1)}' that are similar to images in '{os.path.basename(dir2)}'")
    return similar_count

def get_image_statistics(test_id, orig_dataset_dir, orig_downloaded_dir):
    """Calculates precision and recall for scraped images after deduplication."""
    website_prefix = test_id.split('_')[0]

    # Create temporary directories for processing
    tmp_dataset_dir = os.path.join(orig_dataset_dir, 'tmp')
    if os.path.exists(tmp_dataset_dir): shutil.rmtree(tmp_dataset_dir)
    os.makedirs(tmp_dataset_dir)
    for item in os.listdir(orig_dataset_dir):
        if os.path.isfile(os.path.join(orig_dataset_dir, item)):
            shutil.copy2(os.path.join(orig_dataset_dir, item), tmp_dataset_dir)

    tmp_downloaded_dir = os.path.join(orig_downloaded_dir, 'tmp')
    if os.path.exists(tmp_downloaded_dir): shutil.rmtree(tmp_downloaded_dir)
    os.makedirs(tmp_downloaded_dir)
    for item in os.listdir(orig_downloaded_dir):
        if os.path.isfile(os.path.join(orig_downloaded_dir, item)):
            shutil.copy2(os.path.join(orig_downloaded_dir, item), tmp_downloaded_dir)

    # Deduplicate images in both directories
    find_duplicate_images(test_id, tmp_dataset_dir, True, 0.01)
    find_duplicate_images(test_id, tmp_downloaded_dir, True, 0.01)

    ground_truth_count = sum(1 for f in os.listdir(tmp_dataset_dir) if is_file_calculated(website_prefix, os.path.join(tmp_dataset_dir, f)))
    scraped_total_count = sum(1 for f in os.listdir(tmp_downloaded_dir) if f != 'duplicate_images')
    correctly_scraped_count = check_similar_images(website_prefix, tmp_dataset_dir, tmp_downloaded_dir, 0.01)

    precision = correctly_scraped_count / scraped_total_count if scraped_total_count > 0 else 0
    recall = correctly_scraped_count / ground_truth_count if ground_truth_count > 0 else 0

    # Clean up temp directories
    shutil.rmtree(tmp_dataset_dir)
    shutil.rmtree(tmp_downloaded_dir)

    return ground_truth_count, scraped_total_count, correctly_scraped_count, precision, recall

def check_html_files_and_image_stats(scan_directory_path, ground_truth_images_dir):
    """Calculates image statistics for all relevant subdirectories."""
    print(f"\n--- Image Statistics Calculation ---")
    total_gt, total_scraped, total_correct = 0, 0, 0
    num_cases = 0

    for item_name in os.listdir(scan_directory_path):
        item_path = os.path.join(scan_directory_path, item_name)
        if not os.path.isdir(item_path) or item_name in (INPUT_JSON_SUBDIR, OUTPUT_JSON_SUBDIR, "duplicate_images"):
            continue
        
        site_name, doc_id = parse_site_and_id_from_filename(item_name)
        if not (site_name and doc_id):
            continue

        gt_dir = os.path.join(ground_truth_images_dir, site_name, doc_id)
        if not os.path.isdir(gt_dir):
            print(f"  Warning: Ground truth directory not found for '{item_name}'. Skipping.")
            continue

        print(f"\n  Calculating stats for: {item_name}")
        try:
            stats = get_image_statistics(item_name, gt_dir, item_path)
            if stats:
                gt_count, scraped_count, correct_count, precision, recall = stats
                print(f"    Stats: GT={gt_count}, Scraped={scraped_count}, Correct={correct_count}, Precision={precision:.4f}, Recall={recall:.4f}")
                total_gt += gt_count
                total_scraped += scraped_count
                total_correct += correct_count
                num_cases += 1
        except Exception as e:
            print(f"    Error calculating statistics for '{item_name}': {e}")

    if num_cases > 0:
        overall_precision = total_correct / total_scraped if total_scraped > 0 else 0
        overall_recall = total_correct / total_gt if total_gt > 0 else 0
        print("\n--- Aggregated Image Statistics ---")
        print(f"Total cases processed: {num_cases}")
        print(f"Overall Precision: {overall_precision:.4f}")
        print(f"Overall Recall: {overall_recall:.4f}")
    print("--- End of Image Statistics ---")


if __name__ == "__main__":
    main()