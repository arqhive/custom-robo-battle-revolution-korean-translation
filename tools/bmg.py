# -*- coding: utf-8 -*-
"""BMG (MESGbmg1) reader/writer for Custom Robo Battle Revolution (GXCJ01).

Text form: Shift-JIS decoded; control code 0x1A <len> ... -> {1A:hex of whole code};
undecodable byte -> {XX}. Literal '{' is written as {7B}.
Round trip keeps section order, INF1 entries/attributes, DAT1 layout (gaps/tail raw).
"""
import struct, sys, json, re

def _sec_iter(b):
    n = struct.unpack('>I', b[12:16])[0]
    p = 0x20
    for _ in range(n):
        mg = b[p:p+4]; sz = struct.unpack('>I', b[p+4:p+8])[0]
        yield mg, b[p:p+sz]
        p += sz

def decode(raw):
    out = []; i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0x1A:
            ln = raw[i+1]
            out.append('{1A:%s}' % raw[i+2:i+ln].hex().upper()); i += ln; continue
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i+1 < len(raw):
            try:
                out.append(raw[i:i+2].decode('cp932')); i += 2; continue
            except UnicodeDecodeError:
                pass
        if 0x20 <= c < 0x7F and c != 0x7B or c == 0x0A or 0xA1 <= c <= 0xDF:
            out.append(bytes([c]).decode('cp932')); i += 1; continue
        out.append('{%02X}' % c); i += 1
    return ''.join(out)

_TAG = re.compile(r'\{1A:([0-9A-Fa-f]*)\}|\{([0-9A-Fa-f]{2})\}')
def encode(s):
    out = bytearray(); p = 0
    for m in _TAG.finditer(s):
        out += s[p:m.start()].encode('cp932')
        if m.group(1) is not None:
            body = bytes.fromhex(m.group(1)); out += bytes([0x1A, len(body)+2]) + body
        else:
            out.append(int(m.group(2), 16))
        p = m.end()
    out += s[p:].encode('cp932')
    return bytes(out)

def _scan_str(d, o):
    i = o
    while d[i] != 0:
        i += d[i+1] if d[i] == 0x1A else 1
    return i  # index of terminator

def read(b):
    assert b[:8] == b'MESGbmg1'
    bmg = {'header': b[8:0x20].hex(), 'sections': [],
           'size_unit': 32 if struct.unpack('>I', b[8:12])[0] * 32 == len(b) else 1}
    for mg, s in _sec_iter(b):
        if mg == b'INF1':
            cnt, esz = struct.unpack('>HH', s[8:12])
            ents = []
            for k in range(cnt):
                e = s[16+k*esz:16+(k+1)*esz]
                ents.append({'off': struct.unpack('>I', e[:4])[0], 'attr': e[4:].hex()})
            bmg['inf'] = {'unk': s[12:16].hex(), 'esz': esz, 'entries': ents,
                          'pad': s[16+cnt*esz:].hex()}
            bmg['sections'].append('INF1')
        elif mg == b'DAT1':
            d = s[8:]
            offs = sorted({e['off'] for e in bmg['inf']['entries']})
            strs = {}; chunks = []; p = 0
            for o in offs:
                if o < p:  # offset inside a previous string (shared tail)
                    continue
                if o > p: chunks.append(('raw', d[p:o].hex()))
                end = _scan_str(d, o)
                strs[o] = decode(d[o:end]); chunks.append(('str', o)); p = end + 1
            if p < len(d): chunks.append(('raw', d[p:].hex()))
            bmg['dat'] = {'chunks': chunks, 'strings': strs}
            bmg['sections'].append('DAT1')
        else:
            bmg['sections'].append({'raw': s.hex()})
    # per-entry text
    st = bmg['dat']['strings']
    for e in bmg['inf']['entries']:
        if e['off'] in st: e['text'] = st[e['off']]
    return bmg

def write(bmg):
    """Rebuild. Entry 'text' edits override the string at that entry's original offset."""
    st = dict(bmg['dat']['strings'])
    for e in bmg['inf']['entries']:
        if 'text' in e and e['off'] in st: st[e['off']] = e['text']
    dat = bytearray(); newoff = {}
    for kind, v in bmg['dat']['chunks']:
        if kind == 'raw': dat += bytes.fromhex(v)
        else:
            newoff[v] = len(dat); dat += encode(st[v]) + b'\0'
    # shared-tail offsets keep relative distance (only valid when unchanged)
    def mapoff(o):
        if o in newoff: return newoff[o]
        base = max(k for k in newoff if k <= o); return newoff[base] + (o - base)
    inf = bmg['inf']; body = bytearray()
    for e in inf['entries']:
        body += struct.pack('>I', mapoff(e['off'])) + bytes.fromhex(e['attr'])
    body += bytes.fromhex(inf['pad'])
    secs = []
    for s in bmg['sections']:
        if s == 'INF1':
            payload = struct.pack('>HH', len(inf['entries']), inf['esz']) + bytes.fromhex(inf['unk']) + body
            secs.append(b'INF1' + struct.pack('>I', 8+len(payload)) + payload)
        elif s == 'DAT1':
            while (len(dat) + 8) % 32: dat.append(0)
            secs.append(b'DAT1' + struct.pack('>I', 8+len(dat)) + bytes(dat))
        else:
            secs.append(bytes.fromhex(s['raw']))
    hdr = bytearray(b'MESGbmg1' + bytes.fromhex(bmg['header']))
    total = 0x20 + sum(map(len, secs))
    hdr[8:12] = struct.pack('>I', total // bmg.get('size_unit', 1)); hdr[12:16] = struct.pack('>I', len(secs))
    return bytes(hdr) + b''.join(secs)

if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read()
    print(json.dumps(read(b), ensure_ascii=False, indent=1))
