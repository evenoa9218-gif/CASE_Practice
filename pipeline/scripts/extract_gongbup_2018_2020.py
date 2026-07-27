import json, os
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

base = str(WORK)

with open(os.path.join(base, '공법_모의_사례.json'), encoding='utf-8') as f:
    data = json.load(f)

ids = ["공법_모의_2018_2차_사례", "공법_모의_2018_3차_사례", "공법_모의_2019_1차_사례", "공법_모의_2019_2차_사례", "공법_모의_2019_3차_사례", "공법_모의_2020_1차_사례", "공법_모의_2020_2차_사례", "공법_모의_2020_3차_사례"]

found = {d.get('id'): d for d in data if d.get('id') in ids}

out_dir = os.path.join(base, 'items_2018_2020')
os.makedirs(out_dir, exist_ok=True)

with open(os.path.join(base, 'extract_info_2018_2020.txt'), 'w', encoding='utf-8') as info:
    info.write(f'total items in file: {len(data)}\n')
    for i in ids:
        d = found.get(i)
        if d is None:
            info.write(f"{i} | MISSING\n")
            continue
        pt = d.get('problemText') or ''
        rt = d.get('rubricText') or ''
        info.write(f"{i} | hasRubric={d.get('hasRubric')} | problemLen={len(pt)} | rubricLen={len(rt)}\n")
        with open(os.path.join(out_dir, f'{i}.txt'), 'w', encoding='utf-8') as out:
            out.write("=== problemText ===\n")
            out.write(pt)
            out.write("\n\n=== rubricText ===\n")
            out.write(rt)
