"""Known-control preparation only. NO unknown-key or target plaintext search.

Run once before the CH2-v1 search freeze. All eight source selectors are fixed.
Lexical DP consumes known plaintext, never guesses a key or changes input.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import datetime

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
OUT = ROOT / "preflight_output"
DICT = WORK / "Dorabella_R6_section7_implementation_review_20261016/original/dictionary/en-spelling.txt"
SOURCES = {"pg40307.txt":"478b46dec828bb85ebc0b45288d325d90af888e0dd6d067dcaf0c0d061c99aa4", "pg35698.txt":"aa989e769576c4f1f136a72e711da0a4b3be0edb0236ca99b3f8b605328586b5"}
DSHA = "eade91558167fe09a481abf59e176af8643ad78678cc53dd5aeaf2a8b30fa332"

def sha(b): return hashlib.sha256(b).hexdigest()
def save(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def norm(s):
    s=s.translate(str.maketrans({"Æ":"AE","æ":"ae","Œ":"OE","œ":"oe"}))
    return re.sub("[^A-Za-z]","",s).upper()

def known_eligibility(p,words,prefixes):
    # Forward DAG of known-string boundaries, longest token 24, no key variables.
    paths={0:[]}
    for i in range(87):
        if i not in paths: continue
        for j in range(i+1,min(87,i+24)+1):
            token=p[i:j]
            if j==87 and token in prefixes:
                witness=paths[i]+[{"start1":i+1,"end1":j,"token":token,"kind":"word" if token in words else "final_prefix"}]
                return {"eligible":True,"witness":witness}
            if token in words and j<87 and j not in paths:
                paths[j]=paths[i]+[{"start1":i+1,"end1":j,"token":token,"kind":"word"}]
    return {"eligible":False,"reachable_boundaries0":sorted(paths),"reason":"No complete permitted known-plaintext segmentation"}

def control_key(p,b):
    e=[5,15] if b in ("B1","B3") else [5]
    t=[22,8] if b in ("B2","B3") else [22]
    reserved=set(e+t)
    free=[g for g in range(24) if g not in reserved]
    other=sorted(set(p)-set("ET"))
    if len(other)>len(free): return None
    key={"E":e,"T":t}
    key.update({letter:[g] for letter,g in zip(other,free)})
    return key

def encode_known(p,key):
    counts={k:0 for k in key};g=[];obs=[]
    for i,letter in enumerate(p):
        cyc=key[letter];visit=counts[letter];glyph=cyc[visit%len(cyc)]
        counts[letter]+=1;g.append(glyph)
        obs.append({"position1":i+1,"letter":letter,"visit0":visit,"cycle":cyc,"glyph":glyph})
    return g,obs

def verify_known(g,p,key):
    # Independent occurrence-index oracle: index is count in prefix g[:i],
    # not the forward encoder's mutable counters.
    inverse={}
    for letter,cycle in key.items():
        for x in cycle:
            if x in inverse: raise ValueError("overlapping cycles")
            inverse[x]=letter
    recovered="".join(inverse[x] for x in g)
    checks=[]
    for i,x in enumerate(g):
        letter=inverse[x];cycle=key[letter]
        occurrence=sum(1 for z in g[:i] if z in cycle)
        checks.append({"position1":i+1,"letter":letter,"input_glyph":x,"reencoded_glyph":cycle[occurrence%len(cycle)],"match":cycle[occurrence%len(cycle)]==x and letter==p[i]})
    if len(g)!=87 or recovered!=p or not all(x["match"] for x in checks): raise ValueError("inverse mismatch")
    return {"recovered_plaintext87":recovered,"positions":checks,"matched":87}

def main():
    if OUT.exists(): raise RuntimeError("preflight output already exists: no replacement")
    OUT.mkdir()
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    book={}
    for name,h in SOURCES.items():
        b=(ROOT/"source_books"/name).read_bytes()
        if sha(b)!=h: raise ValueError("source hash "+name)
        book[name]=b.decode("utf-8-sig").replace("\r\n","\n")
    db=DICT.read_bytes()
    if sha(db)!=DSHA: raise ValueError("dictionary hash")
    words=set()
    for line in db.decode("utf-8").splitlines():
        fields=line.split()
        if fields and re.fullmatch("[a-z]{1,24}",fields[0]) and (len(fields[0])>1 or fields[0] in ("a","i")):
            words.add(fields[0].upper())
    prefixes={w[:i] for w in words for i in range(1,len(w)+1)}
    selection=json.loads((ROOT/"control_selection.json").read_text())
    truths=[];decoder=[];rows=[]
    for n,c in enumerate(selection["cases"],1):
        s=book[c["book"]]
        if s.count(c["start"])!=1: raise ValueError("nonunique start "+c["id"])
        a=s.index(c["start"]);z=s.index(c["end"],a)+len(c["end"])
        raw=s[a:z];body=raw[len(c["remove_salutation"]):]
        if not raw.startswith(c["remove_salutation"]): raise ValueError("salutation")
        for excluded in c["exclusions"]:
            if body.count(excluded)!=1: raise ValueError("exclusion "+excluded)
            body=body.replace(excluded,"")
        p=norm(body)[:87]
        if len(p)!=87: raise ValueError("SOURCE_INCOMPLETE "+c["id"])
        key=control_key(p,c["assigned_branch"])
        weak=[letter for letter in "ET" if ((letter=="E" and c["assigned_branch"] in ("B1","B3")) or (letter=="T" and c["assigned_branch"] in ("B2","B3"))) and p.count(letter)<3]
        lex=known_eligibility(p,words,prefixes)
        row={"id":c["id"],"decoder_id":f"P{n:02}","assigned_branch":c["assigned_branch"],"plaintext87":p,"plaintext_sha256":sha(p.encode("ascii")),"distinct_letters":len(set(p)),"alphabet":"".join(sorted(set(p))),"E":p.count("E"),"T":p.count("T"),"representable":key is not None,"weak_cycles":weak,"lexical":lex}
        truth={**row,"source":{**c,"source_sha256":SOURCES[c["book"]],"line_start1":s[:a].count("\n")+1,"line_end1":s[:z].count("\n")+1,"raw_excerpt":raw,"body_after_exclusions":body,"raw_excerpt_sha256":sha(raw.encode()),"body_sha256":sha(body.encode())},"key":key}
        if key is not None:
            g,obs=encode_known(p,key);iv=verify_known(g,p,key)
            q="".join(p[(2*i)%87] for i in range(87))
            ng,nobs=encode_known(q,key);niv=verify_known(ng,q,key)
            truth.update({"glyph87":g,"encoding_positions":obs,"inverse":iv,"negative":{"plaintext87":q,"glyph87":ng,"encoding_positions":nobs,"inverse":niv,"permutation":"q[i]=p[(2*i)%87]"}})
            decoder.append({"id":f"P{n:02}","glyph":g})
        else: decoder.append({"id":f"P{n:02}","glyph":None,"status":"DOMAIN_FAIL"})
        truths.append(truth);rows.append(row)
    for n,t in enumerate(truths,1):
        decoder.append({"id":f"N{n:02}","glyph":t.get("negative",{}).get("glyph87"),"status":"PREPARED" if "negative" in t else "DOMAIN_FAIL"})
    eligible=[r for r in rows if r["representable"] and not r["weak_cycles"] and r["lexical"]["eligible"]]
    strata={b:sum(r["assigned_branch"]==b for r in eligible) for b in ("B0","B1","B2","B3")}
    possible=len(eligible)>=6 and all(strata.values())
    report={"stage":"KNOWN_CONTROL_PREFLIGHT_ONLY","started_utc":started,"ended_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"solver_executed":False,"selection_sha256":sha((ROOT/"control_selection.json").read_bytes()),"dictionary_sha256":DSHA,"max_eligible_successes":len(eligible),"eligible_by_assigned_branch":strata,"gate_6of8_necessary_conditions":possible,"case_summary":rows}
    save(OUT/"private_control_truth.json",truths);save(OUT/"decoder_controls.json",decoder);save(OUT/"preflight_report.json",report)
    print(json.dumps({k:v for k,v in report.items() if k!="case_summary"},indent=2))
    for r in rows: print(r["id"],r["plaintext87"],"K",r["distinct_letters"],"E/T",r["E"],r["T"],"repr",r["representable"],"weak",r["weak_cycles"],"lex",r["lexical"]["eligible"])

if __name__=="__main__": main()
