import os
import sys
import subprocess
import time
import argparse

def run_step(command, working_dir, step_name):
    """A helper function to run a command-line step and print its status."""
    print(f"\n{'='*20}\n[Step {step_name}] Starting...\nCommand: {' '.join(command)}\nWorking Directory: {working_dir}\n{'='*20}")
    try:
        # Use sys.executable to ensure the same Python interpreter is used
        process = subprocess.run([sys.executable] + command, 
                                 cwd=working_dir, 
                                 check=True, 
                                 capture_output=True, 
                                 text=True,
                                 encoding='utf-8')
        print(f"[Step {step_name}] Completed successfully.")
        # Uncomment the line below to see the last 500 characters of the output
        # print("--- Output ---\n" + process.stdout[-500:])
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!!!!! [Step {step_name}] FAILED !!!!!!")
        print(f"Return Code: {e.returncode}")
        print("--- STDOUT ---\n" + e.stdout)
        print("--- STDERR ---\n" + e.stderr)
        return False
    except FileNotFoundError:
        print(f"!!!!!! [Step {step_name}] FAILED !!!!!!")
        print(f"Error: Command '{command[0]}' not found. Please ensure the script exists at the specified location.")
        return False

def main():
    """Main function to orchestrate all steps."""
    parser = argparse.ArgumentParser(description="One-click script to run the complete LLM-to-Script workflow.")
    parser.add_argument("html_file", type=str, help="Relative path to the target HTML file from the 'webcloak' directory (e.g., 'dataset/allrecipes/1/index.html_edited.html').")
    args = parser.parse_args()

    # --- Path Configuration ---
    # The directory where this master script is located (webcloak/experiments/)
    experiments_dir = os.path.dirname(os.path.abspath(__file__))
    # The root directory of the project (webcloak/)
    project_root = os.path.dirname(experiments_dir)
    # The directory containing the three sub-scripts
    scripts_dir = os.path.join(experiments_dir, "LLM-to-Script")
    # The full, absolute path to the target HTML file
    target_html_file_abs = os.path.join(project_root, args.html_file)
    
    # Derive alias from the path for finding the generated script later
    try:
        alias = f"{args.html_file.split('/')[-3]}_{args.html_file.split('/')[-2]}"
    except IndexError:
        print(f"Error: The provided html_file path '{args.html_file}' does not have the expected structure.")
        return

    print("One-Click Execution Script Started...")
    print(f"Master Script Directory: {experiments_dir}")
    print(f"Sub-scripts Directory: {scripts_dir}")
    print(f"Target HTML File: {target_html_file_abs}")
    
    # Check if the API key is set
    if not os.getenv("GEMINI_API_KEY"):
        print("\nError: The GEMINI_API_KEY environment variable is not set. Please set it before running.")
        return
        
    if not os.path.isfile(target_html_file_abs):
        print(f"\nError: The target HTML file was not found at '{target_html_file_abs}'")
        return

    # --- Workflow Start ---
    
    # 1. Run l2s_1.py to generate the log file containing the code
    if not run_step(['l2s_1.py', target_html_file_abs], scripts_dir, "1/4 - Generating Scraper Code"):
        return

    # 2. Run l2s_2.py to parse the log and extract the .py script
    # It will automatically find the latest log file
    if not run_step(['l2s_2.py'], scripts_dir, "2/4 - Parsing Log and Extracting Code"):
        return
        
    # 3. Execute the newly generated scraper script
    generated_script_path = os.path.join(scripts_dir, "generated_scripts", f"{alias}.py")
    
    # Wait a moment to ensure the file system has registered the new file
    time.sleep(1) 
    
    if not os.path.exists(generated_script_path):
        print(f"\nError: The generated scraper script was not found: {generated_script_path}")
        print("Please check the output of Step 2 to confirm if the script was created successfully.")
        return
        
    if not run_step([generated_script_path], scripts_dir, "3/4 - Executing Generated Scraper"):
        return

    # 4. Run l2s_3.py to calculate the final statistics
    if not run_step(['l2s_3.py'], scripts_dir, "4/4 - Calculating Statistics"):
        return
        
    print("\n🎉 Workflow completed successfully!")

if __name__ == "__main__":
    main()