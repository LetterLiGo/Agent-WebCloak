Stage2 program generates invisible defense text that causes LLM-based webagent to return placeholder messages instead of actual image URLs, while remaining completely hidden from human users.

## **Key Features**

- **Two-Phase Protection**: Template mining for small pages (≤10 images), template application for large pages
- **Four Defense Themes**: Mediated resolution, safety alignment triggers, false contextualization, and misleading instructions
- **Triple-Layer Defense**: Hidden text before/after images plus modified alt attributes
- **Stealth Mechanisms**: Advanced CSS hiding techniques and randomized HTML elements
- **High Effectiveness**: Achieves ≥99.99% defense success rate against GPT-4o and Gemini

## **How It Works**

1. **Initialize**: Extract images and assign unique IDs
2. **Generate**: Create defense text using 4 parallel themes
3. **Evaluate**: Test effectiveness with Gemini and GPT-4o
4. **Apply**: Inject invisible defense elements into HTML
5. **Verify**: Confirm final protection success rate

## **Stage2 Usage Guide**

**Dependencies**

```jsx
pip install beautifulsoup4 openai google-generativeai html2text asyncio pathlib
```

**1. API Key Set**

```jsx
export GOOGLE_API_KEY="your_gemini_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
```

**2. Run Protect Program**

```bash
cd source_code/stage2
python main_stage2.py path/to/your/input.html
```

**Parameter Description**

- `input_html`: Input HTML file path (required)
- `-max-depth`: Stage 2 Phase 1 maximum search depth (default: 5)
- `-branch-factor`: Number of variations per theme per round (default: 2)

**3. Check Output**

After completion, results will be saved in: **stage2/Output**