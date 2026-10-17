"""Downloads the Poly Haven (CC0) assets of the creek scene into art/creek/assets.

cd art/creek/assets && python3 ../../../tools/creek/fetch_assets.py all
"""
import json,sys,os,urllib.request
o=urllib.request.build_opener();o.addheaders=[("User-Agent","heres-creek-scene/1.0")];urllib.request.install_opener(o)
def get(u): return json.load(urllib.request.urlopen(u))
def dl(url,path):
    os.makedirs(os.path.dirname(path) or '.',exist_ok=True)
    if not os.path.exists(path): urllib.request.urlretrieve(url,path)
kind,res=(sys.argv[1],sys.argv[2]) if len(sys.argv)>2 else ('','')
for a in sys.argv[3:]:
    f=get(f'https://api.polyhaven.com/files/{a}')
    if kind=='hdri':
        dl(f['hdri'][res]['exr']['url'],f'hdri/{a}_{res}.exr')
    elif kind=='model':
        g=f['gltf'][res]['gltf']; base=f'models/{a}/'
        dl(g['url'],base+os.path.basename(g['url']))
        for p,i in g['include'].items(): dl(i['url'],base+p)
        if 'Alpha' in f: dl(f['Alpha'][res]['jpg']['url'],base+f'textures/{a}_alpha_{res}.jpg')
    else:
        for m in ['Diffuse','nor_gl','Rough','Displacement','AO']:
            if m in f: dl(f[m][res]['jpg']['url'] if 'jpg' in f[m][res] else f[m][res]['png']['url'],f'tex/{a}/{a}_{m}.jpg')
    print('ok',a)


if __name__ == "__main__" and sys.argv[1:] == ["all"]:
    import subprocess
    me = os.path.abspath(__file__)
    subprocess.run([sys.executable, me, "hdri", "4k", "rosendal_park_sunset_puresky"], check=True)
    subprocess.run([sys.executable, me, "model", "2k", "grass_medium_01", "grass_medium_02", "grass_bermuda_01",
                    "rock_moss_set_02", "shrub_sorrel_01", "periwinkle_plant", "moss_01"], check=True)
    subprocess.run([sys.executable, me, "tex", "2k", "mossy_rock", "leafy_grass", "river_small_rocks",
                    "forest_ground_04"], check=True)
