"""/message/font.out (JSystem BFN 4개 묶음) 읽기·고치기.

묶음 머리: u32 개수(4), u32 머리 크기(0x20), (u32 오프셋, u32 크기) × 4.
BFN: 'FONTbfn1', u32 크기, u32 블록 수, 0x20부터 블록(INF1·WID1·MAP1 여러 개·GLY1).
- WID1: u16 시작, u16 끝, 글자마다 (왼쪽 여백 u8, 폭 u8)
- MAP1: u16 type, u16 시작 코드, u16 끝 코드, u16 개수, 뒤에 u16
    type 2 = 코드마다 글자 번호 표(시작~끝), type 3 = (코드, 글자 번호) 쌍
- GLY1: u16 시작, u16 끝, u16 칸 폭, u16 칸 높이, u32 시트 크기, u16 형식(0=I4),
        u16 열, u16 행, u16 시트 폭, u16 시트 높이, 0x20부터 시트
글자 번호 k → 시트 k // (열*행), 칸 (k % 열, k // 열 % 행).

글자를 고쳐도 크기·배치는 그대로라 bytes 를 제자리에서 바꾼다.
"""
import struct
from PIL import Image


class BFN:
    def __init__(self, buf, base, size):
        self.buf, self.base, self.size = buf, base, size
        nb = struct.unpack_from('>I', buf, base + 12)[0]
        p = base + 0x20; self.maps = []
        for _ in range(nb):
            tag = bytes(buf[p:p + 4]); sz = struct.unpack_from('>I', buf, p + 4)[0]
            if tag == b'WID1':
                self.wid = p
                self.wid_start = struct.unpack_from('>H', buf, p + 8)[0]
            elif tag == b'MAP1':
                t, s, e, n = struct.unpack_from('>4H', buf, p + 8)
                ent = struct.unpack_from('>%dH' % n, buf, p + 16)
                self.maps.append((t, s, e, ent))
            elif tag == b'GLY1':
                (self.g_start, self.g_end, self.cw, self.ch, self.sheet_size, self.fmt,
                 self.cols, self.rows, self.sw, self.sh) = struct.unpack_from('>4HI5H', buf, p + 8)
                self.sheets = p + 0x20
            p += sz
        assert self.fmt == 0, 'I4 만 다룸'

    def cmap(self):
        m = {}
        for t, s, e, ent in self.maps:
            if t == 2:
                for k, g in enumerate(ent):
                    if g != 0xFFFF: m[s + k] = g
            elif t == 3:
                for k in range(0, len(ent) - 1, 2): m[ent[k]] = ent[k + 1]
            else:
                raise ValueError('MAP1 type %d' % t)
        return m

    def _cell(self, g):
        sheet, k = divmod(g - self.g_start, self.cols * self.rows)
        return self.sheets + sheet * self.sheet_size, (k % self.cols) * self.cw, (k // self.cols) * self.ch

    def _addr(self, so, x, y):
        tx, px = divmod(x, 8); ty, py = divmod(y, 8)
        return so + (ty * (self.sw // 8) + tx) * 32 + py * 4 + px // 2, px & 1

    def get(self, g):
        so, x0, y0 = self._cell(g)
        im = Image.new('L', (self.cw, self.ch)); px = im.load()
        for y in range(self.ch):
            for x in range(self.cw):
                a, odd = self._addr(so, x0 + x, y0 + y)
                v = self.buf[a] & 0xF if odd else self.buf[a] >> 4
                px[x, y] = v * 17
        return im

    def put(self, g, im):
        so, x0, y0 = self._cell(g); px = im.load()
        for y in range(self.ch):
            for x in range(self.cw):
                a, odd = self._addr(so, x0 + x, y0 + y); v = px[x, y] >> 4
                self.buf[a] = (self.buf[a] & 0xF0 | v) if odd else (self.buf[a] & 0x0F | v << 4)

    def width(self, g):
        o = self.wid + 12 + 2 * (g - self.wid_start)
        return self.buf[o], self.buf[o + 1]

    def set_width(self, g, left, w):
        o = self.wid + 12 + 2 * (g - self.wid_start)
        self.buf[o], self.buf[o + 1] = left, w


def load(data):
    buf = bytearray(data)
    n, hsz = struct.unpack_from('>II', buf, 0)
    fonts = [BFN(buf, *struct.unpack_from('>II', buf, 8 + 8 * i)) for i in range(n)]
    return buf, fonts
