"""Минимальное чтение/запись PNG (8 бит, RGB/RGBA/Gray) на стандартной библиотеке."""
import struct
import zlib


def read_png(path):
    data = open(path, 'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    o, idat, w = 8, [], None
    while o < len(data):
        ln, typ = struct.unpack('>I4s', data[o:o + 8])
        body = data[o + 8:o + 8 + ln]
        if typ == b'IHDR':
            w, h, depth, ctype, _, _, inter = struct.unpack('>IIBBBBB', body)
            assert depth == 8 and inter == 0
        elif typ == b'IDAT':
            idat.append(body)
        o += 12 + ln
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b''.join(idat))
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p + 1:p + 1 + stride]); p += 1 + stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]; c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, out


def write_png(path, w, h, ch, pix):
    ctype = {1: 0, 3: 2, 4: 6}[ch]
    stride = w * ch
    raw = b''.join(b'\x00' + bytes(pix[y * stride:(y + 1) * stride]) for y in range(h))
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as fh:
        fh.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0))
                 + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def downscale2(w, h, ch, pix):
    """Уменьшение в 2 раза усреднением 2×2."""
    W, Hh = w // 2, h // 2
    out = bytearray(W * Hh * ch)
    s = w * ch
    for y in range(Hh):
        r0 = 2 * y * s; r1 = r0 + s
        for x in range(W):
            i = 2 * x * ch
            for c in range(ch):
                out[(y * W + x) * ch + c] = (pix[r0 + i + c] + pix[r0 + i + ch + c] + pix[r1 + i + c] + pix[r1 + i + ch + c] + 2) >> 2
    return W, Hh, out
