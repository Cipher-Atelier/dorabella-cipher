"""Own pure byte/sequence contract. Safe tests may import this, never the broker."""
import json
CAP=65536
class Channels:
    def __init__(self):
        self.buffers={'lm':b'','pat':b''};self.seq={'lm':0,'pat':0};self.closed={'lm':False,'pat':False}
    def feed(self,channel,data):
        if channel not in self.buffers or self.closed[channel]:raise ValueError('CHANNEL_CLOSED_OR_UNKNOWN')
        if type(data) is not bytes or not data:raise ValueError('EOF_OR_BYTES')
        raw=self.buffers[channel]+data
        if len(raw)>CAP:raise ValueError('FRAME_BOUND')
        if b'\n' not in raw:
            if len(raw)==CAP:raise ValueError('FRAME_BOUND')
            self.buffers[channel]=raw;return None
        if not raw.endswith(b'\n') or b'\n' in raw[:-1]:raise ValueError('PIPELINING_FORBIDDEN')
        self.buffers[channel]=b'';self.seq[channel]+=1
        if self.seq[channel]>(512 if channel=='lm' else 80000):raise ValueError('REQUEST_BOUND')
        return raw,self.seq[channel]
    def close(self,channel):
        if channel not in self.closed or self.closed[channel] or self.buffers[channel]:raise ValueError('CLOSE_STATE')
        self.closed[channel]=True
def pat_request(raw,seq):
    x=json.loads(raw)
    if type(x) is not list or len(x)!=3 or type(x[0]) is not int or x[0]!=seq:raise ValueError('REQUEST_ID')
    _,op,value=x
    if type(op) is not str or type(value) is not str:raise ValueError('REQUEST_SHAPE')
    if len(value)>87 or any(not(9<=ord(c)<=13 or 32<=ord(c)<=126) for c in value):raise ValueError('ARG_DOMAIN')
    if op in ('meta','close') and value=='':return op,b''
    if op=='word':return op,value.encode('ascii')
    if op=='list' and len(value)<=46:return op,value.encode('ascii')
    raise ValueError('OP_DOMAIN')
def encode_pat(seq,value):
    raw=(json.dumps([seq,*value],ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
    if len(raw)>CAP:raise ValueError('FRAME_BOUND')
    return raw
