import asyncio
import aiohttp
import os
import shutil

from urllib.parse import urlparse


async def save_images(data_urls, output_dir, test_id, test_case_url):
    # Create images directory
    images_dir = os.path.join(output_dir, f"{test_id}")
    # Remove all files inside the directory first
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)
    os.makedirs(images_dir)

    print(f"Saving {len(data_urls)} images to {images_dir}...")

    # Create async tasks for downloading all images
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, image_url in enumerate(data_urls):
            # Ensure the URL is absolute
            image_file_name = image_url.rsplit("/", 1)[-1]
            if image_url.startswith('http://localhost:633'):
                image_url = './index_files/' + image_url.split('/index_files/')[1]
            if image_url.startswith("./index_files/"):
                image_url = os.path.join(test_case_url.replace('index.html', '').replace('_edited.html', '').replace('_protected.html', ''), image_url[2:])

            # Get file extension from URL or default to .jpg
            parsed_url = urlparse(image_url)
            file_ext = os.path.splitext(parsed_url.path)[1]
            if not file_ext:
                file_ext = ".jpg"

            # Create filename
            filepath = os.path.join(images_dir, image_file_name)

            # Add download task
            tasks.append(download_image(session, image_url, filepath, i))

        # Execute all downloads concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful downloads
        success_count = sum(1 for r in results if r is True)
        print(f"Downloaded {success_count} images successfully")

        return images_dir, success_count


async def download_image(session, url, filepath, index):
    try:
        if '\\(' in url:
            # Handle special case for URLs with parentheses
            url = url.replace('\\(', '(').replace('\\)', ')')
        if url.startswith('file://'):
            # Handle local file URLs
            local_path = urlparse(url).path
            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    with open(filepath, 'wb') as out_f:
                        out_f.write(f.read())
                print(f"Copied image {index} to {filepath}")
                return True
            else:
                print(f"Local file not found: {local_path}")
                return False
        async with session.get(url) as response:
            if response.status == 200:
                with open(filepath, 'wb') as f:
                    f.write(await response.read())
                print(f"Downloaded image {index} to {filepath}")
                return True
            else:
                print(f"Failed to download image {index}: HTTP {response.status}")
                print(url)
                return False
    except Exception as e:
        print(f"Error downloading image {index}: {str(e)}")
        return False