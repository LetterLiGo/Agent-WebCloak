"""
util_iterate.py - Dataset Iteration Utility

This utility script provides data structures and functions to iterate through the WebCloak
dataset. It parses the JSON dataset file and provides convenient access to test cases organized
by website and category.

Usage:
    from util_iterate import list_websites
    websites = list_websites()
    for website in websites:
        for test_case in website.data:
            print(test_case.id, test_case.name)
"""

import json
from dataclasses import dataclass

@dataclass
class TestCase:
    id: str
    website: str
    name: str
    count: int
    question: str = ""
    answer: str = ""

@dataclass
class Website:
    name: str
    prefix: str
    category: str
    length: int
    data: list[TestCase]

def list_websites(json_name = '../../dataset/data.json') -> list[Website]:
    websites = []
    with open(json_name, 'r', encoding='utf-8') as file_s:
        data = json.loads(file_s.read())
        print('Dataset Version', data['version'])
        for item in data['data']:
            test_cases = []
            for case in item['data']:
                if 'count' in case:
                    test_cases.append(TestCase(id=case['id'], website=item['website'],
                                               name=case['name'], count=case['count']))
                else:
                    test_cases.append(TestCase(id=case['id'], website=item['website'],
                                               name=case['name'], count=-1))
            websites.append(Website(name=item['website'], prefix=item['prefix'],
                                    category=item['category'], length=len(test_cases), data=test_cases))
    return websites

if __name__ == '__main__':
    websites = list_websites()
    test_case_count = 0
    for website in websites:
        print('---')
        print(website.name, 'of', website.category, 'with Length', website.length)
        print('---')
        for test_case in website.data:
            test_case_count += 1
            print(test_case.id, test_case.name)
    print("Website count:", len(websites))
    print("Test case count:", test_case_count)