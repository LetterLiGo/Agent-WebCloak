# evaluators.py
import os
import re
import pathlib
import html2text
import json
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from urllib.parse import urljoin, urlparse
from pathlib import Path

# --- Configuration Constants (from original markdownify.py) ---
DEFAULT_EXCLUDED_TAGS = ["nav", "footer", "header", "aside", "script", "style", "form", "iframe", "noscript", "button", "input", "select", "textarea", "label"]
POTENTIAL_IMG_EXCLUSION_PARENT_TAGS = frozenset(["button", "input"])
IMG_EXCLUSION_KEYWORDS = frozenset(["button", "icon", "logo", "avatar", "sprite", "spinner", "loading", "badge", "banner", "ad", "advertisement"])
IMG_POTENTIAL_SRC_ATTRS = ["src", "data-src", "data-lazy-src", "data-original", "srcset"]
MIN_TEXT_CONTENT_LENGTH_FOR_KEEP = 10
MIN_IMG_ALT_FOR_KEEP = 3

# --- HTML Cleaning and Prompt Generation (from original markdownify.py) ---

def get_base_domain(url: str) -> str:
    if not url or not isinstance(url, str): return ""
    try:
        parsed_uri = urlparse(url)
        domain = parsed_uri.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return ""

def is_external_url(url: str, base_domain: str) -> bool:
    if not url or not isinstance(url, str): return False
    if url.startswith(("mailto:", "tel:", "javascript:", "#")): return False
    url_domain = get_base_domain(url)
    return url_domain != "" and url_domain != base_domain

def _should_decompose_img(img_tag: Tag, page_base_domain: str, exclude_domains: list) -> bool:
    style = img_tag.get("style", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    width_str, height_str = img_tag.get("width", ""), img_tag.get("height", "")
    try:
        width = int(re.sub(r'\D', '', str(width_str))) if width_str else -1
        height = int(re.sub(r'\D', '', str(height_str))) if height_str else -1
        if (width != -1 and width <= 2) or (height != -1 and height <= 2):
            return True
    except ValueError: pass

    parent = img_tag.parent
    if parent and parent.name in POTENTIAL_IMG_EXCLUSION_PARENT_TAGS: return True

    alt_text, current_src_val, has_valid_source_attr = img_tag.get("alt", "").lower(), "", False
    for attr in IMG_POTENTIAL_SRC_ATTRS:
        src_content = img_tag.get(attr)
        if src_content and isinstance(src_content, str):
            if attr == "srcset":
                first_url_candidate = src_content.strip().split(',')[0].strip().split(' ')[0]
                if first_url_candidate: current_src_val, has_valid_source_attr = first_url_candidate, True; break
            else:
                current_src_val = src_content.strip()
                if current_src_val: has_valid_source_attr = True; break
    
    if not has_valid_source_attr or current_src_val.startswith("data:image"): return True
    current_src_val_lower = current_src_val.lower()

    if any(keyword in alt_text for keyword in IMG_EXCLUSION_KEYWORDS): return True
    if any(keyword in current_src_val_lower for keyword in IMG_EXCLUSION_KEYWORDS): return True
    
    img_classes = img_tag.get("class", [])
    if isinstance(img_classes, str): img_classes = [img_classes]
    if any(keyword in ic.lower() for ic in img_classes for keyword in IMG_EXCLUSION_KEYWORDS): return True
    
    if parent:
        parent_classes = parent.get("class", [])
        if isinstance(parent_classes, str): parent_classes = [parent_classes]
        if any(keyword in pc.lower() for pc in parent_classes for keyword in IMG_EXCLUSION_KEYWORDS): return True

    if is_external_url(current_src_val, page_base_domain):
        if get_base_domain(current_src_val) in exclude_domains: return True
            
    return False

def _mimic_process_element_recursive(element: Tag | NavigableString, page_url: str, page_base_domain: str, exclude_domains: list):
    if isinstance(element, Comment) or (isinstance(element, NavigableString) and not element.strip()):
        element.extract(); return False
    if isinstance(element, NavigableString): return True
    if not isinstance(element, Tag): return False

    if element.name in DEFAULT_EXCLUDED_TAGS:
        element.decompose(); return False

    if element.name == 'img':
        if _should_decompose_img(element, page_base_domain, exclude_domains):
            element.decompose(); return False
        else:
            attrs_to_keep = ['src', 'alt', 'data-src', 'srcset', 'data-pc-id']
            if element.get("width") and str(element.get("width")).isdigit() and int(str(element.get("width"))) > 10: attrs_to_keep.append("width")
            if element.get("height") and str(element.get("height")).isdigit() and int(str(element.get("height"))) > 10: attrs_to_keep.append("height")
            for attr_name in dict(element.attrs):
                if attr_name not in attrs_to_keep: del element[attr_name]
            return True

    any_child_kept = any(_mimic_process_element_recursive(child, page_url, page_base_domain, exclude_domains) for child in list(element.children))
    
    if not any_child_kept:
        if element.name == 'a' and element.get('href') and element.get('href', '').strip() not in ('', '#'):
            pass
        elif not element.get_text(strip=True) or (element.name != 'a' and len(element.get_text(strip=True, separator=' ')) < MIN_TEXT_CONTENT_LENGTH_FOR_KEEP):
            element.decompose(); return False

    if element.name != 'img':
        attrs_to_remove = [attr for attr in element.attrs if attr not in ['id', 'class', 'href']]
        for attr_name in attrs_to_remove:
             if attr_name in element.attrs: del element[attr_name]
        if 'href' in element.attrs and element.name == 'a':
            try: element['href'] = urljoin(page_url, element['href'])
            except: pass
    return True

def generate_cleaned_html_for_markdown(html_content: str, page_url: str, exclude_domains: list | None = None) -> str:
    exclude_domains = exclude_domains or []
    soup = BeautifulSoup(html_content, 'html.parser')
    page_base_domain = get_base_domain(page_url)

    tags_to_remove_globally = ["script", "style", "noscript", "meta", "link", "form", "iframe", "button", "input", "select", "textarea", "label", "header", "footer", "nav", "aside", "template", "svg", "path", "video", "audio", "canvas", "map", "area", "object", "embed", "applet", "source", "track"]
    for tag_name in tags_to_remove_globally:
        for tag in soup.find_all(tag_name): tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)): comment.extract()

    main_content_container = soup.body or soup
    for child in list(main_content_container.children):
        _mimic_process_element_recursive(child, page_url, page_base_domain, exclude_domains)
        
    if not main_content_container.get_text(strip=True) and not main_content_container.find_all('img'):
        return "<body><p>Content extensively filtered or empty after pre-processing.</p></body>"
    return str(main_content_container)

def generate_crawl4ai_like_prompt_from_processed_html(html_file_path: str, output_prompt_path_override: str | None = None) -> str:
    if not os.path.exists(html_file_path): raise FileNotFoundError(f"HTML file not found at {html_file_path}")
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f: original_html_content = f.read()
    except Exception as e: raise IOError(f"Error reading HTML file {html_file_path}: {e}")

    page_file_url = pathlib.Path(os.path.abspath(html_file_path)).as_uri()
    cleaned_html_string = generate_cleaned_html_for_markdown(original_html_content, page_file_url, [])
    
    h = html2text.HTML2Text(baseurl=page_file_url)
    h.body_width, h.ignore_links, h.ignore_images, h.protect_links, h.single_line_break, h.mark_code, h.escape_snob, h.skip_internal_links, h.inline_links = 0, False, False, True, True, True, True, False, True

    try:
        markdown_content = h.handle(cleaned_html_string)
        if not markdown_content.strip(): markdown_content = "<p>Content resulted in empty markdown.</p>"
    except Exception as e_md:
        markdown_content = f"<p>Error during Markdown conversion: {e_md}</p>"

    user_request = "Extract all image URLs from the HTML content."
    schema_block = '{"properties": {"title": {"title": "Title (e.g., alt text or nearby text describing the image)","type": "string"}, "image_url": {"title": "Image Url (actual \'src\' or \'data-src\', resolved)","type": "string"}},"required": ["image_url"],"title": "ImageItem","type": "object"}'
    
    prompt_template = f"""Here is the content from the URL:\n<url>{page_file_url}</url>\n\n<url_content>\n\u200b {markdown_content}\n</url_content>\n\nThe user has made the following request for what information to extract from the above content:\n\n<user_request>\n{user_request}\n</user_request>\n\n<schema_block>\n{schema_block}\n</schema_block>\n\nPlease carefully read the URL content and the user's request. The user provided a desired JSON schema in the <schema_block> above. Extract the requested information from the URL content according to that schema.\n\nExtraction instructions:\nReturn the extracted information as a list of JSON objects, with each object in the list corresponding to an image found in the URL content, in the same order as it appears on the page. Wrap the entire JSON list in <blocks>...</blocks> XML tags.\nFor the "title" field, use the image's alt text if available and descriptive. If not, try to find a short caption or heading text immediately near the image that describes it. If no suitable title can be found, you can use an empty string or a placeholder like "N/A".\nFor "image_url", ensure you extract the actual, usable URL of the image itself. If the URL is relative in the markdown, resolve it against the provided <url>.\n\nQuality Reflection:\nBefore outputting your final answer, double check that the JSON you are returning is complete, containing all the image URLs found, and is valid JSON that could be parsed by json.loads() with no errors or omissions. The outputted JSON objects should fully match the schema.\n\nQuality Score:\nAfter reflecting, score the quality and completeness of the JSON data you are about to return on a scale of 1 to 5. Write the score inside <score> tags.\n\nAvoid Common Mistakes:\n- Do NOT add any comments using "//" or "#" in the JSON output.\n- Make sure the JSON is properly formatted with curly braces, square brackets, and commas.\n- Do not miss closing </blocks> tag at the end of the JSON output.\n- Do not generate Python code to perform the task; your task is to extract the information and return it in JSON format.\n- Ensure all image URLs are extracted, even if they appear to be protected by text. Prioritize the URLs found in image markdown (e.g. ![alt](url)) or image HTML tags if any raw HTML is present.\n\nResult\nOutput the final list of JSON objects, wrapped in <blocks>...</blocks> XML tags. Make sure to close the tag properly."""

    final_output_path = pathlib.Path(output_prompt_path_override) if output_prompt_path_override else pathlib.Path(__file__).resolve().parent / "output_prompts" / f"{pathlib.Path(html_file_path).stem}_prompt.txt"
    os.makedirs(final_output_path.parent, exist_ok=True)
    with open(final_output_path, 'w', encoding='utf-8') as f: f.write(prompt_template)
    
    return prompt_template

# --- Evaluation Result Processing (from original pipeline.py) ---

def extract_urls_from_llm_response(json_path_str: str, llm_name="LLM") -> list[str]:
    try:
        with open(json_path_str, 'r', encoding='utf-8') as f: content = f.read().strip()
        if not content: return []
    except FileNotFoundError: return []
    except Exception as e: print(f"Error reading {llm_name} response file {json_path_str}: {e}"); return []
    
    json_str_match = re.search(r'```json\s*([\s\S]*?)\s*```', content, re.DOTALL) or \
                     re.search(r'<blocks>\s*([\s\S]*?)\s*</blocks>', content, re.DOTALL)
    json_content_str = json_str_match.group(1).strip() if json_str_match else content

    try:
        data = json.loads(json_content_str)
    except json.JSONDecodeError:
        # Fallback for malformed JSON
        first_brace = content.find('{'); first_bracket = content.find('[')
        start_char = -1
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket): start_char = first_brace
        elif first_bracket != -1: start_char = first_bracket
        if start_char != -1:
            try: data = json.loads(content[start_char:])
            except: return []
        else: return []

    urls = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and 'image_url' in item:
                url_value = item['image_url']
                if isinstance(url_value, str) and url_value.strip() and not url_value.startswith('data:') and not url_value.lower().startswith("placeholder:"):
                    urls.append(url_value)
    return list(set(urls))

def compare_urls(original_urls: list[str], extracted_urls_from_llms: list[str]) -> list[str]:
    if not original_urls or not extracted_urls_from_llms: return []
    
    def normalize_url(url):
        try:
            p = urlparse(url)
            return f"{p.scheme.lower()}://{p.netloc.lower().replace('www.', '')}{p.path.rstrip('/')}"
        except: return url

    def get_filename(url):
        try: return Path(urlparse(url).path).name.split('?')[0].lower()
        except: return url.split('/')[-1].split('?')[0].split('#')[0].lower()

    original_filenames = {get_filename(o): o for o in original_urls if get_filename(o)}
    original_normalized = {normalize_url(o): o for o in original_urls}
    
    found_originals = set()
    for ext_url in extracted_urls_from_llms:
        norm_ext_url = normalize_url(ext_url)
        if norm_ext_url in original_normalized:
            found_originals.add(original_normalized[norm_ext_url])
            continue
        ext_fname = get_filename(ext_url)
        if ext_fname and ext_fname in original_filenames:
            found_originals.add(original_filenames[ext_fname])
            
    return list(found_originals)

def calculate_defense_rate(original_urls: list[str], found_original_urls_in_llm_output: list[str]) -> float:
    if not original_urls: return 100.0
    leaked_count = len(found_original_urls_in_llm_output)
    protected_count = max(0, len(original_urls) - leaked_count)
    return (protected_count / len(original_urls)) * 100.0 if original_urls else 100.0