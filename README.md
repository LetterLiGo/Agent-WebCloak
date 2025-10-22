# WebCloak: Characterizing and Mitigating the Threats of LLM-Driven Web Agents as Intelligent Scrapers

This repository contains the artifact for the paper "WebCloak: Characterizing and Mitigating the Threats of LLM-Driven Web Agents as Intelligent Scrapers". Our work presents the first systematic characterization of LLM-driven web agents as intelligent scrapers and introduces WebCloak, an effective defense mechanism.

---

## 🔬 Overview

The rise of web agents powered by large language models (LLMs) enables users to automate complex web tasks with natural language commands, but introduces serious security concerns: adversaries can easily employ such web agents to conduct advanced web scraping, particularly of rich visual content.

This artifact includes:
- **LLMCrawlBench**: A large test set of 237 extracted real-world webpages (10,895 images) from 50 popular websites across 5 critical categories
- **WebCloak Defense**: A dual-layered defense mechanism with Dynamic Structural Obfuscation and Optimized Semantic Labyrinth
- **Comprehensive Evaluation**: Testing against LLM scraper implementations including LLM-to-Script (L2S), LLM-Native Crawlers (LNC), and LLM-based web agents (LWA)

---

## 🛠️ Preparation

### Prerequisites

In a Python 3.12 environment, run these commands to build the required environment:

```bash
conda create -n webcloak python=3.12
conda activate webcloak
pip install -r requirements.txt --no-deps

# Initialize Playwright if not already initialized
playwright install
```

### Dataset Download

The dataset files can be downloaded separately from Google Drive via this link: https://zenodo.org/uploads/17251212.

The downloaded dataset files should be placed directly inside the `/dataset/artifact/` folder, , e.g., the `99designs` folder should be in `/dataset/artifact/99designs`.

### Environment Setup

To run the experiments, you need to set up your own API keys. You can do this by editing the `artifact/experiments/secret.py` file:

```bash
cd artifact/experiments
# Edit secret.py to add your own API keys
# Or copy from template: cp secret_template.py secret.py
```
---

## 🗂️ Repository Structure

- **`dataset/artifact/`**: LLMCrawlBench - 237 real-world webpages from 50 popular websites
- **`artifact/source_code/`**: WebCloak defense implementation
- **`artifact/experiments/`**: Scripts for various scraping tools and defense mechanisms

---

## 🎯 Key Results

Our evaluation demonstrates that:

- **Threat Assessment**: Sophisticated LLM-powered frameworks significantly lower the bar for effective scraping
- **Defense Effectiveness**: WebCloak reduces scraping recall rates from **88.7% to 0%** against leading LLM-driven scraping agents
- **Visual Quality**: Perfect visual quality maintained for legitimate users
- **Robustness**: Effective against adversarial prompts and multi-turn attacks

---

## 🔍 LLMCrawlBench Dataset

The dataset includes 237 webpages from 50 popular websites across 5 categories:
- **Marketplaces**: Amazon, eBay, Alibaba, etc.
- **Travel**: Booking, Airbnb, TripAdvisor, etc.
- **Lifestyle**: AllRecipes, Bon Appétit, etc.
- **Design**: Behance, Dribbble, etc.
- **Entertainment**: IMDb, ESPN, etc.

Each webpage includes:
- Original HTML files
- Associated assets (CSS, JS, images)
- Image metadata and ground truth annotations
- Defended versions with WebCloak applied


---

## 🚀 Usage

### 1. Running the WebCloak Defense

To apply the Dynamic Structural Obfuscation (Stage 1) defense to webpages:

```bash
cd artifact/source_code
python stage1/defend.py
```

Defended files are saved as `index.html_edited.html` in the dataset directories. Specified content can be seen in `source_code/stage1/README.md`.

To apply the Optimized Semantic Labyrinth (Stage 2) defense to webpages:

```bash
# Initialize for dependencies
pip install beautifulsoup4 openai google-generativeai html2text asyncio pathlib

# Set Gemini and OpenAI API keys
export GOOGLE_API_KEY="your_gemini_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"

# Start to Do Defense
cd artifact/source_code/stage2
python main_stage2.py path/to/your/input.html
```

**Example Output**: We have included a complete execution example in `source_code/stage2/Output/test_20251001_233314/` containing:
- `protected_html/`: Defended HTML files with invisible protection layers
- `llm_responses/`: LLM-generated defense text for each image
- `markdown_prompts/`: Structured prompts used for defense generation

This demonstrates successful Stage 2 execution and can be used as a reference. Specified content can be seen in `source_code/stage2/README.md`.

### 2. Running LLM-Driven Scrapers Experiments

Although headless command-line-only mode is supported, we highly recommend the experiments to be done in a GUI-enabled environment, for best result visualisation and optimal accuracy.

#### Running Browser-Use

```bash
cd artifact/experiments
python run_browser_use.py

# For headless mode (command-line environments)
python run_browser_use.py --headless

# Test against Stage 1 defended pages
python run_browser_use.py --edited-file
```

More usages, like model selection, can be found in `experiments/README_browser_use.md`.

#### Running Crawl4AI

```bash
cd artifact/experiments
python run_crawl4ai.py

# For headless mode
python run_crawl4ai.py --headless

# Test against Stage 1 defended pages
python run_crawl4ai.py --edited-file
```

More usages, like model selection, can be found in `experiments/README_crawl4ai.md`.

#### Running LLM-to-Script

Configure your Gemini API key for LLM-to-Script paradigm by setting environment variable:

```bash
export GEMINI_API_KEY='YOUR_API_KEY'
```

This command below is an example of doing LLM-to-Script experiments.

```bash
cd artifact/experiments
python llm2script.py dataset/allrecipes/1/index.html
```

The output results of this example are located in 'experiments/LLM-to-Script/allrecipes_1_gemini-2.5-pro-preview-03-25' and 'experiments/LLM-to-Script/json', the generated logs are located in 'experiments/LLM-to-Script/logs', and the code generated by LLM is located in 'experiments/LLM-to-Script/generated_scripts'.

#### HTTP Mode (Required for Crawl4AI Adversarial Robustness Tests)

For accurate adversarial robustness evaluation against Crawl4AI, set up a local web server:

1. Install Laravel Herd (Windows/macOS) or Valet Linux
2. Set up `http://webcloak.test/` pointing to the artifact directory
3. Run: `python run_crawl4ai.py --http-path`

More details can be found in `experiments/README_crawl4ai.md`. This step is not necessary when not doing Crawl4AI adversarial robustness tests.

#### Adversarial Robustness Testing

Test against sophisticated adversarial prompts for Browser Use and Crawl4AI:

```bash
# Generic adversarial prompts
python run_crawl4ai.py --adversary generic
python run_browser_use.py --adversary generic

# Knowledge-based adversarial prompts
python run_crawl4ai.py --adversary knowledge
python run_browser_use.py --adversary knowledge
```

For LLM-to-Script, the process will involve two steps: 
1. Generate adaptive adversarial scraper scripts via `experiments/Table10/adaptive_L2S.py`. Choose between different user messages to get scripts for different settings
2. Utilize `experiments/LLM-to-Script/l2s_3.py` to gather statistics


---

## 🛡️ WebCloak Defense

LLM-driven scraping agents often reply on webpage parsing and interpretation. To mitigate such evolving threats, we introduce dual-layer WebCloak with (1) dynamic obfuscation and (2) semantic labyrinth. 

WebCloak aims to be a lightweight, “in-page” solution that transforms a standard webpage into a self-protecting asset, without relying on external tools or heavy server-side interventions.

---

## 📜Citation
If you find our work/code/dataset helpful, please consider citing:
```
@inproceedings{li2026webcloak,
  title={WebCloak: Characterizing and Mitigating Threats from {LLM}-Driven Web Agents as Intelligent Scrapers},
  author={Li, Xinfeng and Qiu, Tianze and Jin, Yingbin and Wang, Lixu and Guo, Hanqing and Jia, Xiaojun and Wang, XiaoFeng and Dong, Wei},
  booktitle={2026 IEEE Symposium on Security and Privacy (S\&P)},
  year={2026}
}
```


---

## ⚖️ Ethical Considerations

Our research protocol, including LLMCrawlBench data collection and the user studies, received full approval from our Institutional Review Board (IRB). In line with best practices for web agent datasets like WebArena, Mind2Web, LLMCrawlBench consists of offline snapshots of public webpages, and no private or authenticated user data was accessed or stored. 

All experiments are conducted locally to avoid impact on live websites. Ground-truth annotation is done by trained annotators under clear guidelines to ensure objectivity and relevance. WebCloak is designed as a defensive technology to protect website owners. Access to our datasets is strictly regulated and granted only for legitimate research purposes, subject to rigorous scrutiny and institutional approval to maintain ethical standards. We have also contacted the websites to inform them of our research.
