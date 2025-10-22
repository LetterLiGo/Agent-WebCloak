import os
import re
import time
import glob
import google.generativeai as genai

# --- Configuration ---
# The script will automatically find the latest LLM log file in the current directory.
OUTPUT_DIRECTORY = "generated_scripts"
OUTPUT_FILE_SUFFIX = ".py"

# Reads API key from environment variables for consistency and security.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = 'gemini-2.5-pro-preview-03-25' 

LLM_PROMPT = """You are an expert code cleaner. Parse the Python code from the following log segment.
The code is intended for web scraping. If you see obvious errors that would prevent it from running (e.g., syntax errors, incorrect variable names), please make the minimal corrections necessary.
Return ONLY the raw Python code. Do not include any explanations, comments about your changes, or markdown formatting like ```python ... ```."""

# --- Helper Functions ---
def strip_markdown_code_block(code_string):
    """Removes markdown code block delimiters from a string."""
    if code_string is None: return ""
    match = re.match(r"^```(?:python\n)?(.*?)\n?```$", code_string, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else code_string.strip()

def get_code_from_llm(log_content_for_llm):
    """Sends content to the Gemini API and returns the processed code."""
    print("    Calling Gemini API to extract and clean code...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(LLM_PROMPT + "\n\n--- LOG SEGMENT ---\n" + log_content_for_llm)
        cleaned_code = strip_markdown_code_block(response.text)
        print(f"    LLM response received (length: {len(cleaned_code)} chars).")
        return cleaned_code
    except Exception as e:
        print(f"    Error calling Gemini API: {e}")
        return f"# LLM API Error: {e}"

def parse_log_and_generate_scripts(log_path, output_dir):
    """Parses the log file, extracts segments, calls LLM, and writes output scripts."""
    print(f"Starting to parse log file: {log_path}")
    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            log_content_full = f.read()
    except Exception as e:
        print(f"Error reading log file '{log_path}': {e}")
        return

    # Regex to find each website segment based on the new log format
    segment_pattern = re.compile(
        r"^-{6} Current Website is (.*?)\s-{6}\n(.*?)\n-{6} End of",
        re.DOTALL
    )
    
    # Regex to find the alias within a segment
    alias_pattern = re.compile(r"Website alias: (.*?),")

    matches = segment_pattern.finditer(log_content_full)
    segments_processed = 0
    for match_obj in matches:
        segments_processed += 1
        log_segment_content = match_obj.group(2).strip()
        
        # Extract the alias (e.g., 'allrecipes_1') to use as a filename
        alias_match = alias_pattern.search(log_segment_content)
        if not alias_match:
            print(f"  Warning: Could not find 'Website alias:' in segment. Skipping.")
            continue
            
        base_filename = alias_match.group(1).strip()
        print(f"\nProcessing segment for: {base_filename}")
        
        output_filename = f"{base_filename}{OUTPUT_FILE_SUFFIX}"
        full_output_path = os.path.join(output_dir, output_filename)
        print(f"  Output file will be: {full_output_path}")

        processed_code = get_code_from_llm(log_segment_content)

        try:
            with open(full_output_path, 'w', encoding='utf-8') as py_file:
                py_file.write(processed_code)
            print(f"  Successfully wrote script to: {full_output_path}")
        except IOError as e:
            print(f"  Error writing to file '{full_output_path}': {e}")
            
    if segments_processed == 0:
        print("No valid segments were found in the log file.")
    else:
        print(f"\nFinished processing. Total segments found: {segments_processed}")

def main():
    """Main script logic."""
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set. Please set it before running.")
        return

    # Find the most recent LLM log file in the current directory
    log_files = glob.glob('*_LLM.log')
    if not log_files:
        print("Error: No '*_LLM.log' files found in the current directory.")
        return
    
    latest_log_file = max(log_files, key=os.path.getmtime)
    print(f"Found latest log file to process: {latest_log_file}")

    parse_log_and_generate_scripts(latest_log_file, OUTPUT_DIRECTORY)

if __name__ == "__main__":
    main()