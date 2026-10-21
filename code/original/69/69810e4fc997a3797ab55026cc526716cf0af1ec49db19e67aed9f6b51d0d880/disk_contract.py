"""Own exact byte lookup; no language arithmetic, model pruning or external modules."""
import os, re, struct, json
from collections import OrderedDict
TABS=re.compile(rb'\t+')
NUMBER=re.compile(rb'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
def parse(raw,order):
    if not raw or len(raw)>512:raise ValueError('ROW_BOUND')
    line=raw[:-1] if raw.endswith(b'\n') else raw
    fs=TABS.split(line)
    if len(fs)!=order+1:raise ValueError('FIELD_COUNT')
    key=tuple(fs[:-1]);value=fs[-1]
    if any(not 1<=len(k)<=128 or any(c<33 or c>126 for c in k) for k in key):raise ValueError('KEY_DOMAIN')
    if not 1<=len(value)<=96 or not NUMBER.fullmatch(value):raise ValueError('VALUE_DOMAIN')
    return key,value
def canonical(key,value):
    return b''.join(struct.pack('<H',len(v))+v for v in (*key,value))
class DiskLM:
    def __init__(self,entries,tick=lambda:None,capacity=4096):
        if not 1<=capacity<=4096:raise ValueError('CACHE_BOUND')
        self.files={};self.tick=tick;self.capacity=capacity;self.cache=OrderedDict()
        self.stats=dict(calls=0,hits=0,misses=0,evictions=0,preads=0,read_bytes=0,max_comparisons=0,cache_payload_peak=0)
        try:
            for e in entries:
                self.files[e['id']]=(open(e['path'],'rb'),open(e['index_path'],'rb'),e)
        except BaseException:self.close();raise
    def _row(self,table,j):
        data,index,e=self.files[table]
        pair=os.pread(index.fileno(),16,j*8);self.stats['preads']+=1;self.stats['read_bytes']+=len(pair)
        if len(pair)!=16:raise ValueError('OFFSET_TRUNCATED')
        a,b=struct.unpack('<QQ',pair)
        if not 0<=a<b<=e['bytes'] or b-a>512:raise ValueError('OFFSET_RANGE')
        raw=os.pread(data.fileno(),b-a,a);self.stats['preads']+=1;self.stats['read_bytes']+=len(raw)
        if len(raw)!=b-a:raise ValueError('SOURCE_TRUNCATED')
        return parse(raw,e['order'])
    def lookup(self,table,key):
        self.tick()
        if type(table) is not int or table not in self.files:raise ValueError('TABLE_ID')
        e=self.files[table][2]
        if type(key) is not tuple or len(key)!=e['order'] or any(type(k) is not bytes or len(k)>128 for k in key):raise ValueError('QUERY_DOMAIN')
        ck=(table,key);self.stats['calls']+=1
        if ck in self.cache:
            self.stats['hits']+=1;v=self.cache.pop(ck);self.cache[ck]=v
        else:
            self.stats['misses']+=1;lo=0;hi=e['rows'];count=0
            while lo<hi:
                mid=(lo+hi)//2;k,val=self._row(table,mid);count+=1
                if k<=key:lo=mid+1
                else:hi=mid
            v=(False,None,None)
            if lo:
                k,val=self._row(table,lo-1);count+=1
                if k==key:v=(True,val,lo)
            self.stats['max_comparisons']=max(count,self.stats['max_comparisons'])
            if len(self.cache)==self.capacity:self.cache.popitem(last=False);self.stats['evictions']+=1
            self.cache[ck]=v
            payload=sum(sum(map(len,k[1]))+(len(x[1]) if x[1] is not None else 0) for k,x in self.cache.items())
            self.stats['cache_payload_peak']=max(payload,self.stats['cache_payload_peak'])
        return {'found':v[0],'value_hex':v[1].hex() if v[1] is not None else None,'last_row_1based':v[2]}
    def close(self):
        for a,b,e in self.files.values():a.close();b.close()
        self.files={}
def frame(seq,values,final):
    if type(seq) is not int or not 0<=seq<100 or type(final) is not bool or len(values)>128:raise ValueError('FRAME_FIELDS')
    for r in values:
        if set(r)!={'found','value_hex','last_row_1based'} or type(r['found']) is not bool:raise ValueError('RECORD_FIELDS')
        if r['found']:
            if type(r['value_hex']) is not str or len(r['value_hex'])>192 or not re.fullmatch('[0-9a-f]+',r['value_hex']) or len(r['value_hex'])%2:raise ValueError('VALUE_HEX')
            if type(r['last_row_1based']) is not int or not 1<=r['last_row_1based']<=10000000:raise ValueError('ROW_ID')
        elif r['value_hex'] is not None or r['last_row_1based'] is not None:raise ValueError('MISSING_FIELDS')
    raw=(json.dumps({'v':1,'seq':seq,'count':len(values),'values':values,'final':final},separators=(',',':'))+'\n').encode('ascii')
    if len(raw)>65536:raise ValueError('FRAME_BOUND')
    return raw
def unframe(raw,seq):
    if len(raw)>65536 or not raw.endswith(b'\n') or b'\n' in raw[:-1]:raise ValueError('FRAME_BYTES')
    x=json.loads(raw)
    if set(x)!={'v','seq','count','values','final'} or x['v']!=1 or x['seq']!=seq or type(x['count']) is not int or x['count']!=len(x['values']):raise ValueError('FRAME_HEADER')
    if frame(x['seq'],x['values'],x['final'])!=raw:raise ValueError('FRAME_CANONICAL')
    return x['values'],x['final']
