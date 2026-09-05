import re

with open(r'C:\Users\User\.gemini\antigravity\brain\577d565c-e66f-44e4-b8c9-08c1c0cb3668\.system_generated\steps\69\content.md', 'r', encoding='utf-8') as f:
    html = f.read()

links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
csvs = [l for l in links if 'csv' in l.lower()]
print(set(csvs))
