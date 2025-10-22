"""
util_browser_use.py - Browser-Use Experiment Runner
Tested against browser-use v0.1.48 (2025.5.16)

This utility script runs Browser-Use-based web scraping experiments using agentic web browsing.
It leverages LLM-powered agents to interact with web pages through a real browser, extract
image URLs, and evaluate results against ground truth data.

The script supports multiple LLM providers (OpenAI, Anthropic, Gemini, DeepSeek) via LangChain,
includes custom proxy support for Anthropic API, and provides optional WandB logging with
detailed step-by-step metrics.

Usage: See run_browser_use.py
"""

from os import path
import os
import httpx
import time
import shutil

from dotenv import load_dotenv

load_dotenv()

from secret import (GOOGLE_API_KEY, OPENAI_API_KEY, CLAUDE_API_KEY, DEEPSEEK_API_KEY,
                    CUSTOM_BASE_URL, GOOGLE_BASE_URL, OPENAI_BASE_URL, CLAUDE_BASE_URL, DEEPSEEK_BASE_URL)

if CUSTOM_BASE_URL:
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
    os.environ["HTTP_PROXYS"] = "http://127.0.0.1:7890"

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel
from browser_use import Controller, Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.agent.views import AgentHistoryList

import wandb
import anthropic

from functools import cached_property
from typing import Any, Dict

from statistics.image_counter import get_image_statistics
from statistics.image_saver import save_images

class ImageItem(BaseModel):
    title: str
    image_url: str


class ImageItems(BaseModel):
    items: list[ImageItem]

use_wandb = False
download_images = True


async def main(test_name: str, test_id: str, test_case_url: str, save_path: str, headless: bool, task: str, use_model: str):
    output_dir = path.join(save_path, test_name)
    try:
        shutil.rmtree(path.join(output_dir, test_id))
    except FileNotFoundError:
        pass
    os.makedirs(output_dir, exist_ok=True)

    use_openrouter = CUSTOM_BASE_URL and ("openrouter" in CLAUDE_BASE_URL)

    if use_model == "OPENAI":
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
        if CUSTOM_BASE_URL:
            os.environ["OPENAI_BASE_URL"] = OPENAI_BASE_URL
        llm_used = ChatOpenAI(
            model="openai/gpt-4o" if use_openrouter else "gpt-4o",
        )
    elif use_model == "ANTHROPIC":
        if use_openrouter:
            os.environ["OPENAI_API_KEY"] = CLAUDE_API_KEY
            os.environ["OPENAI_BASE_URL"] = CLAUDE_BASE_URL
            llm_used = ChatOpenAI(
                model="anthropic/claude-3.7-sonnet"
            )
        else:
            llm_used = ChatAnthropicWithProxy(
                model_name="claude-3-7-sonnet-20250219",
                anthropic_api_key=CLAUDE_API_KEY,
                use_proxy=CUSTOM_BASE_URL,
                anthropic_api_url=CLAUDE_BASE_URL if CUSTOM_BASE_URL else None,
            )
    elif use_model == "GEMINI":
        if CUSTOM_BASE_URL:
            os.environ["OPENAI_API_KEY"] = GOOGLE_API_KEY
            os.environ["OPENAI_BASE_URL"] = GOOGLE_BASE_URL
            llm_used = ChatOpenAI(
                model="google/gemini-2.5-flash" if use_openrouter else "gemini-2.5-flash",
            )
        else:
            # Open TUN mode of your proxy to it failed to start
            os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
            llm_used = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-preview-04-17",
                google_api_key=GOOGLE_API_KEY,
            )
    elif use_model == "DEEPSEEK":
        if CUSTOM_BASE_URL:
            os.environ["OPENAI_API_KEY"] = DEEPSEEK_API_KEY
            os.environ["OPENAI_BASE_URL"] = DEEPSEEK_BASE_URL
            llm_used = ChatOpenAI(
                model="deepseek/deepseek-v3.2-exp" if use_openrouter else "deepseek-v3",
            )
        else:
            os.environ["DEEPSEEK_API_KEY"] = DEEPSEEK_API_KEY
            llm_used = ChatDeepSeek(
                model="deepseek-v3"
            )
    else:
        raise NotImplementedError(f"{use_model} is not implemented.")

    if use_wandb:
        wandb.init(
            project="WebAgent-Crawler-Safety",
            group="Stage1-Small-Scale",
            name=f"e2e-web_GUI_agent-scraper-{time.strftime('%Y%m%d-%H%M%S')}",
            entity="LetterLisafeweb",
            tags=[test_id],
            config={
                "agent_task": "BU",
                "model": llm_used,
                "experiment_version": "v1.0",
                "browser": "chromium",
                "target_url": test_case_url,
            }
        )

    browser = Browser(config=BrowserConfig(headless=headless))
    async with await browser.new_context() as context:
        controller = Controller(output_model=ImageItems)
        agent = MonitoredAgent(
            task=task.format(url=test_case_url),
            max_actions_per_step=8,
            llm=llm_used,
            use_vision=False,
            browser_context=context,
            controller=controller,
        )
        history = await agent.run(max_steps=20)
        result = history.final_result()
        if result:
            parsed: ImageItems = ImageItems.model_validate_json(result)
            for item in parsed.items:
                print('\n--------------------------------')
                print(f"Title: {item.title}")
                print(f"Image URL: {item.image_url}")

            result_urls = [item.image_url for item in parsed.items]

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
                dataset_dir = '../../' + f'.{dataset_base_dir}' + \
                              test_case_url_cleaned_processed.replace('_edited.html', '').replace('_protected.html',
                                                                                                  '.html').replace(
                                  'index.html', 'index_files').split(dataset_base_dir)[-1]
                print(dataset_dir)
                ground_truth_count, scraped_total_count, correctly_scraped_count, precision, recall = get_image_statistics(
                    test_id, dataset_dir, download_dir)

                print("------------------------------")
                print(f"Ground truth count: {ground_truth_count}")
                print(f"Scraped total count: {scraped_total_count}")
                print(f"Correctly scraped count: {correctly_scraped_count}")
                print(f"Precision: {precision}")
                print(f"Recall: {recall}")
        else:
            print("No result found")

        output_dir = path.join(save_path, test_name)
        os.makedirs(output_dir, exist_ok=True)

        with open(path.join(output_dir, test_id + ".json"), 'w') as f:
            f.write(result)
        await browser.close()

    if use_wandb:
        wandb.finish()

class ChatAnthropicWithProxy(ChatAnthropic):
    use_proxy: bool = False
    """Whether to use proxy to connect to Anthropic API."""

    @cached_property
    def _client_params(self) -> Dict[str, Any]:
        client_params: Dict[str, Any] = {
            "api_key": self.anthropic_api_key.get_secret_value(),
            "base_url": self.anthropic_api_url,
            "max_retries": self.max_retries,
            "default_headers": (self.default_headers or None),
        }
        # value <= 0 indicates the param should be ignored. None is a meaningful value
        # for Anthropic client and treated differently than not specifying the param at
        # all.
        if self.default_request_timeout is None or self.default_request_timeout > 0:
            client_params["timeout"] = self.default_request_timeout

        # manually added code, to use proxy to connect to Anthropic API
        if self.use_proxy:
            client_params["http_client"] = httpx.Client(mounts={
                "http://": httpx.HTTPTransport(proxy="http://localhost:7890"),
                "https://": httpx.HTTPTransport(proxy="http://localhost:7890"),
            })

        return client_params

    @cached_property
    def _async_client_params(self) -> Dict[str, Any]:
        """Returns the parameters for creating an async client instance."""
        client_params = self._client_params.copy()

        # Replace the httpx.Client with httpx.AsyncClient if proxy is enabled
        if self.use_proxy:
            client_params["http_client"] = httpx.AsyncClient(mounts={
                "http://": httpx.AsyncHTTPTransport(proxy="http://localhost:7890"),
                "https://": httpx.AsyncHTTPTransport(proxy="http://localhost:7890"),
            })

        return client_params

    @cached_property
    def _client(self) -> anthropic.Client:
        return anthropic.Client(**self._client_params)

    @cached_property
    def _async_client(self) -> anthropic.AsyncClient:
        return anthropic.AsyncClient(**self._async_client_params)

class MonitoredAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None
        self.total_tokens = 0
        self.action_count = 0
        self.successful_actions = 0
        self.use_wandb = False

    async def run(self, max_steps: int = 100):
        self.start_time = time.time()
        try:
            result = await super().run(max_steps)
            execution_time = time.time() - self.start_time
            success_rate = self.successful_actions / self.action_count if self.action_count > 0 else 0
            print({
                "execution_time": execution_time,
                "total_tokens": self._message_manager.state.history.current_tokens,
                "actions_performed": self.action_count,
                "success_rate": success_rate,
                "average_tokens_per_action": self.total_tokens / self.action_count if self.action_count > 0 else 0
            })
            history_list: AgentHistoryList = self.state.history

            total_steps = len(history_list.history)
            if self.use_wandb:
                print(f"Total steps count: {total_steps}")

            for i, history in enumerate(history_list.history, start=1):
                tokens_used = history.metadata.input_tokens if history.metadata else "unknown"
                duration = history.metadata.duration_seconds if history.metadata else "unknown"
                goal = history.model_output.current_state.next_goal if history.model_output else "no_goal"
                # success = "success" if history.metadata and history.metadata.success else "failed"

                if self.use_wandb:
                    print(f"Step {i}:")
                    print(f"  - Token cost: {tokens_used}")
                    print(f"  - Time usage: {duration} sec")
                    print(f"  - Goal: {goal}")
                    # print(f"  - Status: {success}")

            if self.use_wandb:
                wandb.log({
                    "execution_time": execution_time,
                    "total_tokens": self._message_manager.state.history.current_tokens,
                    "actions_performed": self.action_count,
                    "success_rate": success_rate,
                    "average_tokens_per_action": self.total_tokens / self.action_count if self.action_count > 0 else 0
                })

            return result
        except Exception as e:
            if self.use_wandb:
                wandb.log({"error": str(e)})
            raise e

    async def execute_action(self, *args, **kwargs):
        self.action_count += 1
        result = await super().execute_action(*args, **kwargs)
        if result.success:
            self.successful_actions += 1

        # Assume token usages are in results
        if hasattr(result, 'tokens_used'):
            self.total_tokens += result.tokens_used

        wandb.log({
            "action_success": result.success,
            "action_type": result.action_type if hasattr(result, 'action_type') else 'unknown',
            "action_duration": result.duration if hasattr(result, 'duration') else 0
        })

        return result