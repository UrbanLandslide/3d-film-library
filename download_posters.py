#!/usr/bin/env python3
"""Download film artwork into posters/ on GitHub Actions; no API key required."""
import re, json, time, urllib.request, urllib.parse, pathlib, difflib
source=pathlib.Path('index.html').read_text(encoding='utf-8')
films=re.findall(r"^\['((?:\\'|[^'])+)','",source,re.M)
assert len(films)>=100, f'Only {len(films)} film titles found'
folder=pathlib.Path('posters');folder.mkdir(exist_ok=True)
exceptions={'Jurassic World 3D':'Jurassic World','Jurassic Park 3D':'Jurassic Park','IMAX: Under the Sea':'Under the Sea 3D','IMAX: Born to Be Wild':'Born to Be Wild 3D','IMAX: Dinosaurs Alive!':'Dinosaurs Alive!','The Wizard of Oz':'The Wizard of Oz 1939','The Lion King':'The Lion King 1994','Predator':'Predator 1987','The Mummy':'The Mummy 2017','The Three Musketeers':'The Three Musketeers 2011','Alice in Wonderland':'Alice in Wonderland 2010','The Avengers':'The Avengers 2012','A Christmas Carol':'A Christmas Carol 2009','Point Break':'Point Break 2015','Conan the Barbarian':'Conan the Barbarian 2011','Fast Lane':'Fast Lane 2011','Cousteau Collection':'The Silent World 1956'}
def norm(t):return re.sub(r'[^a-z0-9]','',t.lower().replace('3d',''))
def slug(t):return re.sub(r'^-|-$','',re.sub(r'[^a-z0-9]+','-',t.lower()))
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'3DFilmLibrary/1.0 (personal movie catalogue)'})
 with urllib.request.urlopen(req,timeout=22) as response:return response.read()
found=[];missing=[]
for title in films:
 target=folder/(slug(title)+'.jpg')
 if target.exists() and target.stat().st_size>1000:found.append(title);continue
 q=exceptions.get(title,title)
 try:
  endpoint='https://v3-cinemeta.strem.io/catalog/movie/top/search='+urllib.parse.quote(q)+'.json'
  matches=json.loads(get(endpoint)).get('metas',[])
  base=norm(re.sub(r'\s+\d{4}$','',q))
  choices=[m for m in matches if m.get('type')=='movie' and norm(m.get('name',''))==base]
  if not choices:
   print('UNMATCHED',title);missing.append(title);continue
  movie=choices[0]
  poster=movie.get('poster','')
  if not poster.startswith('https://'):missing.append(title);continue
  data=get(poster)
  if len(data)<1000 or data[:2]!=b'\xff\xd8':
   # Re-encode PNG/WEBP to JPEG when necessary (Pillow available in Actions)
   from PIL import Image
   from io import BytesIO
   img=Image.open(BytesIO(data)).convert('RGB');img.thumbnail((500,750));img.save(target,'JPEG',quality=83,optimize=True)
  else:target.write_bytes(data)
  found.append(title);print('OK',title)
 except Exception as e:print('FAILED',title,str(e)[:100]);missing.append(title)
 time.sleep(.15)
print('Downloaded:',len(found),'Missing:',len(missing))
pathlib.Path('poster-report.txt').write_text('Downloaded: '+str(len(found))+' / '+str(len(films))+'\nMissing:\n'+'\n'.join(missing)+'\n')
