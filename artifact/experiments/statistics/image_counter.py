import os
import shutil

from .image_deduplicator import find_duplicate_images, is_file_calculated, get_image_hash, \
    hamming_distance


def get_image_statistics(test_id, orig_dataset_dir, orig_downloaded_dir):
    """
    :param test_id:
    :param orig_dataset_dir:
    :param orig_downloaded_dir:
    :return: ground_truth_count: actual image count, scraped_total_count: scraped image count, correctly_scraped_count: correctly scraped image count, precision: precision rate, recall: recall rate
    """
    website_prefix = test_id.split('_')[0]

    tmp_dataset_dir = os.path.join(orig_dataset_dir, 'tmp')
    try:
        shutil.rmtree(tmp_dataset_dir)
    except FileNotFoundError:
        pass
    os.makedirs(tmp_dataset_dir, exist_ok=True)

    # Copy all files from orig_dataset_dir to tmp_dataset_dir
    print(f"Temporarily copying files from {orig_dataset_dir} to {tmp_dataset_dir}")
    for item in os.listdir(orig_dataset_dir):
        item_path = os.path.join(orig_dataset_dir, item)
        if os.path.isfile(item_path):
            shutil.copy2(item_path, tmp_dataset_dir)

    tmp_downloaded_dir = os.path.join(orig_downloaded_dir, 'tmp')
    try:
        shutil.rmtree(tmp_downloaded_dir)
    except FileNotFoundError:
        pass
    os.makedirs(tmp_downloaded_dir, exist_ok=True)

    # Copy all files from downloaded_dir to tmp_downloaded_dir
    print(f"Temporarily copying files from {orig_downloaded_dir} to {tmp_downloaded_dir}")
    for item in os.listdir(orig_downloaded_dir):
        item_path = os.path.join(orig_downloaded_dir, item)
        if os.path.isfile(item_path):
            shutil.copy2(item_path, tmp_downloaded_dir)

    find_duplicate_images(test_id, tmp_dataset_dir, True, 0.01)
    find_duplicate_images(test_id, tmp_downloaded_dir, True, 0.01)

    ground_truth_count = sum(
        1 for f in os.listdir(tmp_dataset_dir)
        if is_file_calculated(website_prefix, f)
    )

    scraped_total_count = sum(
        1 for f in os.listdir(tmp_downloaded_dir)
        if not f == 'duplicate_images'
    )

    correctly_scraped_count = check_similar_images(website_prefix, tmp_dataset_dir, tmp_downloaded_dir, 0.01)

    precision = correctly_scraped_count / scraped_total_count if scraped_total_count > 0 else 0
    recall = correctly_scraped_count / ground_truth_count if ground_truth_count > 0 else 0

    return ground_truth_count, scraped_total_count, correctly_scraped_count, precision, recall

def check_similar_images(website_prefix, dir1, dir2, threshold=0.01):
    """if len(sys.argv) < 3:
        print("Usage: python image_similarity_counter.py <directory1> <directory2> [similarity threshold]")
        sys.exit(1)

    dir1 = sys.argv[1]
    dir2 = sys.argv[2]"""
    """try:
        threshold = int(sys.argv[3]) if len(sys.argv) >= 4 else 10
    except ValueError:
        print("Threshold must be an integer")
        sys.exit(1)"""

    if not os.path.isdir(dir1) or not os.path.isdir(dir2):
        print("Error: Both arguments must be valid directories")
        return 0

    # Collect hashes for all images in the second directory
    print(f"Scanning images in directory {dir2}...")
    hashes2 = []
    for item in os.listdir(dir2):
        if item == "duplicate_images": continue
        img_hash = get_image_hash(os.path.join(dir2, item))
        hashes2.append((item, img_hash))
    print(f"Collected hashes for {len(hashes2)} images")

    similar_count = 0
    # Compare each image in the first directory
    print(f"Comparing images in directory {dir1} with directory {dir2}...")
    for f in os.listdir(dir1):
        # Right half: As images from some websites may not have extensions
        if is_file_calculated(website_prefix, f):
            path1 = os.path.join(dir1, f)
            h1 = get_image_hash(path1)
            if h1 is None:
                continue
            # If downloaded, compare with all hashes in the second directory
            # If copied from local, just compare the file names
            if any(f == f2 for f2, _ in hashes2):
                similar_count += 1
            elif any(hamming_distance(h1, h2) <= threshold for _, h2 in hashes2 if h2 is not None):
                similar_count += 1

    print(f"In directory '{dir1}', {similar_count} images are similar to images in directory '{dir2}' (threshold: {threshold})")
    return similar_count