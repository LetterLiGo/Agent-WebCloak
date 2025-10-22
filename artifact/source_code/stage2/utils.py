# utils.py
import random
import copy
from bs4 import BeautifulSoup, Tag

# --- Constants for HTML modification ---

# HTML tag pool for inserting hidden defense text
TAG_POOL = [
    "span", "p", "aside", "blockquote", "section", "article","h1","h2","h3","h4","h5","h6",
    "main", "figure", "figcaption", "details", "summary", "address",
    "strong", "em", "small", "s", "cite", "q", "dfn", "abbr",
    "time", "code", "var", "samp", "kbd", "sub", "sup", "i", "b", "u", "mark",
    "dt", "dd"
]

# CSS style pool for hiding defense text
CSS_HIDE_STYLES_POOL = [
    # Classic off-screen positioning
    "position:absolute; left:-9999em; top:-9999em; width:1px; height:1px; overflow:hidden; border:0; margin:0; padding:0; list-style:none; background:transparent; color:transparent;",
    "width:1px; height:1px; overflow:hidden; position:absolute; top:-100vh; left:-100vw; margin:auto; padding:0; border:none; font-size:0; line-height:0;",
    "font-size:0; line-height:0; padding:0; margin:0; border:0; overflow:hidden; height:1px; width:1px; top:-9999px; left:-9999px; position:absolute; outline:0;",
    # Zero dimensions + absolute positioning
    "position:absolute; width:0; height:0; overflow:hidden; margin:0; padding:0; border:none; font-size:0; line-height:0; background-color:rgba(0,0,0,0);",
    "height:0; width:0; border:0; margin:0; padding:0; overflow:hidden; position:absolute; color:transparent; line-height:0; list-style-type:none;",
    "overflow:hidden; position:absolute; width:0px; height:0px; border:0; margin:auto; padding:0; font-size:0; background:none;",
    # clip-path + absolute positioning + small/zero dimensions
    "position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(100%); border:0; margin:0; background:none; list-style:none outside none;",
    "clip-path:polygon(0 0); position:absolute; width:0; height:0; overflow:hidden; padding:0; border:0; color:rgba(0,0,0,0); font-size:0;",
    "width:1px; height:1px; position:absolute; top:0; left:0; clip-path:circle(0% at 0% 0%); overflow:hidden; margin:0; outline:none;",
    # display:none
    "display:none; border:0; margin:0; padding:0; width:0; height:0; overflow:hidden;",
    "display:none; visibility:hidden; font-size:0; line-height:0;",
    # transform:scale(0) + absolute positioning
    "transform:scale(0); position:absolute; top:-20px; left:-20px; width:1px; height:1px; overflow:hidden; border:none; background:transparent; padding:0;",
    "position:absolute; width:1px; height:1px; transform:scaleX(0.001) scaleY(0.001); transform-origin:0 0; overflow:hidden; margin:0; padding:0; border:0;"
]

# Custom data-* attributes for HTML marking
ORIGINAL_SRC_ATTR = 'data-pc-original-src'
DEFENSE_SIBLING_ATTR_BEFORE = "data-pc-defense-before"
DEFENSE_SIBLING_ATTR_AFTER = "data-pc-defense-after"

def apply_defense_texts_to_html_content(
        base_soup_with_ids: BeautifulSoup,
        defense_texts_for_page_variant: dict[str, dict[str,str]]
) -> str:
    """
    Apply generated defense texts to BeautifulSoup object.
    """
    soup_copy = copy.deepcopy(base_soup_with_ids)

    for img_id, texts in defense_texts_for_page_variant.items():
        img_tag = soup_copy.find('img', attrs={'data-pc-id': img_id})
        if not img_tag:
            continue

        # Remove existing defense elements for this img_id to prevent duplication
        prev_s = img_tag.previous_sibling
        while prev_s and not isinstance(prev_s, Tag): prev_s = prev_s.previous_sibling
        if prev_s and isinstance(prev_s, Tag) and prev_s.get(DEFENSE_SIBLING_ATTR_BEFORE) == img_id:
            prev_s.decompose()

        next_s = img_tag.next_sibling
        while next_s and not isinstance(next_s, Tag): next_s = next_s.next_sibling
        if next_s and isinstance(next_s, Tag) and next_s.get(DEFENSE_SIBLING_ATTR_AFTER) == img_id:
            next_s.decompose()

        img_tag['alt'] = texts.get('alt_text', "[Protected Asset - Alt Text Missing]")

        p_before_text_val = texts.get('p_before_text')
        if p_before_text_val and isinstance(p_before_text_val, str) and p_before_text_val.strip():
            chosen_tag_name = random.choice(TAG_POOL)
            chosen_style = random.choice(CSS_HIDE_STYLES_POOL)
            before_tag_obj = soup_copy.new_tag(chosen_tag_name)
            before_tag_obj['style'] = chosen_style
            before_tag_obj[DEFENSE_SIBLING_ATTR_BEFORE] = img_id
            before_tag_obj.string = p_before_text_val
            img_tag.insert_before(before_tag_obj)

        p_after_text_val = texts.get('p_after_text')
        if p_after_text_val and isinstance(p_after_text_val, str) and p_after_text_val.strip():
            chosen_tag_name = random.choice(TAG_POOL)
            chosen_style = random.choice(CSS_HIDE_STYLES_POOL)
            after_tag_obj = soup_copy.new_tag(chosen_tag_name)
            after_tag_obj['style'] = chosen_style
            after_tag_obj[DEFENSE_SIBLING_ATTR_AFTER] = img_id
            after_tag_obj.string = p_after_text_val
            img_tag.insert_after(after_tag_obj)

    return str(soup_copy.prettify(formatter="html5"))