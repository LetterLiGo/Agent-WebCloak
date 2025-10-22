"""
util_crawl4ai.py - Crawl4AI Experiment Runner
Tested against crawl4ai==0.6.2 + fix from #1073 (included in ./crawl4ai_package/)

This utility script runs Crawl4AI-based web scraping experiments with LLM-powered extraction.
It uses async crawling with Playwright to extract image URLs from web pages, then evaluates
the results against ground truth data to calculate precision and recall metrics.

The script supports multiple LLM providers (OpenAI, Anthropic, Gemini, DeepSeek) and includes
optional WandB logging and resource monitoring (CPU/memory usage).

Usage: See run_crawl4ai.py
"""

from os import path
import os
import shutil
import psutil
import asyncio

import nest_asyncio
import time
import wandb
import json

from pydantic import BaseModel

from secret import (GOOGLE_API_KEY, OPENAI_API_KEY, CLAUDE_API_KEY, DEEPSEEK_API_KEY,
                    CUSTOM_BASE_URL, GOOGLE_BASE_URL, OPENAI_BASE_URL, CLAUDE_BASE_URL, DEEPSEEK_BASE_URL)
from statistics.image_counter import get_image_statistics
from statistics.image_saver import save_images
from crawl4ai_package.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai_package import (LLMExtractionStrategy, CrawlerRunConfig, CacheMode,
                      BrowserConfig, AsyncWebCrawler, LLMConfig)

nest_asyncio.apply()

class ImageItem(BaseModel):
    title: str
    image_url: str

use_wandb = False
download_images = True

if use_wandb:
    wandb_info = {
        "project": "WebAgent-Crawler-Safety",
        "group": "Stage-1-Adv-Naive-S1",
        "entity": "LetterLisafeweb",
    }

async def main(test_name: str, test_id: str, test_case_url: str, save_path: str, headless: bool, task: str, use_model: str):
    output_dir = path.join(save_path, test_name)
    try:
        shutil.rmtree(path.join(output_dir, test_id))
    except FileNotFoundError:
        pass
    os.makedirs(output_dir, exist_ok=True)

    # Set up resource monitoring during agent.run(...)
    proc = psutil.Process(os.getpid())
    cpu_samples = []
    mem_samples = []
    monitoring = True

    async def monitor():
        proc.cpu_percent(None)  # warm up
        while monitoring:
            cpu_samples.append(proc.cpu_percent(None))
            mem_samples.append(proc.memory_percent())
            await asyncio.sleep(0.1)

    monitor_task = asyncio.create_task(monitor())

    start_time = time.time()
    use_openrouter = CUSTOM_BASE_URL and ("openrouter" in CLAUDE_BASE_URL)

    if use_model == "OPENAI":
        llm_config = LLMConfig(
            provider="openai/gpt-4o",
            api_token=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL if CUSTOM_BASE_URL else None,
        )
    elif use_model == "ANTHROPIC":
        llm_config = LLMConfig(
            provider="openai/anthropic/claude-3.7-sonnet" if use_openrouter else "openai/claude-3-7-sonnet-20250219",
            api_token=CLAUDE_API_KEY,
            base_url=CLAUDE_BASE_URL if CUSTOM_BASE_URL else None,
        )
    elif use_model == "GEMINI":
        llm_config = LLMConfig(
            # provider="openai/gemini-2.5-pro-preview-05-06",
            # provider="openai/gemini-2.5-flash-preview-04-17",
            provider="openai/google/gemini-2.5-flash" if use_openrouter else "openai/gemini-2.5-flash",
            api_token=GOOGLE_API_KEY,
            base_url=GOOGLE_BASE_URL if CUSTOM_BASE_URL else None,
        )
    elif use_model == "DEEPSEEK":
        llm_config = LLMConfig(
            # provider="openai/deepseek-v3",
            provider="openai/deepseek/deepseek-v3.2-exp" if use_openrouter else "openai/deepseek-v3",
            api_token=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL if CUSTOM_BASE_URL else None,
        )
    else:
        raise ValueError(f"Model {use_model} is not supported.")

    llm_strategy = LLMExtractionStrategy(
        llm_config=llm_config,
        schema=ImageItem.model_json_schema(),  # Or use model_json_schema()
        extraction_type="schema",
        instruction=task.format(url=test_case_url),
        chunk_token_threshold=4000,
        overlap_rate=0.0,
        apply_chunking=True,
        input_format="markdown",  # or "html", "fit_markdown"
        extra_args={
            "timeout": 300
        }
    )

    browser_cfg = BrowserConfig(headless=headless)
    crawl_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        delay_before_return_html=5,
    )

    crawler_strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_cfg)

    async with AsyncWebCrawler(config=browser_cfg, crawler_strategy=crawler_strategy) as crawler:
        if use_wandb:
            run = wandb.init(
                project=wandb_info["project"],
                group=wandb_info["group"],
                name=f"e2e-llm_scraper-{time.strftime('%Y%m%d-%H%M%S')}",
                entity=wandb_info["entity"],
                tags=[test_id],
                config={
                    "agent_task": "Crawl4AI",
                    "model": llm_config.provider,
                    "experiment_version": "v1.0",
                    "browser": "chromium",
                    "target_url": test_case_url,
                }
            )

        print(time.time() - start_time)

        # 4. Let's say we want to crawl a single page
        result = await crawler.arun(
            url=test_case_url,
            config=crawl_config
        )

        if result.success:
            monitoring = False
            await monitor_task

            # 5. The extracted content is presumably JSON
            data = json.loads(result.extracted_content)
            print("Extracted items length:", len(data))
            print("Extracted items:", data)

            if len(data) > 0:
                if 'error' in data[0]:
                    if data[0]['error']:
                        print("Error:", data[0]['error'])
                        if use_wandb: run.finish()
                        return

            with open(path.join(output_dir, test_id + ".json"), 'w') as f:
                f.write(result.extracted_content)

            # 6. Show usage stats
            llm_strategy.show_usage()  # prints token usage

            # Get metrics from llm_strategy
            avg_cpu_usage = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
            peak_mem_usage = max(mem_samples) if mem_samples else 0.0
            usage_stats = llm_strategy.total_usage
            execution_time = time.time() - start_time
            total_tokens = usage_stats.total_tokens

            if isinstance(result.extracted_content, str):
                result_data = json.loads(result.extracted_content)
            else:
                result_data = result.extracted_content
            result_urls = [item.get("image_url") for item in result_data if item.get("image_url")]

            # Save images to the output directory
            if download_images:
                test_case_url_cleaned = test_case_url.split('?_')[0]
                download_dir, _ = await save_images(result_urls, output_dir, test_id, test_case_url_cleaned)
                print(f"Images saved to {download_dir}")

                # Edit this when changing dataset dir
                dataset_base_dir = "/dataset/"
                test_case_url_cleaned_processed = test_case_url_cleaned
                if dataset_base_dir in test_case_url_cleaned_processed:
                    test_case_url_cleaned_processed = test_case_url_cleaned_processed.split(dataset_base_dir)[1]
                dataset_dir = '../../' + f'.{dataset_base_dir}' + test_case_url_cleaned_processed.replace('_edited.html', '').replace('_protected.html', '.html').replace('index.html', 'index_files').split(dataset_base_dir)[-1]
                print(dataset_dir)
                ground_truth_count, scraped_total_count, correctly_scraped_count, precision, recall = get_image_statistics(test_id, dataset_dir, download_dir)

                print("------------------------------")
                print(f"Ground truth count: {ground_truth_count}")
                print(f"Scraped total count: {scraped_total_count}")
                print(f"Correctly scraped count: {correctly_scraped_count}")
                print(f"Precision: {precision}")
                print(f"Recall: {recall}")

                # Log metrics to WandB
                metrics = {
                    "successful_count": correctly_scraped_count,
                    "downloaded_count": scraped_total_count,
                    "original_count": ground_truth_count,
                    "precision": precision,
                    "recall": recall,
                    "execution_time": execution_time,
                    "total_tokens": total_tokens,
                    "avg_cpu_usage": avg_cpu_usage,
                    "peak_mem_usage": peak_mem_usage,
                }
            else:
                metrics = {
                    "execution_time": execution_time,
                    "total_tokens": total_tokens,
                    "avg_cpu_usage": avg_cpu_usage,
                    "peak_mem_usage": peak_mem_usage,
                }

            if use_wandb:
                wandb.log(metrics)
        else:
            monitoring = False
            print("Error:", result.error_message)

        if use_wandb:
            run.finish()