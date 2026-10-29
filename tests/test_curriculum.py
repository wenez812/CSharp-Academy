import json
from pathlib import Path

def test_curriculum_shape():
    data=json.loads((Path(__file__).resolve().parents[1]/'curriculum'/'curriculum.json').read_text(encoding='utf-8'))
    assert len(data)==28
    assert len({x['id'] for x in data})==28
    assert all(len(x.get('practice_tasks', [])) >= 2 for x in data)
    assert all(x.get('title') and x.get('explanation') and x.get('example_code') for x in data)
