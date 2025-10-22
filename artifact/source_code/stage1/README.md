# Dynamic Structural Obfuscation Defense

This directory contains the implementation of the Dynamic Structural Obfuscation defense mechanism from the WebCloak paper.

## Overview

Dynamic Structural Obfuscation is a defense technique that modifies the structure of HTML pages to make it more difficult for LLM-driven web agents to extract visual assets and sensitive content. The defense works by:

1. **HTML Structure Transformation**: Converting `<img>` tags to other HTML elements (div, section)
2. **Attribute Obfuscation**: Replacing `src` attributes with dynamically generated random attribute names
3. **Content Encoding**: Encoding image URLs with a simple character shift cipher
4. **JavaScript Restoration**: Adding client-side JavaScript to decode and restore images for legitimate browser viewing
5. **Honeypot Injection**: Adding fake `src` attributes with decoy URLs to mislead scrapers

## Usage

To run the Dynamic Structural Obfuscation defense:

```bash
cd source_code
python stage1/defend.py
```

## Output

- **Logs**: The defense process log example is stored in `main.log`
- **Defended Files**: The obfuscated HTML files are saved in the `dataset` directory with names following the pattern `index.html_edited.html`
- **JavaScript Files**: Restoration scripts are generated in the `index_files/` directories with random names

## Technical Details

The defense implements several obfuscation techniques:

- **Dynamic Attribute Names**: Uses random 3-6 character strings as attribute names instead of `src`
- **Shadow DOM**: Utilizes closed Shadow DOM to hide the actual image rendering logic
- **Site-Specific Styling**: Includes custom CSS rules for proper display across different websites
- **Performance Tracking**: Measures and reports processing times for each webpage

## Compatibility

The defense includes site-specific adaptations for major websites including Amazon, Google Travel, TripAdvisor, Kayak, and many others to ensure proper visual rendering after obfuscation.