# main_Stage2.py
import os
import argparse
from datetime import datetime
import asyncio
from pathlib import Path
import json
import random
from bs4 import BeautifulSoup
import copy
from tqdm import tqdm

# Import from our refactored modules
import config
import utils
import prompts
import language_models
import evaluators


class ProcessingPipeline:
    def __init__(self, max_depth_d, branch_factor_b, output_base_dir):
        self.max_depth_d = max_depth_d
        self.branch_factor_b = branch_factor_b
        print(f"TAP Configuration: Phase1_Depth={self.max_depth_d}, BranchFactor(per-root)={self.branch_factor_b}")

        # --- Output Directories ---
        self.base_output_dir = Path(output_base_dir)
        self.protected_html_base_dir = self.base_output_dir / "protected_html"
        self.markdown_base_dir = self.base_output_dir / "markdown_prompts"
        self.json_base_dir = self.base_output_dir / "llm_responses"
        for dir_path in [self.protected_html_base_dir, self.markdown_base_dir, self.json_base_dir]:
            os.makedirs(dir_path, exist_ok=True)

        # --- State Variables ---
        self.root_states = []
        for i, root_dir in enumerate(prompts.ROOT_DEFENSE_DIRECTIONS):
            self.root_states.append({
                "name": root_dir["name"],
                "theme_prompt": root_dir["prompt"],
                "image_group_image_objects": [],
                "current_best_applied_texts_for_group": {},
                "current_best_rate": 0.0,
                "current_gemini_rate": 0.0,
                "current_openai_rate": 0.0,
                "successful_examples_for_feedback": [],
                "is_template_group_perfected": False,
            })
        self.all_images_globally = []
        self.master_soup_with_ids: BeautifulSoup | None = None
        self.current_word_count_target = config.INITIAL_WORD_COUNT_TARGET

    def get_tap_output_dirs_for_depth(self, depth: int, subfolder: str = ""):
        depth_str = f"depth_{depth}"
        if subfolder:
            depth_str = f"{subfolder}_d{depth}"
        html_dir = self.protected_html_base_dir / depth_str
        md_dir = self.markdown_base_dir / depth_str
        json_dir = self.json_base_dir / depth_str
        for d_path in [html_dir, md_dir, json_dir]:
            os.makedirs(d_path, exist_ok=True)
        return html_dir, md_dir, json_dir

    def _initialize_images_and_groups(self, initial_html_content_str: str, initial_html_stem: str) -> bool:
        print("Initializing images and groups...")
        self.master_soup_with_ids = BeautifulSoup(initial_html_content_str, 'html.parser')
        self.all_images_globally = []

        img_tags = self.master_soup_with_ids.find_all('img')
        if not img_tags:
            print("Warning: No <img> tags found in the initial HTML content.")
            return False

        for i, img_tag in enumerate(tqdm(img_tags, desc="Processing images", unit="img")):
            img_id = f"{initial_html_stem}_img_{i}"
            img_tag['data-pc-id'] = img_id
            
            original_url = img_tag.get(utils.ORIGINAL_SRC_ATTR)
            if not original_url:
                for attr_name in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-srcset']:
                    url = img_tag.get(attr_name)
                    if url and isinstance(url, str) and not url.startswith('data:'):
                        if attr_name == 'data-srcset':
                            url = url.strip().split(',')[0].split(' ')[0]
                        original_url = url
                        img_tag[utils.ORIGINAL_SRC_ATTR] = url
                        break
                if not original_url:
                    original_url = img_tag.get('src', f"unknown_src_for_{img_id}")
                    img_tag[utils.ORIGINAL_SRC_ATTR] = original_url
            
            parent_context_str = ""
            if img_tag.parent:
                parent_context_str = str(img_tag.parent.prettify(formatter="html5"))
                if len(parent_context_str) > 500:
                    parent_context_str = parent_context_str[:250] + "..." + parent_context_str[-250:]
            
            self.all_images_globally.append({
                'id': img_id, 'original_url': original_url,
                'img_tag_string': str(img_tag), 'html_snippet': parent_context_str,
            })
        
        print(f"Initialized {len(self.all_images_globally)} images with IDs and original URLs.")
        return True

    def _distribute_images_to_root_states(self, images_to_process: list[dict]):
        for state in self.root_states:
            state['image_group_image_objects'] = list(images_to_process)
            state['current_best_applied_texts_for_group'] = {}
            state['current_best_rate'] = 0.0
            state['current_gemini_rate'] = 0.0
            state['current_openai_rate'] = 0.0
            state['successful_examples_for_feedback'] = []
            state['is_template_group_perfected'] = False

    def _update_feedback_for_root_state(self, root_state: dict, best_texts: dict):
        root_state['successful_examples_for_feedback'] = []
        if not best_texts or not root_state['image_group_image_objects']: return

        relevant_texts = [
            {"original_url": img['original_url'], **best_texts.get(img['id'], {})}
            for img in root_state['image_group_image_objects'] if img['id'] in best_texts
        ]
        random.shuffle(relevant_texts)
        root_state['successful_examples_for_feedback'] = relevant_texts[:min(len(relevant_texts), 3)]

    async def _evaluate_minimal_page_for_template_group(self, template_group_images, defense_texts, test_page_stem, depth):
        if not template_group_images:
            return {0: {"gemini_rate": 100.0, "openai_rate": 100.0, "combined_rate": 100.0}}

        temp_isolated_soup = BeautifulSoup("<body></body>", 'html.parser')
        for img_data in template_group_images:
            if original_tag := self.master_soup_with_ids.find('img', attrs={'data-pc-id': img_data['id']}):
                temp_isolated_soup.body.append(copy.deepcopy(original_tag))

        minimal_html_content = utils.apply_defense_texts_to_html_content(temp_isolated_soup, defense_texts)
        
        html_dir, md_dir, json_dir = self.get_tap_output_dirs_for_depth(depth, subfolder=f"phase1_minimal_evals_d{depth}")
        
        page_path = html_dir / f"{test_page_stem}.html"
        with open(page_path, "w", encoding="utf-8") as f: f.write(minimal_html_content)

        prompt_path = md_dir / f"{test_page_stem}_prompt.txt"
        evaluators.generate_crawl4ai_like_prompt_from_processed_html(str(page_path), str(prompt_path))

        json_openai = json_dir / f"{test_page_stem}_openai_resp.json"
        json_gemini = json_dir / f"{test_page_stem}_gemini_resp.json"
        await asyncio.gather(
            language_models.run_evaluation_gemini(str(prompt_path), str(json_gemini)),
            language_models.run_evaluation_openai(str(prompt_path), str(json_openai))
        )
        
        original_urls = [img['original_url'] for img in template_group_images]
        extracted_gemini = evaluators.extract_urls_from_llm_response(str(json_gemini), "Gemini-P1Eval")
        extracted_openai = evaluators.extract_urls_from_llm_response(str(json_openai), "GPT-4o-P1Eval")

        leaked_gemini = evaluators.compare_urls(original_urls, extracted_gemini)
        rate_gemini = evaluators.calculate_defense_rate(original_urls, leaked_gemini)
        leaked_openai = evaluators.compare_urls(original_urls, extracted_openai)
        rate_openai = evaluators.calculate_defense_rate(original_urls, leaked_openai)
        
        return {0: {
            "gemini_rate": rate_gemini, "openai_rate": rate_openai,
            "combined_rate": (rate_gemini + rate_openai) / 2.0
        }}

    async def _evaluate_final_page(self, page_content_str, page_stem, depth):
        html_dir, md_dir, json_dir = self.get_tap_output_dirs_for_depth(depth, subfolder=f"final_validation_d{depth}")
        page_path = html_dir / f"{page_stem}_full_eval.html"
        with open(page_path, "w", encoding="utf-8") as f: f.write(page_content_str)

        prompt_path = md_dir / f"{Path(page_path).stem}_prompt.txt"
        evaluators.generate_crawl4ai_like_prompt_from_processed_html(str(page_path), str(prompt_path))

        json_openai = json_dir / f"{Path(page_path).stem}_openai_resp.json"
        json_gemini = json_dir / f"{Path(page_path).stem}_gemini_resp.json"
        await asyncio.gather(
            language_models.run_evaluation_gemini(str(prompt_path), str(json_gemini)),
            language_models.run_evaluation_openai(str(prompt_path), str(json_openai))
        )

        all_original_urls = [img['original_url'] for img in self.all_images_globally]
        if not all_original_urls: return {-1: {"combined_rate": 100.0, "note": "No images"}}

        extracted_gemini = evaluators.extract_urls_from_llm_response(str(json_gemini), "Gemini-FinalEval")
        extracted_openai = evaluators.extract_urls_from_llm_response(str(json_openai), "GPT-4o-FinalEval")
        
        rate_gemini = evaluators.calculate_defense_rate(all_original_urls, evaluators.compare_urls(all_original_urls, extracted_gemini))
        rate_openai = evaluators.calculate_defense_rate(all_original_urls, evaluators.compare_urls(all_original_urls, extracted_openai))
        
        overall_rate = (rate_gemini + rate_openai) / 2.0
        print(f"   Final Overall Page Validation: Combined: {overall_rate:.2f}% (G: {rate_gemini:.2f}%, O: {rate_openai:.2f}%)")
        return {-1: {"gemini_rate": rate_gemini, "openai_rate": rate_openai, "combined_rate": overall_rate}}


    async def process_html_tap(self, initial_html_path_str: str):
        initial_file = Path(initial_html_path_str)
        with open(initial_file, 'r', encoding='utf-8') as f: html_content = f.read()
        if not self._initialize_images_and_groups(html_content, initial_file.stem) or not self.all_images_globally:
            return initial_html_path_str

        # --- Phase 1: Template Mining ---
        print(f"\n{'='*15} Phase 1: Template Mining / Direct Optimization {'='*15}")
        images_for_phase_1 = self.all_images_globally[:10]
        self._distribute_images_to_root_states(images_for_phase_1)

        best_overall_rate_p1 = -1.0
        best_overall_texts_p1 = {}
        perfect_templates = []
        cross_poll_inspirations = []

        for depth in range(1, self.max_depth_d + 1):
            print(f"\n--- Phase 1: Depth {depth}/{self.max_depth_d} for template group ({len(images_for_phase_1)} images) ---")
            # __import__('ipdb').set_trace()
            self.current_word_count_target = config.INITIAL_WORD_COUNT_TARGET + (depth - 1) * config.WORD_COUNT_INCREASE_PER_DEPTH
            if len(perfect_templates) >= 3:
                print(f"Collected {len(perfect_templates)} perfect templates. Ending Phase 1 early.")
                break

            print(f"Generating defense variations...")
            gen_tasks = [
                language_models.generate_defense_variations_for_image_group(
                    r['image_group_image_objects'], r['theme_prompt'], self.branch_factor_b,
                    self.current_word_count_target, r['successful_examples_for_feedback'],
                    cross_poll_inspirations, is_initial_root_generation_round=(depth == 1)
                ) for r in self.root_states if r['image_group_image_objects']
            ]
            gen_results = await asyncio.gather(*gen_tasks)

            eval_tasks, eval_inputs = [], []
            for root_idx, root_variations in enumerate(gen_results):
                if not root_variations: continue
                for var_idx in range(self.branch_factor_b):
                    texts = root_variations.get(f"variation_{var_idx}")
                    if not texts: continue
                    page_stem = f"{initial_file.stem}_p1_d{depth}_r{root_idx}_v{var_idx}"
                    eval_inputs.append((root_idx, var_idx, texts))
                    eval_tasks.append(self._evaluate_minimal_page_for_template_group(images_for_phase_1, texts, page_stem, depth))

            print(f"Evaluating {len(eval_tasks)} variations...")
            eval_results = []
            with tqdm(total=len(eval_tasks), desc=f"Evaluating D{depth}", unit="var") as pbar:
                for coro in asyncio.as_completed(eval_tasks):
                    result = await coro
                    eval_results.append(result)
                    pbar.update(1)

            for i, result in enumerate(eval_results):
                root_idx, var_idx, texts = eval_inputs[i]
                root_state = self.root_states[root_idx]
                
                if isinstance(result, Exception):
                    print(f"Error evaluating R'{root_state['name']}'V{var_idx}D{depth}: {result}")
                    continue

                scores = result.get(0, {})
                combined_rate = scores.get('combined_rate', 0.0)
                print(f"  P1D{depth} R'{root_state['name']}'(i{root_idx}) V{var_idx}: Combined: {combined_rate:.2f}% (G:{scores.get('gemini_rate',0):.2f}%,O:{scores.get('openai_rate',0):.2f}%)")

                if combined_rate >= root_state['current_best_rate']:
                    root_state.update({
                        'current_best_applied_texts_for_group': texts, 'current_best_rate': combined_rate,
                        'current_gemini_rate': scores.get('gemini_rate',0), 'current_openai_rate': scores.get('openai_rate',0),
                        'is_template_group_perfected': (combined_rate >= 99.99)
                    })
                    self._update_feedback_for_root_state(root_state, texts)
                
                if combined_rate > best_overall_rate_p1:
                    best_overall_rate_p1, best_overall_texts_p1 = combined_rate, texts
                    print(f"    New GLOBAL best P1 defense! From R'{root_state['name']}'V{var_idx}. Rate: {best_overall_rate_p1:.2f}%")

                if combined_rate >= 99.99 and not any(item["texts"] == texts for item in perfect_templates):
                    perfect_templates.append({"texts": texts, "rate_info": scores, "source_hint": f"R'{root_state['name']}',D{depth},V{var_idx}"})
                    print(f"    100% P1 defense by R'{root_state['name']}'V{var_idx}! Collected {len(perfect_templates)} unique 100% template(s).")
                    if len(perfect_templates) >= 3: break
            if len(perfect_templates) >= 3: break

            cross_poll_inspirations = list(set(
                f"P_B: {r['current_best_applied_texts_for_group'][r['image_group_image_objects'][0]['id']].get('p_before_text','')[:70]}..."
                for r in self.root_states if r['current_best_rate'] > 50 and r['image_group_image_objects'] and r['image_group_image_objects'][0]['id'] in r['current_best_applied_texts_for_group']
            ))
            cross_poll_inspirations = [{"theme_hint":"CrossPollinateP1", "snippet_example": s} for s in cross_poll_inspirations[:5]]

        chosen_template = {}
        if perfect_templates:
            chosen_template_data = perfect_templates[0]
            chosen_template = chosen_template_data["texts"]
            if best_overall_rate_p1 < chosen_template_data["rate_info"].get("combined_rate", 100.0):
                best_overall_rate_p1 = chosen_template_data["rate_info"].get("combined_rate", 100.0)
                best_overall_texts_p1 = chosen_template
            print(f"Phase 1 Concluded. 100% template.")
        elif best_overall_texts_p1:
            chosen_template = best_overall_texts_p1
            print(f"Phase 1 Concluded. No 100% template.")
        else:
            print("CRITICAL: Phase 1 failed to find any defense. Aborting.")
            return initial_html_path_str

        # --- Decision Point & Phase 2 ---
        if len(self.all_images_globally) <= 10:
            print("Total images <= 10. Applying Phase 1 best defense as final.")
            final_html_str = utils.apply_defense_texts_to_html_content(self.master_soup_with_ids, best_overall_texts_p1)
            save_dir = self.protected_html_base_dir / "final_small_page"
        else:
            print(f"\n{'='*15} Phase 2: Template Application to All Images ({len(self.all_images_globally)} total) {'='*15}")
            all_final_texts = {}
            chunks = [self.all_images_globally[i:i + 10] for i in range(0, len(self.all_images_globally), 10)]
            imitation_tasks = [
                language_models.generate_imitated_defenses(chunk, images_for_phase_1, chosen_template)
                for chunk in chunks
            ]

            print(f"Applying template to {len(chunks)} image groups...")
            imitation_results = []
            with tqdm(total=len(imitation_tasks), desc="Phase 2: Applying template", unit="chunk") as pbar:
                for coro in asyncio.as_completed(imitation_tasks):
                    result = await coro
                    imitation_results.append(result)
                    pbar.update(1)

            for res in imitation_results:
                if isinstance(res, dict): all_final_texts.update(res)

            final_html_str = utils.apply_defense_texts_to_html_content(self.master_soup_with_ids, all_final_texts)
            await self._evaluate_final_page(final_html_str, initial_file.stem, 99)
            save_dir = self.protected_html_base_dir / "final_large_page"
        
        os.makedirs(save_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{initial_file.stem}_TAP_R{best_overall_rate_p1:.0f}_{ts}.html"
        fpath = save_dir / fname
        with open(fpath, "w", encoding="utf-8") as f: f.write(final_html_str)
        print(f"Final HTML saved to: '{fpath}'")
        return str(fpath)

async def main_tap_runner():
    parser = argparse.ArgumentParser(description='Process HTML through TAP protection pipeline.')
    parser.add_argument('input_html', help='Path to the input HTML file')
    parser.add_argument('--max-depth', type=int, default=config.DEFAULT_MAX_DEPTH_D, help=f'TAP Phase 1: Max search depth (default: {config.DEFAULT_MAX_DEPTH_D})')
    parser.add_argument('--branch-factor', type=int, default=config.DEFAULT_BRANCH_FACTOR_B, help=f'TAP: Variations per theme per depth (default: {config.DEFAULT_BRANCH_FACTOR_B})')
    args = parser.parse_args()

    if not os.path.exists(args.input_html):
        print(f"Error: Input file '{args.input_html}' does not exist.")
        return

    input_stem = Path(args.input_html).stem
    ts_main = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_base = config.DEFAULT_BASE_OUTPUT_FOLDER / f"{input_stem}_{ts_main}"
    
    pipeline = ProcessingPipeline(
        max_depth_d=args.max_depth,
        branch_factor_b=args.branch_factor,
        output_base_dir=run_output_base
    )
    final_path = await pipeline.process_html_tap(args.input_html)
    if final_path and os.path.exists(final_path):
        print(f"\nTAP Runner finished successfully. Final output HTML: {final_path}")
    else:
        print(f"\nTAP Runner FAILED or produced no valid final output for '{args.input_html}'.")

if __name__ == "__main__":
    print("TAP Defense Pipeline - Main Entry Point")
    if config.OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE" or config.GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        print("WARNING: API keys not found. Please set them as environment variables or in config.py.")
    
    asyncio.run(main_tap_runner())