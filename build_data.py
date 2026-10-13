import re,csv,json
from pathlib import Path
src=Path('/mnt/data/files/Pasted markdown(2).md').read_text(encoding='utf-8')
rows=[]
for line in src.splitlines():
    if not line.startswith('|') or '---' in line or 'Company Name' in line: continue
    cells=[c.strip() for c in line.strip().strip('|').split('|')]
    if len(cells)<11: continue
    m=re.match(r'\[([\s\S]*?)\]\((https?://[^)]+)\)',cells[0])
    name=re.sub(r'\s+',' ',m.group(1)).strip() if m else re.sub(r'\s+',' ',cells[0]).strip()
    url=m.group(2) if m else ''
    def num(s):
        s=s.replace('₹','').replace(',','').strip()
        try:return float(re.sub(r'[^0-9.\-]','',s))
        except:return None
    rows.append({'companyName':name,'sourceUrl':url,'currentPrice':num(cells[1]),'listingDate':cells[2].replace('`','').strip(),'issuePrice':num(cells[3]),'qib':cells[4],'hni':cells[5],'retail':cells[6],'total':cells[7],'listingGain':cells[8],'currentGain':cells[9],'stockType':cells[10].strip()})
Path('/mnt/data/ipo-dashboard/data/ipos.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('rows',len(rows))
