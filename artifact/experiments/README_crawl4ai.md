# Overview

This experiment uses Crawl4AI, an LLM-powered web crawling framework, to extract valuable contents from websites. The code of experiment consists of:

- `run_crawl4ai.py` - Main entry point script that orchestrates the experiments
- `util_crawl4ai.py` - Core utility module containing the Crawl4AI experiment runner with async web crawling, LLM-based extraction, and evaluation logic
- `util_iterate.py` - Dataset iteration utility for loading and iterating through test cases

# Running

Initialize Playwright first if it is not initialized yet.
```bash
playwright install
```

Then, you can just start the experiment.

```bash
cd experiments
python run_crawl4ai.py
```

To run the experiment in command-line only environment, headless need to be toggled on.

```bash
cd experiments
python run_crawl4ai.py --headless
```

You can also use an `--edited-file` argument to directly run for stage1 defended web pages.

```bash
cd experiments
python run_crawl4ai.py --edited-file
```

# Model Selection

You can specify which LLM model to use with the `--use-model` argument. If not specified, Gemini is used by default.

```bash
# Use Google Gemini 2.5 (default)
python run_crawl4ai.py --use-model GEMINI

# Use OpenAI GPT-4o
python run_crawl4ai.py --use-model OPENAI

# Use Anthropic Claude 3.7 Sonnet
python run_crawl4ai.py --use-model ANTHROPIC

# Use DeepSeek V3
python run_crawl4ai.py --use-model DEEPSEEK
```

# Running in HTTP Mode

> Note: This step is not required for getting correct results in our main experiment, but required for correct results in our adversary robustness experiments, due to some design issues of the Crawl4AI package.

Download a way to host directories as websites first.

The easiest way is to download Laravel Herd https://herd.laravel.com/ for Windows and macOS, or download Valte Linux https://github.com/cpriego/valet-linux for Linux.

Then set up http://webcloak.test/ at the directory of WebCloak artifact.

For Laravel Herd, select "Add Site" -> "Link existing project", then click the Settings button on the Sites panel and select "Show sites without valid driver", and it's now working.

Then, you can just start the experiment in HTTP mode.

```bash
cd experiments
python run_crawl4ai.py --http-path

# Combine with model selection
python run_crawl4ai.py --http-path --use-model ANTHROPIC
```

# Running for Adversary Tasks

```bash
# Use generic adversarial prompt
python run_crawl4ai.py --adversary generic

# Use knowledge-based adversarial prompt
python run_crawl4ai.py --adversary knowledge

# Combine with specific model and HTTP mode
python run_crawl4ai.py --adversary knowledge --use-model GEMINI --http-path
```