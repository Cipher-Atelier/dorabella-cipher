from pathlib import Path
import json,datetime
R=Path(__file__).resolve().parents[1]
events=[]
for line in (R/'logs/events.jsonl').read_text().splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
done={x['case'] for x in events if x.get('event')=='complete'}
active=[x['case'] for x in events if x.get('event')=='begin' and x['case'] not in done]
print(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'done':len(done),
 'active':{n:{s:len(list((R/'runs'/n/s/n).glob('*.json'))) for s in ['first','middle','final']} for n in active}}))
