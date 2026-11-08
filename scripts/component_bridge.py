"""JSON interface for Luomu CAD's independently implemented symbol engine."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src' if (ROOT/'src').is_dir() else ROOT))
from luomu_cad.component_library import assemble, catalogue, furniture_geometry

if __name__ == '__main__':
    action = sys.argv[1]
    data = json.loads(sys.stdin.read()) if action != 'catalog' else None
    if action == 'catalog':
        result = catalogue()
    elif action == 'build':
        result = assemble(data)
    elif action == 'furniture':
        result = furniture_geometry(data)
    elif action == 'probe':
        result=[]
        for item in catalogue()['furniture']:
            try:result.append({'key':item['key'],'name':item['name'],'ok':True,'entities':len(furniture_geometry(item)['entities'])})
            except Exception as error:result.append({'key':item['key'],'ok':False,'error':str(error)})
    else:
        raise ValueError('Use catalog/build/furniture')
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
