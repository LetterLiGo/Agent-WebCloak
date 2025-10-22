# language_models.py
import json
import asyncio
from math import ceil
from openai import AsyncOpenAI
import google.generativeai as genai

import config
import prompts

# --- Client and Semaphore Initialization ---
if config.GOOGLE_API_KEY and config.GOOGLE_API_KEY != "YOUR_GOOGLE_API_KEY_HERE":
    try:
        genai.configure(api_key=config.GOOGLE_API_KEY)
    except Exception as e:
        print(f"Warning: Error configuring Google API with provided key: {e}. Gemini tests may fail.")

openai_client_gpt4mini_defgen = AsyncOpenAI(
    api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL
)
openai_client_gpt4o_tester = AsyncOpenAI(
    api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL
)

openai_client_gemini = None
if config.GOOGLE_API_KEY and config.GOOGLE_API_KEY != "YOUR_GOOGLE_API_KEY_HERE":
    if hasattr(config, 'GOOGLE_BASE_URL') and config.GOOGLE_BASE_URL:
        openai_client_gemini = AsyncOpenAI(
            api_key=config.GOOGLE_API_KEY,
            base_url=config.GOOGLE_BASE_URL
        )

gpt4mini_semaphore = asyncio.Semaphore(config.GPT4MINI_CONCURRENCY)
gpt4o_tester_semaphore = asyncio.Semaphore(config.GPT4O_CONCURRENCY)
gemini_semaphore = asyncio.Semaphore(config.GEMINI_CONCURRENCY)


async def _fetch_one_defense_variation_from_llm(
    image_group_data_batch: list[dict],
    root_defense_theme_prompt: str,
    variation_index: int,
    total_variations_for_theme: int,
    current_word_count_target: int,
    group_specific_successful_examples: list[dict] | None,
    cross_pollination_examples: list[dict] | None,
    is_initial_root_generation: bool = False,
    temperature: float = 0.75
) -> dict | None:
    image_ids_in_batch = [img['id'] for img in image_group_data_batch]
    
    full_prompt = prompts.create_variation_prompt(
        image_group_data_batch, root_defense_theme_prompt, variation_index,
        total_variations_for_theme, current_word_count_target,
        group_specific_successful_examples, cross_pollination_examples,
        is_initial_root_generation
    )

    retries = 3
    delay_seconds = 5
    for attempt in range(retries):
        try:
            async with gpt4mini_semaphore:
                response = await openai_client_gpt4mini_defgen.chat.completions.create(
                    model=config.OPENAI_MODEL_NAME_DEFGEN,
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    timeout=300.0
                )
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                llm_response_content = response.choices[0].message.content.strip()
                try:
                    parsed_json = json.loads(llm_response_content)
                    if not isinstance(parsed_json, dict): raise ValueError("Top level not a dict.")

                    for img_id_in_request in image_ids_in_batch:
                        if img_id_in_request not in parsed_json:
                            parsed_json[img_id_in_request] = {"p_before_text": "Error: Missing from LLM response.", "alt_text": "Error", "p_after_text": "Error"}
                        elif not (isinstance(parsed_json[img_id_in_request], dict) and \
                                  all(k in parsed_json[img_id_in_request] for k in ['p_before_text', 'alt_text', 'p_after_text'])):
                            parsed_json[img_id_in_request] = {"p_before_text": "Error: Malformed structure from LLM.", "alt_text": "Error", "p_after_text": "Error"}
                    return parsed_json
                except (json.JSONDecodeError, ValueError) as e_parse:
                    print(f"Error: Failed to parse/validate JSON from LLM for Var {variation_index + 1} (Attempt {attempt+1}): {e_parse}")
            else:
                print(f"Error: Invalid or empty response structure from LLM for Var {variation_index + 1} (Attempt {attempt+1}).")
        except Exception as e_api:
            print(f"Error during LLM API call for Var {variation_index + 1} (Attempt {attempt+1}/{retries}): {type(e_api).__name__}: {e_api}")

        if attempt < retries - 1:
            current_delay = delay_seconds * (2 ** attempt)
            await asyncio.sleep(current_delay)
        else:
            print(f"Error: Max retries ({retries}) reached for LLM call for Var {variation_index + 1}.")
            return {img_id: {"p_before_text": "Error: Max LLM retries.", "alt_text": "Max retries.", "p_after_text": "Max retries."} for img_id in image_ids_in_batch}
    return None

async def generate_defense_variations_for_image_group(
    image_group_data: list[dict],
    root_defense_theme_prompt: str,
    num_variations_to_generate: int,
    current_word_count_target: int,
    group_specific_successful_examples: list[dict] | None,
    cross_pollination_examples: list[dict] | None,
    temperature: float = 0.75,
    is_initial_root_generation_round: bool = False
) -> dict | None:
    all_variations_aggregated: dict = {f"variation_{i}": {} for i in range(num_variations_to_generate)}
    num_physical_batches = ceil(len(image_group_data) / config.BATCH_SIZE_IMAGES_PER_LLM_CALL)

    for i_batch in range(num_physical_batches):
        start_idx = i_batch * config.BATCH_SIZE_IMAGES_PER_LLM_CALL
        end_idx = start_idx + config.BATCH_SIZE_IMAGES_PER_LLM_CALL
        current_physical_batch_img_data = image_group_data[start_idx:end_idx]

        if not current_physical_batch_img_data: continue

        llm_tasks = []
        for var_idx in range(num_variations_to_generate):
            llm_tasks.append(
                _fetch_one_defense_variation_from_llm(
                    image_group_data_batch=current_physical_batch_img_data,
                    root_defense_theme_prompt=root_defense_theme_prompt,
                    variation_index=var_idx,
                    total_variations_for_theme=num_variations_to_generate,
                    current_word_count_target=current_word_count_target,
                    group_specific_successful_examples=group_specific_successful_examples,
                    cross_pollination_examples=cross_pollination_examples,
                    is_initial_root_generation=is_initial_root_generation_round,
                    temperature=temperature
                )
            )
        
        results_for_physical_batch = await asyncio.gather(*llm_tasks, return_exceptions=True)

        for var_idx in range(num_variations_to_generate):
            var_key = f"variation_{var_idx}"
            result = results_for_physical_batch[var_idx]

            if isinstance(result, Exception):
                print(f"Error fetching variation {var_idx} for batch {i_batch}: {result}")
                for img_data_item in current_physical_batch_img_data:
                    all_variations_aggregated[var_key][img_data_item['id']] = {
                        "p_before_text": f"Error: LLM task failed Var {var_idx+1}",
                        "alt_text": "LLM task fail", "p_after_text": "LLM task fail"
                    }
                continue

            if result:
                all_variations_aggregated[var_key].update(result)
            else:
                for img_data_item in current_physical_batch_img_data:
                    if img_data_item['id'] not in all_variations_aggregated[var_key]:
                        all_variations_aggregated[var_key][img_data_item['id']] = {
                            "p_before_text": f"Error: LLM gen failed Var {var_idx+1}, Batch {i_batch+1}",
                            "alt_text": "", "p_after_text": ""
                        }
    return all_variations_aggregated


async def generate_imitated_defenses(
    target_images_data: list[dict],
    template_image_group_data: list[dict],
    template_defense_texts: dict[str, dict[str, str]],
    temperature: float = 0.5
) -> dict | None:
    if not target_images_data:
        return None
    
    target_image_ids_in_batch = [img['id'] for img in target_images_data]
    full_prompt = prompts.create_imitation_prompt(target_images_data, template_image_group_data, template_defense_texts)

    retries = 3
    delay_seconds = 5
    for attempt in range(retries):
        try:
            async with gpt4mini_semaphore:
                response = await openai_client_gpt4mini_defgen.chat.completions.create(
                    model=config.OPENAI_MODEL_NAME_DEFGEN,
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    timeout=300.0
                )
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                llm_response_content = response.choices[0].message.content.strip()
                try:
                    parsed_json = json.loads(llm_response_content)
                    if not isinstance(parsed_json, dict): raise ValueError("Top level not a dict for imitation response.")
                    
                    for img_id in target_image_ids_in_batch:
                        if img_id not in parsed_json:
                            parsed_json[img_id] = {"p_before_text": "Error: Missing from Imitation LLM.", "alt_text": "Error", "p_after_text": "Error"}
                        elif not (isinstance(parsed_json[img_id], dict) and \
                                  all(k in parsed_json[img_id] for k in ['p_before_text', 'alt_text', 'p_after_text'])):
                            parsed_json[img_id] = {"p_before_text": "Error: Malformed structure from Imitation LLM.", "alt_text": "Error", "p_after_text": "Error"}
                    return parsed_json
                except (json.JSONDecodeError, ValueError) as e_parse:
                    print(f"Error: Failed to parse/validate JSON from Imitation LLM (Attempt {attempt+1}): {e_parse}")
            else:
                print(f"Error: Invalid or empty response structure from Imitation LLM (Attempt {attempt+1}).")
        except Exception as e_api:
            print(f"Error during Imitation LLM API call (Attempt {attempt+1}/{retries}): {type(e_api).__name__}: {e_api}")

        if attempt < retries - 1:
            current_delay = delay_seconds * (2 ** attempt)
            await asyncio.sleep(current_delay)
        else:
            print(f"Error: Max retries ({retries}) reached for Imitation LLM call.")
            return {img_id: {"p_before_text": "Error: Max LLM retries (Imitation).", "alt_text": "Max retries.", "p_after_text": "Max retries."} for img_id in target_image_ids_in_batch}
    return None

async def run_evaluation_gemini(input_prompt_path_str: str, output_json_path_str: str):
    async with gemini_semaphore:
        try:
            if not config.GOOGLE_API_KEY or config.GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f); return
            
            with open(input_prompt_path_str, 'r', encoding='utf-8') as f: input_content = f.read()
            if not input_content.strip():
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([],f); return

            if openai_client_gemini:
                response = await openai_client_gemini.chat.completions.create(
                    model=config.GEMINI_MODEL_NAME_TESTER,
                    messages=[{"role": "user", "content": input_content}],
                    temperature=0.3,
                )
                output_content = ""
                if response.choices and response.choices[0].message and response.choices[0].message.content:
                    output_content = response.choices[0].message.content
            else:
               
                model = genai.GenerativeModel(config.GEMINI_MODEL_NAME_TESTER)
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                response = await model.generate_content_async(input_content, safety_settings=safety_settings)
                
                output_content = ""
                if response.candidates:
                    first_candidate = response.candidates[0]
                    if first_candidate.content and first_candidate.content.parts:
                        output_content = "".join(part.text for part in first_candidate.content.parts if hasattr(part, 'text'))
                if not output_content and hasattr(response, 'text'):
                    output_content = response.text
            
            with open(output_json_path_str, 'w', encoding='utf-8') as f:
                f.write(output_content if output_content else json.dumps([]))
        
        except FileNotFoundError:
            with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f)
        except Exception as e:
            print(f"Error in run_evaluation_gemini (prompt: {output_json_path_str}): {type(e).__name__} - {e}")
            try:
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f)
            except Exception as e_write: print(f"Additionally, failed to write empty JSON on Gemini error: {e_write}")

'''async def run_evaluation_gemini(input_prompt_path_str: str, output_json_path_str: str):
    async with gemini_semaphore:
        try:
            if not config.GOOGLE_API_KEY or config.GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f); return
            
            with open(input_prompt_path_str, 'r', encoding='utf-8') as f: input_content = f.read()
            if not input_content.strip():
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([],f); return

            model = genai.GenerativeModel(config.GEMINI_MODEL_NAME_TESTER)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            response = await model.generate_content_async(input_content, safety_settings=safety_settings)
            
            output_content = ""
            if response.candidates:
                first_candidate = response.candidates[0]
                if first_candidate.content and first_candidate.content.parts:
                    output_content = "".join(part.text for part in first_candidate.content.parts if hasattr(part, 'text'))
            if not output_content and hasattr(response, 'text'):
                output_content = response.text
            
            with open(output_json_path_str, 'w', encoding='utf-8') as f:
                f.write(output_content if output_content else json.dumps([]))
        
        except FileNotFoundError:
            with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f)
        except Exception as e:
            print(f"Error in run_evaluation_gemini (prompt: {output_json_path_str}): {type(e).__name__} - {e}")
            try:
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f)
            except Exception as e_write: print(f"Additionally, failed to write empty JSON on Gemini error: {e_write}")
'''
async def run_evaluation_openai(input_prompt_path_str: str, output_json_path_str: str):
    async with gpt4o_tester_semaphore:
        try:
            if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f); return

            with open(input_prompt_path_str, 'r', encoding='utf-8') as f: input_content = f.read()
            if not input_content.strip():
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([],f); return

            response = await openai_client_gpt4o_tester.chat.completions.create(
                model=config.OPENAI_MODEL_NAME_TESTER,
                messages=[{"role": "user", "content": input_content}],
                temperature=0.3,
            )
            output_content = ""
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                output_content = response.choices[0].message.content
            
            with open(output_json_path_str, 'w', encoding='utf-8') as f:
                f.write(output_content if output_content else json.dumps([]))
        except FileNotFoundError:
            with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f)
        except Exception as e:
            print(f"Error in run_evaluation_openai (prompt: {output_json_path_str}): {type(e).__name__} - {e}")
            try:
                with open(output_json_path_str, 'w', encoding='utf-8') as f: json.dump([], f)
            except Exception as e_write: print(f"Additionally, failed to write empty JSON on GPT-4o error: {e_write}")