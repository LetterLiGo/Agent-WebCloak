from os import path
import re
import time
import random
import string

from tqdm import tqdm

from iterate import list_websites


def generate_random_string():
    length = random.randint(3, 6)
    random_string = ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
    return random_string


def html_reg_exp(website: str, test_case: str, use_dynamic: bool, html: str) -> (str, str, str):
    if website != 'imdb':
        script_pattern = r'<script\b[^>]*>.*?</script>'
        html = re.sub(script_pattern, '', html, flags=re.DOTALL)
    html_to_replace_img = (html.replace('data-default-src', 'src')
                           .replace('data-src', 'src'))

    # In case we get multiple src attributes
    def which_src_to_keep(match):
        if "./index_files/" in match.group(3):
            return match.group(2) + match.group(3)
        else:
            return match.group(1) + match.group(2)

    html_to_replace_img = re.sub(r'(src="[^"]*")([^>]*?)(src="[^"]*")', which_src_to_keep, html_to_replace_img)
    html_to_replace_img = re.sub(r'data-doc-\w+\s*=\s*["\'][^"\']*["\']', '', html_to_replace_img)

    img_tag_list_names = []
    src_list_names = []

    pattern_with_srcset = r'<img[^>]*?srcset\s*=\s*["\'][^"\']*["\'][^>]*?>'

    def replace_img_with_srcset(match):
        img_tag = random.choice(['div', 'section'])
        img_tag_list_names.append(img_tag)
        if use_dynamic:
            src_name = generate_random_string()
        else:
            src_name = 'antiscrapesrc'
        src_list_names.append(src_name)

        src_pattern = r'src\s*=\s*["\']([^"\']*)["\']'
        src_match = re.search(src_pattern, match.group(0))
        src_content = src_match.group(1) if src_match else ""

        srcset_pattern = r'srcset\s*=\s*["\']([^"\']*)["\']'
        srcset_match = re.search(srcset_pattern, match.group(0))
        srcset_content = srcset_match.group(1) if srcset_match else ""

        encoded_src = ''.join([chr((ord(c) + 3) % 256) for c in src_content])
        new_tag = match.group(0).replace(f'srcset="{srcset_content}"', 'removed=""')
        new_tag = new_tag.replace('<img', f'<{img_tag}').replace(f'src="{src_content}"', f'{src_name}="{encoded_src}"')

        if new_tag.rstrip().endswith('/>'):
            new_tag = new_tag.replace('/>', f'></{img_tag}>')
        if new_tag.rstrip().endswith('>'):
            new_tag = new_tag + f"</{img_tag}>"

        return new_tag

    pattern_only_src = r'<img[^>]*?src\s*=\s*["\'][^"\']*["\'][^>]*?>'

    def replace_img_only_src(match):
        img_tag = random.choice(['div', 'section'])
        if use_dynamic:
            src_name = generate_random_string()
        else:
            src_name = 'antiscrapesrc'
        img_tag_list_names.append(img_tag)
        src_list_names.append(src_name)

        src_pattern = r'src\s*=\s*["\']([^"\']*)["\']'
        src_match = re.search(src_pattern, match.group(0))
        src_content = src_match.group(1) if src_match else ""

        encoded_src = ''.join([chr((ord(c) + 3) % 256) for c in src_content])
        honey_pot_url = ("./index_files/" + generate_random_string() + random.choice(
            ["_", "-", ""]) + generate_random_string() + random.choice([".jpg", ".png", ".webp"]))
        new_tag = match.group(0).replace('<img', f'<{img_tag}').replace(f'src="{src_content}"',
                                                                        f'{src_name}="{encoded_src}" src="{honey_pot_url}"')

        if new_tag.rstrip().endswith('/>'):
            new_tag = new_tag.replace('/>', f'></{img_tag}>')
        if new_tag.rstrip().endswith('>'):
            new_tag = new_tag + f"</{img_tag}>"

        return new_tag

    # Apply the substitution
    modified_html = re.sub(pattern_with_srcset, replace_img_with_srcset, html_to_replace_img)
    modified_html = re.sub(pattern_only_src, replace_img_only_src, modified_html)

    # Remove all <source> tags with srcset attribute
    pattern_for_source = r'<source[^>]*?srcset\s*=\s*["\'][^"\']*["\'][^>]*?>'
    modified_html = re.sub(pattern_for_source, lambda x: "", modified_html)

    if use_dynamic:
        js_selectors = []
        for i, (tag, attr) in enumerate(zip(img_tag_list_names, src_list_names)):
            js_selectors.append(f'document.querySelector("{tag}[{attr}]")')

        combined_js_selector = ", ".join(js_selectors)
        if not js_selectors:
            combined_js_selector = '...document.querySelectorAll("aselement[antiscrapesrc]")'

        combined_url_tags = ", ".join([f'"{tag}"' for tag in src_list_names])
        js_part_1 = f"""
        var list = [{combined_js_selector}];
        var tags_list = [{combined_url_tags}];
        console.log(list);
        """
    else:
        combined_url_tags = ", ".join([f"'antiscrapesrc'" for _ in src_list_names])
        js_part_1 = f"""
        var list = document.querySelectorAll("aselement[antiscrapesrc]");
        var tags_list = [{combined_url_tags}];
        """

    site_specific_styles_items = {
        "agoda": """if (list[i].getAttribute("class").includes("tw-w-full")) list[i].style.minHeight = "400px";""",
        "allrecipes": """list[i].style.maxHeight = "unset"; if (list[i].getAttribute("class").includes("primary-image")) list[i].style.height = "320px";
                        if (list[i].getAttribute("class").includes("card__img")) {
                            list[i].style.height = "unset"; list[i].style.width = "100%"; list[i].style.aspectRatio = "282 / 188";
                        }""",
        "amazon": """list[i].style.backgroundSize = "contain";""",
        "apartmenttherapy": "list[i].style.aspectRatio = 1;",
        "behance": """if (list[i].getAttribute("class")) if (list[i].getAttribute("class").includes("rf-ribbon__image")) {
                            list[i].style.width = "31px"; list[i].style.height = "57px";
                            list[i].style.top = "-7px";
                        }""",
        "bleacherreport": """if (list[i].getAttribute("class").includes("nkk98f")) list[i].style.minHeight = "300px";""",
        "bonappetit": "list[i].style.aspectRatio = 1;",
        "canva": """if (!url.includes(".svg")) list[i].strpstyle.position = "absolute"; 
                    else list[i].style.height = "30px";""",
        "cbssports": """if (list[i].getAttribute("alt").includes("Image thumbnail")) {
                            list[i].style.height = "auto";
                            list[i].style.aspectRatio = "auto 670 / 377";
                        }""",
        "coroflot": """if (list[i].getAttribute("data-img-height") == null) list[i].style.minHeight = "200px";""",
        "cupofjo": """if (url.includes('Big-Salad')) list[i].style.height = "34px";""",
        "dittomusic": """if (width != null) {
                        list[i].style.width = width + "px";
                        list[i].style.backgroundSize = "contain";}""",
        "dribbble": """list[i].style.minWidth = "80px";""",
        "eventbrite": """if (list[i].getAttribute("class")) if (list[i].getAttribute("class").includes("full-width")) {
                            list[i].style.aspectRatio = "1.5";
                            list[i].style.borderRadius = "40px";
                        }""",
        "flipkart": """list[i].style.backgroundSize = "contain";""",
        "googletravel": """list[i].style.visibility = "visible";""",
        "goop": "list[i].style.aspectRatio = 1;",
        "havenly": """list[i].style.backgroundSize = "contain"; 
                      if (list[i].getAttribute("class").includes("image-21553")) list[i].style.height = "58px";""",
        "kayak": """if (list[i].getAttribute("class")) {
                        if (list[i].getAttribute("class").includes("js-image")) {
                            list[i].style.width = "174px"; list[i].style.height = "116px";
                        }
                        if (list[i].getAttribute("class").includes("mR2O-agency-logo")) {
                            list[i].style.width = "50px"; list[i].style.height = "26px";
                            if (list[i].getAttribute("alt")) {
                                if (list[i].getAttribute("alt").includes("Trip.com")) {
                                    list[i].style.backgroundSize = "contain";
                                    list[i].style.width = "unset"; list[i].style.height = "unset";
                                }
                            }
                        }
                    }""",
        "lazada": """list[i].style.width = "100%"; list[i].style.height = "100%";
                    if (list[i].getAttribute("alt")) if (list[i].getAttribute("alt").includes("Logo")) {
                        list[i].style.width = "127px"; list[i].style.height = "40px";
                    }""",
        "marthastewart": """list[i].style.position = "absolute";
                            if (list[i].getAttribute("class")) if (list[i].getAttribute("class").includes("primary-image__image")) {
                                list[i].style.position = "unset"; list[i].style.height = "320px";
                            }""",
        "mercadolivre": """list[i].style.width = "100%"; list[i].style.height = "100%";
                        if (list[i].getAttribute("class")) if (list[i].getAttribute("class").includes("ui-search-filter-official-store__image")) {
                            list[i].style.aspectRatio = "54 / 40";
                        }""",
        "poshmark": """if (list[i].getAttribute("class")) {
                            if (!list[i].getAttribute("class").includes("store-icon") && !list[i].getAttribute("class").includes("header__logo")) list[i].style.position = "absolute";
                            if (list[i].getAttribute("class").includes("ps--a")) list[i].style.display = "none";
                        } else list[i].style.position = "absolute";""",
        "rakuten": """list[i].style.backgroundSize = "contain";
                        if (list[i].getAttribute("class")) {
                            if (list[i].getAttribute("class").includes("h-100  obj-cover")) list[i].style.aspectRatio = "1";
                            if (list[i].getAttribute("class").includes("product-item__primary-image")) list[i].style.aspectRatio = "232 / 174";
                        }""",
        "thekitchn": """list[i].style.aspectRatio = 1;""",
        "ticketmaster": """list[i].style.backgroundSize = "contain";
                        if (list[i].getAttribute("alt")) {
                            if (list[i].getAttribute("alt").includes("sg_")) list[i].style.height = "188px";
                            if (list[i].getAttribute("alt").includes("logo")) list[i].style.width = "140px";
                        }
                        if (list[i].getAttribute("class")) {
                            if (list[i].getAttribute("class").includes("sc-c6cb1a20-1")) list[i].style.height = "300px";
                        }""" + ("""if (list[i].getAttribute("loading")) {
                                list[i].style.height = "188px";
                                list[i].style.width = "400px";
                            }""" if test_case == "5" else ""),
        "tripadvisor": """if (list[i].getAttribute("alt")) if (list[i].getAttribute("alt").includes("Tripadvisor")) list[i].style.backgroundSize = "contain";""",
        "walmart": """if (list[i].getAttribute("class")) {
                        if (list[i].getAttribute("class") == "db") list[i].style.aspectRatio = "1";
                        if (list[i].getAttribute("class") == "br-100 v-btm") list[i].style.flexShrink = "0";
                    }""",
    }

    site_specific_styles_global = {
        "amazon": """const aPage = document.getElementById('a-page');
                if (aPage) aPage.style.transform = "translateY(-20px)";""" if test_case == "1" else "",
        "tripadvisor": """
                const vildqElements = document.getElementsByClassName('vILDq e fbkSn');
                const oqgnyElements = document.getElementsByClassName('oqGNy');
                for (let el of vildqElements) el.style.width = "300px";
                for (let el of oqgnyElements) el.style.width = "300px";
                """,
    }

    js_to_add = """document.addEventListener('DOMContentLoaded', function() {\n""" + js_part_1 + """
    for (var i = 0; i < list.length; i++) {
        if (list[i] != null) {
            var url = list[i].getAttribute(tags_list[i]);
            console.log(list[i], url);
            url = Array.from(url).map(c => String.fromCharCode((c.charCodeAt(0) - 3 + 256) % 256)).join('');
            console.log(list[i], url);
            var height = list[i].getAttribute('height');
            var width = list[i].getAttribute('width');""" + ("""
            if ((!height || !width) && url) {
                var matches = url.match(/_(\\\d+)x(\\\d+)/);
                console.log(matches);
                if (matches && matches.length >= 3) {
                    width = Number(matches[1]);
                    height = Number(matches[2]);
                    if (width > 400) {
                        width /= 2; height /= 2;
                    }
                }
            }
            """ if website in ['craigslist', 'dittomusic'] else "") + """
            const shadow = list[i].attachShadow({mode: 'closed'});
            const style = document.createElement('style');
            style.textContent = `:host { 
                background-image: url("${url.replace('\"', '\\\\"')}") !important;
                background-position: center;
                background-repeat: no-repeat;
                display: block;
                max-width: 100%;
                max-height: 100%;
            }`;
            shadow.appendChild(style);

            list[i].style.maxWidth = "100%";
            list[i].style.maxHeight = "100%";
            if (height != null && width != null && height != "" && width != "") {
                list[i].style.display = "inline-block";
                if (height != 1 && width != 1 && height != 0 && width != 0) {
                    list[i].style.height = !isNaN(Number(height)) ? height + "px" : height;
                    list[i].style.width = !isNaN(Number(width)) ? width + "px" : width;
                }
                if (list[i].style.width == "auto") list[i].style.width = list[i].style.height;
                if (list[i].style.height == "auto") list[i].style.width = list[i].style.width;
                style.textContent += ` :host { background-size: cover; }`;
            } else {
                list[i].style.display = "block";
                list[i].style.transform = "none";
                list[i].style.inset = "0";
                style.textContent += ` :host { background-size: cover; }`;
            }
            """ + (site_specific_styles_items[website] if website in site_specific_styles_items else "") + """
        }
    }
    """ + (site_specific_styles_global[website] if website in site_specific_styles_global else "") + """
})
        """

    js_name = generate_random_string() + generate_random_string() + ".js"
    modified_html = modified_html.replace('</head>',
                                          f'<script src="./index_files/{js_name}"></script>\n</head>')

    return modified_html, js_to_add, js_name


if __name__ == '__main__':
    websites = list_websites('../../dataset/data.json')

    all_times = []
    website_times = {}

    for website in tqdm(websites):
        print(website.name, 'of', website.category, 'with Length', website.length)
        print('---')

        website_times[website.prefix] = []
        for test_case in tqdm(website.data):
            start_time = time.time()

            file_path = (path.dirname(__file__) + '/../../../dataset/artifact/' +
                         website.prefix + '/' + test_case.id + '/index.html')
            print(test_case.id, test_case.name, file_path)

            with open(file_path, 'r', encoding='utf-8') as file_r:
                result_html, result_js, js_name = html_reg_exp(website.prefix, test_case.id, True, file_r.read())
            with open(file_path + '_edited.html', 'w', encoding='utf-8') as file_w:
                file_w.write(result_html)
            with open(file_path.replace('index.html', f'index_files/{js_name}'), 'w', encoding='utf-8') as file_w:
                file_w.write(result_js)

            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000
            all_times.append(execution_time_ms)
            website_times[website.prefix].append(execution_time_ms)

            print(f"Processing time: {execution_time_ms:.2f} ms")

    # Print summary statistics
    print("\n--- Performance Summary ---")
    print(f"Overall average execution time: {sum(all_times) / len(all_times):.2f} ms")
    print(f"Min execution time: {min(all_times):.2f} ms")
    print(f"Max execution time: {max(all_times):.2f} ms")
    print("\n--- Per Website Statistics ---")

    for website, times in website_times.items():
        if times:  # Only print stats if we have data for this website
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            print(
                f"{website}: avg={avg_time:.2f} ms, min={min_time:.2f} ms, max={max_time:.2f} ms, samples={len(times)}")