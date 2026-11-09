import json,sys,pathlib
sys.path.insert(0,'scripts')
from update_prices_official import fetch_day
from rules import normalized_name
from datetime import date
rows=fetch_day(date(2026,11,6))
names=["SpectraA Technology Solutions","Maharaja Speedex","Anawil Wire Engineering","Goldline Pharmaceutical","Defrail Technologies","E to E Transportation","HyTech Engineers","IndoMIM","HRS Aluglaze","Sheel Biotech","Sat Kartar Shopping","Anya Polytech Fertilizers","Standard Glass Lining","Identical Brains Studios","Dhanlaxmi Crop Science","Shiv Texchem","Divyadhan Recycling Industries","Sahasra Electronic Solutions","Techera Engineering India","Thinking Hats Entertainment Solutions","Paramount Speciality Forgings","Osel Devcies","Shubhshree Biofuels Energy","Mach Conferences and Events","Aesthetik Engineers","Bulkcorp Intl","Sathlokhar Synergys","Manglam Infra","Chetana Education","Ambey Laboratories"]
out={}
for n in names:
    w=normalized_name(n).split()[0]
    out[n]=[(r[0],r[1],r[2],r[3],r[4]) for r in rows if w in normalized_name(r[2]).split()][:6]
pathlib.Path('reports').mkdir(exist_ok=True)
pathlib.Path('reports/probe.json').write_text(json.dumps(out,indent=1))
