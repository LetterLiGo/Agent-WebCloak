# WebCloak: Characterizing and Mitigating the Threats of LLM-Driven Web Agents as Intelligent Scrapers

<p align="left">
  <a href="https://visitor-badge.laobi.icu/badge?page_id=web-cloak.github.io">
    <img src="https://visitor-badge.laobi.icu/badge?page_id=web-cloak.github.io" alt="Visitors">
  </a>
  <a href="https://letterligo.github.io/paper/SP26_WebAgent.pdf">
    <img src="https://img.shields.io/badge/Paper-PDF-red" alt="Paper">
  </a>
  <a href="https://zenodo.org/records/17251212">
    <img src="https://img.shields.io/badge/Dataset-Zenodo-blue" alt="Dataset">
  </a>
  <a href="https://web-cloak.github.io/">
    <img src="https://img.shields.io/badge/Website-Visit-blue" alt="Website">
  </a>
  <a href="https://github.com/LetterLiGO/Agent-WebCloak">
    <img src="https://img.shields.io/github/stars/LetterLiGO/Agent-WebCloak?style=social" alt="GitHub stars">
  </a>
  <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">
    <img src="https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg" alt="License: CC BY-NC-SA 4.0">
  </a>
  
</p>



This repository contains the code for our paper "WebCloak: Characterizing and Mitigating the Threats of LLM-Driven Web Agents as Intelligent Scrapers" (IEEE S&P 2026). Our work presents the first systematic characterization of LLM-driven web agents as intelligent scrapers and introduces WebCloak, an effective defense mechanism.

---

## 🔬 Overview

The rise of web agents powered by large language models (LLMs) enables users to automate complex web tasks with natural language commands, but introduces serious security concerns: adversaries can easily employ such web agents to conduct advanced web scraping, particularly of rich visual content.

This artifact includes:
- **LLMCrawlBench**: A large test set of 237 extracted real-world webpages (10,895 images) from 50 popular websites across 5 critical categories.
- **WebCloak Defense**: A dual-layered defense mechanism with Dynamic Structural Obfuscation and Optimized Semantic Labyrinth.
- **Comprehensive Evaluation**: Testing against LLM scraper implementations including LLM-to-Script (L2S), LLM-Native Crawlers (LNC), and LLM-based web agents (LWA).

---

## ⚔️ The Threat: LLM-Driven Web Agents as Intelligent Scrapers

LLM-driven web agents can be easily repurposed for malicious scraping. These agents typically follow a "Parse-then-Interpret" mechanism, which makes them vulnerable to our defense.

<p align="center">
  <img src="static/images/agents-mechanism.png" alt="Agent Mechanism" width="70%">
</p>

---

## 🛡️ WebCloak Defense

WebCloak is a dual-layered defense mechanism designed to protect against LLM-driven scrapers.

<p align="center">
  <img src="static/images/design_overview.png" alt="WebCloak Overview" width="70%">
</p>

### Stage 1: Dynamic Structural Obfuscation

This stage randomizes structural cues and restores visual content client-side using non-traditional methods.

<p align="center">
  <img src="static/images/design_s1.png" alt="WebCloak Stage 1" width="70%">
</p>

### Stage 2: Optimized Semantic Labyrinth

This stage misleads the LLM's interpretation by adding harmless-yet-misleading contextual clues, without sacrificing visual quality for legitimate users.

<p align="center">
  <img src="static/images/design_s2.png" alt="WebCloak Stage 2" width="70%">
</p>

---

## 🗂️ LLMCrawlBench Dataset

LLMCrawlBench is a large-scale benchmark dataset for evaluating web scraping threats.

<p align="center">
  <img src="static/images/dataset.png" alt="Dataset" width="70%">
</p>

<p align="center">
  <img src="static/images/dataset_details.jpg" alt="Dataset" width="70%">
</p>

---

## 🚀 Usage

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

The dataset files can be downloaded separately from Google Drive via this link: https://drive.google.com/drive/folders/1OLZPqcdE8I4nvK4NJ0tXeS1_PTUD6kLk?usp=sharing

The downloaded dataset files should be placed directly inside the `/dataset/` folder, e.g., the `99designs` folder should be in `/dataset/99designs`.

### Environment Setup

To run the experiments, you need to set up your own API keys. You can do this by editing the `artifact/experiments/secret.py` file:

```bash
cd artifact/experiments
# Edit secret.py to add your own API keys
# Or copy from template: cp secret_template.py secret.py
```

### Running the WebCloak Defense

To apply the Dynamic Structural Obfuscation (Stage 1) defense to webpages:

```bash
cd artifact/source_code
python stage1/defend.py
```

Defended files are saved as `index.html_edited.html` in the dataset directories.

To apply the Optimized Semantic Labyrinth (Stage 2) defense to webpages:

```bash
# Set Gemini and OpenAI API keys
export GOOGLE_API_KEY="your_gemini_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"

# Start to Do Defense
cd artifact/source_code/stage2
python main_stage2.py path/to/your/input.html
```

### Running LLM-Driven Scrapers Experiments

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

#### Running Crawl4AI

```bash
cd artifact/experiments
python run_crawl4ai.py

# For headless mode
python run_crawl4ai.py --headless

# Test against Stage 1 defended pages
python run_crawl4ai.py --edited-file
```

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

---

## ⚖️ Ethical Considerations

Our research protocol, including LLMCrawlBench data collection and the user studies, received full approval from our Institutional Review Board (IRB). In line with best practices for web agent datasets like WebArena, Mind2Web, LLMCrawlBench consists of offline snapshots of public webpages, and no private or authenticated user data was accessed or stored.

All experiments are conducted locally to avoid impact on live websites. Ground-truth annotation is done by trained annotators under clear guidelines to ensure objectivity and relevance. WebCloak is designed as a defensive technology to protect website owners. Access to our datasets is strictly regulated and granted only for legitimate research purposes, subject to rigorous scrutiny and institutional approval to maintain ethical standards. We have also contacted the websites to inform them of our research.

---

## 📄 License

This project is licensed under the terms of the `LICENSE` file. This software is licensed for non-commercial use only.

---

## ✏️ Citation

If you find our work/code/dataset useful, please consider citing our paper:

```bibtex
@inproceedings{li2026webcloak,
  title={WebCloak: Characterizing and Mitigating the Threats of LLM-Driven Web Agents as Intelligent Scrapers},
  author={Li, Xinfeng and Qiu, Tianze and Jin, Yingbin and Wang, Lixu and Guo, Hanqing and Jia, Xiaojun and Wang, XiaoFeng and Dong, Wei},
  booktitle={IEEE Symposium on Security and Privacy (S&P)},
  year={2026}
}
```
