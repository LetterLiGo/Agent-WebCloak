# Web scraping script using the Gemini API.

from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, ThinkingConfig, ToolCodeExecution, HttpOptions
import os
import datetime
import sys
import glob
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
model_id = "gemini-2.5-pro-preview-03-25"
# model_id = "gemini-2.5-flash-preview-04-17"

google_search_tool = Tool(
    google_search = GoogleSearch()
)

code_execution_tool = Tool(
    code_execution= ToolCodeExecution()
)

def generate_code(item_web, html_log=None, llm_log=None):
    webcontent, weburl, webalias = webpage_read(item_web, html_log)

    response = client.models.generate_content(
        model=model_id,
        contents=f"""This is the target website 

                {webcontent}

                """+"""
                Can you write a scrape python code for me, you should carefully examine this target webpage. My goal is to extract all unique image urls from this website. Finally, I can download them to my local folder.
                
                Note that you should contain user agents to avoid being detected as a bot, such as:
                'headers' and 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                For some websites, you may need to use a proxy or a headless browser to avoid detection.

                IMPORTANT NOTE: For dynamic websites like Behance, using 'requests' and 'BeautifulSoup' alone
                might not capture all images as they are often loaded with JavaScript.
                Consider uncommenting and using the Selenium part of the 'scrape_behance_image_urls' function
                if you have Selenium and a WebDriver (e.g., ChromeDriver) installed.

                IMPORTANT NOTE: !!!Please return the response in the following format!!!
                # Thinking Process
                Detailed explanation of your approach to the target website and the steps you will take in the code
                """+f"""
                # Python Code
                ```python
                Complete Python code to 1) extract image URLs, 2) save these urls as json format: {webalias}_{model_id}_image_urls.json
                """+"""{url1 \n, url2 \n, .. } 3) download based on these urls to local images, note that the image folder's name is"""+f"""{webalias}_{model_id}. 4) This python code can also count the number of unique image URLs.
                ```
            """,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            thinking_config=ThinkingConfig(thinking_budget=2048),
            response_modalities=["TEXT"],
            system_instruction="""You are Gemini Code, an AI coding assistant running in a CLI environment.
                Your goal is to help the user with their coding tasks by understanding their request, planning the necessary steps, and using the available tools via **native function calls**.
                
                Tool Use: Google Search Tool, Code Execution Tool

                Workflow:
                1.  **Analyze & Plan:** Understand the user's request based on the provided directory context (`ls` output) and the request itself. For non-trivial tasks, **first outline a brief plan** of the steps and tools you will use in a text response. **Note:** Actions that modify files (`edit`, `create_file`) will require user confirmation before execution.
                2.  **Execute:** If a plan is not needed or after outlining the plan, make the **first necessary function call** to execute the next step (e.g., `view` a file, `edit` a file, `grep` for text, `tree` for structure).
                3.  **Observe:** You will receive the result of the function call (or a message indicating user rejection). Use this result to inform your next step.
                4.  **Repeat:** Based on the result, make the next function call required to achieve the user's goal. Continue calling functions sequentially until the task is complete.
                5.  **Complete:** Once the *entire* task is finished, **you MUST call the `task_complete` function**, providing a concise summary of what was done in the `summary` argument. 
                    *   The `summary` argument MUST accurately reflect the final outcome (success, partial success, error, or what was done).
                    *   Format the summary using **Markdown** for readability (e.g., use backticks for filenames `like_this.py` or commands `like this`).
                    *   If code was generated or modified, the summary **MUST** contain the **actual, specific commands** needed to run or test the result (e.g., show `pip install Flask` and `python app.py`, not just say "instructions provided"). Use Markdown code blocks for commands.

                Important Rules:
                *   **Use Native Functions:** ONLY interact with tools by making function calls as defined above. Do NOT output tool calls as text (e.g., `cli_tools.ls(...)`).
                *   **Sequential Calls:** Call functions one at a time. You will get the result back before deciding the next step. Do not try to chain calls in one turn.
                *   **Initial Context Handling:** When the user asks a general question about the codebase contents (e.g., "what's in this directory?", "show me the files", "whats in this codebase?"), your **first** response MUST be a summary or list of **ALL** files and directories provided in the initial context (`ls` or `tree` output). Do **NOT** filter this initial list or make assumptions (e.g., about virtual environments). Only after presenting the full initial context should you suggest further actions or use other tools if necessary.
                *   **Accurate Context Reporting:** When asked about directory contents (like "whats in this codebase?"), accurately list or summarize **all** relevant files and directories shown in the `ls` or `tree` output, including common web files (`.html`, `.js`, `.css`), documentation (`.md`), configuration files, build artifacts, etc., not just specific source code types. Do not ignore files just because virtual environments are also present. Use `tree` for a hierarchical view if needed.
                *   **Handling Explanations:** 
                    *   If the user asks *how* to do something, asks for an explanation, or requests instructions (like "how do I run this?"), **provide the explanation or instructions directly in a text response** using clear Markdown formatting.
                    *   **Proactive Assistance:** When providing instructions that culminate in a specific execution command (like `python file.py`, `npm start`, `git status | cat`, etc.), first give the full explanation, then **explicitly ask the user if they want you to run that final command** using the `execute_command` tool. 
                        *   Example: After explaining how to run `calculator.py`, you should ask: "Would you like me to run `python calculator.py | cat` for you using the `execute_command` tool?" (Append `| cat` for commands that might page).
                    *   Do *not* use `task_complete` just for providing information; only use it when the *underlying task* (e.g., file creation, modification) is fully finished.
                *   **Planning First:** For tasks requiring multiple steps (e.g., read file, modify content, write file), explain your plan briefly in text *before* the first function call.
                *   **Precise Edits:** When editing files (`edit` tool), prefer viewing the relevant section first (`view` tool with offset/limit), then use exact `old_string`/`new_string` arguments if possible. Only use the `content` argument for creating new files or complete overwrites.
                *   **Task Completion Signal:** ALWAYS finish action-oriented tasks by calling `task_complete(summary=...)`. 
                    *   The `summary` argument MUST accurately reflect the final outcome (success, partial success, error, or what was done).
                    *   Format the summary using **Markdown** for readability (e.g., use backticks for filenames `like_this.py` or commands `like this`).
                    *   If code was generated or modified, the summary **MUST** contain the **actual, specific commands** needed to run or test the result (e.g., show `pip install Flask` and `python app.py`, not just say "instructions provided"). Use Markdown code blocks for commands.

                The user's first message will contain initial directory context and their request."""
        )
    )

    original_stdout = sys.stdout  # Save a reference to the original standard output

    with open(llm_log, 'a+', encoding='utf-8') as log_file:
        sys.stdout = log_file  # Redirect stdout to the log file
        print(f'------ Current Website is {item_web['dir']} ------')
        print(f'Generating Scraper Code for Website URL:: {weburl}, Website alias: {webalias}, using {model_id}')
        print(f"---------------------" * 3)
        if response and hasattr(response, 'candidates') and response.candidates:
            if hasattr(response.candidates[0], 'content') and hasattr(response.candidates[0].content, 'parts'):
                for each in response.candidates[0].content.parts:
                    if hasattr(each, 'text'):
                        print(each.text)
                    else:
                        print("Error: Part has no text attribute.")
            else:
                print("Error: Response candidate content or parts not found.")
        else:
            print("Error: Response or candidates not found.")
        
        print(f"---------------------" * 3)
        print(f"------ Token usage {response.usage_metadata} ------")
        print(f'------ End of {item_web['dir']} ------')

        sys.stdout = original_stdout  # Reset stdout to its original value

    print(f"Output LLM response logged to {llm_log}")


def webpage_read(item_web, log_filename=None):
    # Read the HTML content from a local file
    original_stdout = sys.stdout  # Save a reference to the original standard output
    
    with open(log_filename, 'a+', encoding='utf-8') as log_file:
        sys.stdout = log_file  # Redirect stdout to the log file
        with open(item_web['dir'], 'r', encoding='utf-8') as file:
            html_content = file.read()
            print(f'------ Current Website is {item_web['dir']} ------')
            print(f"Website URL: {item_web['url']}")
            print(f"Length of HTML content: {len(html_content)}")
            print(f"---------------------" * 3)
            print(html_content)
            print(f"---------------------" * 3)
            print(f'------ End of {item_web['dir']} ------')
        sys.stdout = original_stdout  # Reset stdout to its original value

    print(f"Output HTML logged to {log_filename}")
    return item_web['dir'], item_web['url'], item_web['alias']

if __name__ == "__main__":
    # Import argparse to handle command-line arguments
    import argparse

    # Create a parser
    parser = argparse.ArgumentParser(description="Generate a web scraping script for a single HTML file.")
    # Add a required positional argument for the HTML file path
    parser.add_argument("html_file", type=str, help="The full path to the target HTML file.")
    # Parse the arguments
    args = parser.parse_args()

    # Derive an alias from the file path (e.g., 'allrecipes_1')
    try:
        path_parts = args.html_file.split('/')
        alias = f"{path_parts[-3]}_{path_parts[-2]}"
    except IndexError:
        # Fallback to the filename if the path structure is unexpected
        alias = os.path.basename(args.html_file)

    # Prepare the target file in the format expected by the script
    tar_web_list = [{'dir': args.html_file, 'url': "unknown", 'alias': alias}]

    # Log files will be created in the current working directory
    current_time_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    html_log = f"{current_time_str}_{alias}_{model_id}_html.log"
    llm_log = f"{current_time_str}_{alias}_{model_id}_LLM.log"

    print(f"Processing single file: {args.html_file}")
    for item_web in tar_web_list:
        print(f"Generating scraper for alias: {item_web['alias']} with url: {item_web['url']} using {model_id}")
        generate_code(item_web, html_log, llm_log)