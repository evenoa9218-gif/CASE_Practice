import json, os
with open('공법_모의_사례.json', encoding='utf-8') as f:
    data = json.load(f)
ids = ['공법_모의_2021_1차_사례', '공법_모의_2021_2차_사례', '공법_모의_2021_3차_사례', '공법_모의_2022_1차_사례', '공법_모의_2022_2차_사례', '공법_모의_2022_3차_사례', '공법_모의_2023_1차_사례', '공법_모의_2023_2차_사례']
found = {d.get('id'): d for d in data if d.get('id') in ids}
print("count:", len(found))
os.makedirs('items', exist_ok=True)
for i in ids:
    d = found.get(i)
    if d is None:
        print("MISSING:", i)
        continue
    pt = d.get('problemText') or ''
    rt = d.get('rubricText') or ''
    print(i, 'problemLen=', len(pt), 'rubricLen=', len(rt), 'hasRubric=', d.get('hasRubric'))
    with open(f'items/{i}.txt', 'w', encoding='utf-8') as out:
        out.write("=== problemText ===\n")
        out.write(pt)
        out.write("\n\n=== rubricText ===\n")
        out.write(rt)
