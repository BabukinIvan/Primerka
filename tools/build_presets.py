"""PRIMERKA (model-viewer): сборка заготовок из CC0-ассетов MakeHuman.

Результат в models/:
  body_<тип>.glb    — фигура + футболка и джинсы во всех размерах (S–XL), каждая вещь-размер отдельным материалом
  textures/*.png    — ткань: денимная фактура (для перекраски) и футболка с принтом
  presets.json      — замеры фигур, таблица размеров, рассчитанный запас посадки
  bundle.js         — всё то же одним файлом (data-URI), чтобы index.html открывался двойным кликом

Запуск: python3 tools/build_presets.py   (только стандартная библиотека Python)
"""
import base64
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mhlib import (load_obj, load_target, apply_target, load_mhclo, fit_proxy, tri_faces,  # noqa: E402
                   vertex_normals, girth)
import pngio  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'source', 'makehuman')
OUT = os.path.join(ROOT, 'models')
SUIT = 'male_casualsuit04'          # футболка + джинсы, CC0

# Три заготовки фигуры: веса морфов MakeHuman (macrodetails), рост 173 см у всех.
BODIES = {
    'slim':  {'name': 'Худощавая', 'mods': [('averagemuscle-minweight', 0.6), ('minmuscle-minweight', 0.15)]},
    'avg':   {'name': 'Средняя',   'mods': [('averagemuscle-maxweight', 0.4), ('maxmuscle-maxweight', 0.2)]},
    'heavy': {'name': 'Плотная',   'mods': [('averagemuscle-maxweight', 0.6), ('minmuscle-maxweight', 0.3)]},
}
# Таблица размеров изделий (обхваты готовой вещи, см)
SIZES = ['S', 'M', 'L', 'XL']
GARMENTS = {
    'tee':   {'name': 'Футболка', 'sizes': {'S': {'chest': 96}, 'M': {'chest': 104}, 'L': {'chest': 112}, 'XL': {'chest': 120}}},
    'jeans': {'name': 'Джинсы', 'sizes': {'S': {'waist': 76, 'hips': 94}, 'M': {'waist': 84, 'hips': 102},
                                          'L': {'waist': 92, 'hips': 110}, 'XL': {'waist': 100, 'hips': 118}}},
}
CM = 0.1                 # единица MakeHuman — дециметр
BASE_GAP = 0.35 * CM     # минимальный зазор ткань–кожа, чтобы не мерцало
TIGHT_LIMIT = -0.2 * CM  # тесная вещь облегает тело, но не уходит под кожу
LOOSE_LIMIT = 9.0 * CM


def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def main():
    V0, _, F = load_obj(os.path.join(SRC, 'base.obj'))
    body_tris = tri_faces(F, {'body'})
    T = {n[:-7]: load_target(os.path.join(SRC, 'targets', n)) for n in os.listdir(os.path.join(SRC, 'targets'))}
    suit_dir = os.path.join(SRC, 'clothes', SUIT)
    cV, cVT, cF = load_obj(os.path.join(suit_dir, SUIT + '.obj'))
    refs, scales, _ = load_mhclo(os.path.join(suit_dir, SUIT + '.mhclo'))
    eV, _, eF = load_obj(os.path.join(SRC, 'eyes', 'low-poly.obj'))
    erefs, escales, _ = load_mhclo(os.path.join(SRC, 'eyes', 'low-poly.mhclo'))

    def make_body(mods):
        V = [v[:] for v in V0]
        for e in ('african', 'asian', 'caucasian'):
            apply_target(V, T[e + '-male-young'], 1 / 3)
        for n, k in mods:
            apply_target(V, T['universal-male-young-' + n], k)
        return V

    # Разметка по средней фигуре: вершины рук (чтобы обхват груди не захватывал руки)
    A = make_body([])
    bverts = sorted({i for t, _ in body_tris for i in t})
    ys = [A[i][1] for i in bverts]
    Y0, H = min(ys), max(ys) - min(ys)
    arm = {i for i, v in enumerate(A) if abs(v[0]) > 1.9 and v[1] > Y0 + 0.5 * H}
    torso_tris = [t for t in body_tris if not any(i in arm for i in t[0])]
    lv = {'hipsLo': 0.47, 'hipsHi': 0.54, 'waistLo': 0.58, 'waistHi': 0.66, 'chestLo': 0.68, 'chestHi': 0.73}

    # Деление комплекта на футболку и джинсы по связности (2 отдельных куска)
    par = list(range(len(cV)))
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for _, vs, _ in cF:
        for v in vs[1:]:
            par[find(v)] = find(vs[0])
    comps = {}
    for i in range(len(cV)):
        comps.setdefault(find(i), []).append(i)
    parts = sorted(comps.values(), key=lambda idx: sum(cV[i][1] for i in idx) / len(idx))
    part_of = {}
    for i in parts[0]:
        part_of[i] = 'jeans'
    for i in parts[1]:
        part_of[i] = 'tee'
    sleeve = [refs[i][0][0] in arm for i in range(len(cV))]

    os.makedirs(os.path.join(OUT, 'textures'), exist_ok=True)
    presets = {'version': 1, 'source': 'MakeHuman system assets (CC0): base.obj hm08, macrodetails targets, ' + SUIT,
               'sizes': SIZES, 'garments': GARMENTS, 'bodies': {}}

    for key, cfg in BODIES.items():
        V = make_body(cfg['mods'])
        y0 = min(V[i][1] for i in bverts)
        Hb = max(V[i][1] for i in bverts) - y0
        def lvl(f):
            return y0 + f * Hb
        def scan(tris, lo, hi, pick):
            ys_ = [lvl(lo + (hi - lo) * k / 10) for k in range(11)]
            return pick(((girth(V, tris, y, 0.0, 0.5), y) for y in ys_), key=lambda p: p[0])
        chest, y_chest = scan(torso_tris, lv['chestLo'], lv['chestHi'], max)
        waist, y_waist = scan(torso_tris, lv['waistLo'], lv['waistHi'], min)
        hips, y_hips = scan(torso_tris, lv['hipsLo'], lv['hipsHi'], max)
        meas = {'height': round(Hb * 10, 1), 'chest': round(chest * 10, 1), 'waist': round(waist * 10, 1), 'hips': round(hips * 10, 1)}

        G = fit_proxy(V, refs, scales)
        g_tris = tri_faces(cF)
        GN = vertex_normals(G, g_tris)
        # обхваты вещи «как посажена MakeHuman» на тех же уровнях
        tee_tris = [t for t in g_tris if part_of[t[0][0]] == 'tee' and not sleeve[t[0][0]]]
        jeans_tris = [t for t in g_tris if part_of[t[0][0]] == 'jeans']
        jeans_top = max(G[i][1] for i in parts[0])
        y_band = jeans_top - 0.3                       # пояс джинсов сидит ниже природной талии
        band_body = girth(V, torso_tris, y_band, 0.0, 1.0)
        fit = {'tee': {'chest': girth(G, tee_tris, y_chest, 0.0, 0.5)},
               'jeans': {'waist': girth(G, jeans_tris, y_band, 0.0, 1.0),
                         'hips': girth(G, jeans_tris, y_hips, 0.0, 0.5)}}
        # Запас вещи переносим на уровень пояса: обхват пояса = тело на поясе + (обхват размера − талия покупателя)
        waist_shift = band_body - waist
        y_crotch = lvl(0.47)
        y_neck = lvl(0.86)

        def offset(g, size, i):
            """Сдвиг вершины вещи по нормали для размера: (обхват размера − обхват посадки) / 2π."""
            y = G[i][1]
            if g == 'tee':
                d = (GARMENTS['tee']['sizes'][size]['chest'] / 10 - fit['tee']['chest']) / (2 * math.pi)
                d = max(TIGHT_LIMIT, min(LOOSE_LIMIT, d))
                k = 0.5 if sleeve[i] else lerp(1.0, 0.25, (y - y_chest) / (y_neck - y_chest))
                return d * k
            s = GARMENTS['jeans']['sizes'][size]
            dw = (s['waist'] / 10 + waist_shift - fit['jeans']['waist']) / (2 * math.pi)
            dh = (s['hips'] / 10 - fit['jeans']['hips']) / (2 * math.pi)
            dw, dh = (max(TIGHT_LIMIT, min(LOOSE_LIMIT, x)) for x in (dw, dh))
            if y >= y_hips:
                return lerp(dh, dw, (y - y_hips) / (jeans_top - y_hips))
            if y >= y_crotch:
                return dh
            return lerp(dh * 0.35, dh * 0.8, (y - lvl(0.05)) / (y_crotch - lvl(0.05)))   # штанина: свободнее к бедру

        # Футболка поверх джинсов. Футболку не трогаем (иначе низ расширяется под самые широкие джинсы),
        # а джинсы под футболкой прижимаем: выше подола они не выходят за самый узкий размер футболки.
        # Ниже груди отступ футболки одинаков по высоте, поэтому хватает одного числа.
        tee_min = BASE_GAP + min(max(TIGHT_LIMIT, min(LOOSE_LIMIT, (GARMENTS['tee']['sizes'][s]['chest'] / 10 - fit['tee']['chest'])
                                                      / (2 * math.pi))) for s in SIZES) - 0.25 * CM
        tee_low = min(G[i][1] for i in parts[1] if not sleeve[i])
        y_hem = max(G[i][1] for i in parts[1] if not sleeve[i] and G[i][1] < tee_low + 0.2)   # верх кромки подола

        variants = {}
        for g in ('jeans', 'tee'):
            for size in SIZES:
                P = []
                for i in range(len(cV)):
                    if part_of[i] != g:
                        P.append(None); continue
                    d = BASE_GAP + offset(g, size, i)
                    if g == 'jeans' and d > tee_min:
                        d = lerp(d, tee_min, (G[i][1] - (y_hem - 0.1)) / 0.2)   # плавно от подола вверх
                    P.append([G[i][k] + GN[i][k] * d for k in range(3)])
                variants[(g, size)] = P

        ease = {g: {s: {} for s in SIZES} for g in GARMENTS}
        for size in SIZES:
            ease['tee'][size]['chest'] = round(GARMENTS['tee']['sizes'][size]['chest'] - meas['chest'], 1)
            for z in ('waist', 'hips'):
                ease['jeans'][size][z] = round(GARMENTS['jeans']['sizes'][size][z] - meas[z], 1)

        E = fit_proxy(V, erefs, escales)
        write_glb(os.path.join(OUT, 'body_%s.glb' % key), V, body_tris, bverts, y0, G, cF, cVT, part_of, variants, E, eF)
        presets['bodies'][key] = {'name': cfg['name'], 'file': 'body_%s.glb' % key, 'measurements': meas,
                                  'garmentFit': {g: {k: round(v * 10, 1) for k, v in d.items()} for g, d in fit.items()},
                                  'ease': ease, 'morphs': cfg['mods']}
        print('%-6s рост %.0f  грудь %.1f  талия %.1f  бёдра %.1f   | посадка MH: футболка %.1f, джинсы талия %.1f бёдра %.1f'
              % (key, meas['height'], meas['chest'], meas['waist'], meas['hips'],
                 fit['tee']['chest'] * 10, fit['jeans']['waist'] * 10, fit['jeans']['hips'] * 10))

    make_textures(suit_dir)
    with open(os.path.join(OUT, 'presets.json'), 'w', encoding='utf8') as fh:
        json.dump(presets, fh, ensure_ascii=False, indent=1)
    write_bundle(presets)


# ---------------- текстуры ----------------

def make_textures(suit_dir):
    w, h, ch, pix = pngio.read_png(os.path.join(suit_dir, SUIT + '_diffuse.png'))
    w, h, pix = pngio.downscale2(w, h, ch, pix)
    pngio.write_png(os.path.join(OUT, 'textures', 'print.png'), w, h, ch, pix)   # оригинал: футболка с принтом + джинсы
    # фактура денима в оттенках серого, нормированная к ~1.0 по яркости — цвет задаёт материал
    lum = bytearray(w * h)
    for i in range(w * h):
        p = pix[i * ch:i * ch + 3]
        lum[i] = (p[0] * 54 + p[1] * 183 + p[2] * 19) >> 8
    # средняя яркость джинсовой части атласа (низ: v < 0.58 → строки сверху в PNG от 0.42h)
    rows = range(int(0.45 * h), h)
    vals = [lum[y * w + x] for y in rows for x in range(0, int(0.8 * w), 7)]
    vals = [v for v in vals if v > 8]
    mean = sum(vals) / len(vals)
    gain = 205 / mean
    gray = bytearray(min(255, int(v * gain)) for v in lum)
    pngio.write_png(os.path.join(OUT, 'textures', 'fabric.png'), w, h, 1, gray)


# ---------------- GLB ----------------

class GLB:
    def __init__(self):
        self.bin = bytearray()
        self.g = {'asset': {'version': '2.0', 'generator': 'PRIMERKA tools/build_presets.py',
                            'copyright': 'Fig. & clothes: MakeHuman assets, CC0'},
                  'scene': 0, 'scenes': [{'nodes': []}], 'nodes': [], 'meshes': [], 'materials': [],
                  'accessors': [], 'bufferViews': [], 'buffers': [], 'textures': [], 'images': [], 'samplers': []}

    def view(self, data, target):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.g['bufferViews'].append({'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data), 'target': target})
        self.bin += data
        return len(self.g['bufferViews']) - 1

    def acc(self, vals, comps, ctype=5126, target=34962, minmax=False):
        flat = [x for v in vals for x in v] if comps > 1 else list(vals)
        fmt = {5126: 'f', 5123: 'H', 5125: 'I'}[ctype]
        bv = self.view(struct.pack('<%d%s' % (len(flat), fmt), *flat), target)
        a = {'bufferView': bv, 'componentType': ctype, 'count': len(vals),
             'type': {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3'}[comps]}
        if minmax:
            a['min'] = [min(v[k] for v in vals) for k in range(comps)]
            a['max'] = [max(v[k] for v in vals) for k in range(comps)]
        self.g['accessors'].append(a)
        return len(self.g['accessors']) - 1

    def material(self, name, color, rough=0.8, mask=False, tex=None):
        m = {'name': name, 'pbrMetallicRoughness': {'baseColorFactor': color, 'metallicFactor': 0.0, 'roughnessFactor': rough}}
        if mask:
            m.update(alphaMode='MASK', alphaCutoff=0.5, doubleSided=True)
        if tex is not None:
            m['pbrMetallicRoughness']['baseColorTexture'] = {'index': tex}
        self.g['materials'].append(m)
        return len(self.g['materials']) - 1

    def texture_png(self, data):
        bv = self.view(data, None)
        del self.g['bufferViews'][bv]['target']
        self.g['images'].append({'bufferView': bv, 'mimeType': 'image/png'})
        if not self.g['samplers']:
            self.g['samplers'].append({'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497})
        self.g['textures'].append({'sampler': 0, 'source': len(self.g['images']) - 1})
        return len(self.g['textures']) - 1

    def mesh(self, name, P, N, idx, mat, uv=None):
        attrs = {'POSITION': self.acc(P, 3, minmax=True), 'NORMAL': self.acc(N, 3)}
        if uv is not None:
            attrs['TEXCOORD_0'] = self.acc(uv, 2)
        ct = 5123 if len(P) < 65536 else 5125
        prim = {'attributes': attrs, 'indices': self.acc(idx, 1, ct, 34963), 'material': mat}
        self.g['meshes'].append({'name': name, 'primitives': [prim]})
        self.g['nodes'].append({'name': name, 'mesh': len(self.g['meshes']) - 1})
        self.g['scenes'][0]['nodes'].append(len(self.g['nodes']) - 1)

    def save(self, path):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.g['buffers'] = [{'byteLength': len(self.bin)}]
        for k in ('textures', 'images', 'samplers'):
            if not self.g[k]:
                del self.g[k]
        js = json.dumps(self.g, separators=(',', ':')).encode()
        js += b' ' * ((4 - len(js) % 4) % 4)
        with open(path, 'wb') as fh:
            fh.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(self.bin)))
            fh.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
            fh.write(struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin))


def to_m(v, y0):
    return (round(v[0] * 0.1, 5), round((v[1] - y0) * 0.1, 5), round(v[2] * 0.1, 5))


def white_png():
    import zlib
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    raw = b''.join(b'\x00' + b'\xff\xff\xff' * 4 for _ in range(4))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def write_glb(path, V, body_tris, bverts, y0, G, cF, cVT, part_of, variants, E, eF):
    glb = GLB()
    # тело
    remap = {v: k for k, v in enumerate(bverts)}
    N = vertex_normals(V, body_tris)
    glb.mesh('body', [to_m(V[i], y0) for i in bverts], [tuple(round(x, 4) for x in N[i]) for i in bverts],
             [remap[i] for t, _ in body_tris for i in t], glb.material('skin', [0.72, 0.47, 0.34, 1.0], 0.6))
    # глаза
    e_tris = tri_faces(eF)
    EN = vertex_normals(E, e_tris)
    glb.mesh('eyes', [to_m(v, y0) for v in E], [tuple(round(x, 4) for x in n) for n in EN],
             [i for t, _ in e_tris for i in t], glb.material('eyes', [0.12, 0.09, 0.08, 1.0], 0.3))
    # вещи: вершины разделяются по парам (вершина, UV)
    tex = glb.texture_png(white_png())
    g_tris = tri_faces(cF)
    for g in ('tee', 'jeans'):
        tris = [t for t in g_tris if part_of[t[0][0]] == g]
        for size in SIZES:
            P = variants[(g, size)]
            PN = vertex_normals([p if p is not None else [0, 0, 0] for p in P], tris)
            key, pos, nor, uv, idx = {}, [], [], [], []
            for vs, ts in tris:
                for v, t in zip(vs, ts):
                    k = (v, t)
                    if k not in key:
                        key[k] = len(pos)
                        pos.append(to_m(P[v], y0)); nor.append(tuple(round(x, 4) for x in PN[v]))
                        u, w = cVT[t]; uv.append((round(u, 5), round(1 - w, 5)))
                    idx.append(key[k])
            visible = size == 'M'
            color = [0.95, 0.95, 0.95, 1.0 if visible else 0.0] if g == 'tee' else [0.25, 0.36, 0.55, 1.0 if visible else 0.0]
            mat = glb.material('%s_%s' % (g, size), color, 0.85, mask=True, tex=tex)
            glb.mesh('%s_%s' % (g, size), pos, nor, idx, mat, uv)
    glb.save(path)


def write_bundle(presets):
    def uri(p, mime):
        with open(p, 'rb') as fh:
            return 'data:%s;base64,%s' % (mime, base64.b64encode(fh.read()).decode())
    data = {'presets': presets, 'models': {}, 'textures': {}}
    for k, b in presets['bodies'].items():
        data['models'][k] = uri(os.path.join(OUT, b['file']), 'model/gltf-binary')
    for t in ('fabric', 'print'):
        data['textures'][t] = uri(os.path.join(OUT, 'textures', t + '.png'), 'image/png')
    with open(os.path.join(OUT, 'bundle.js'), 'w', encoding='utf8') as fh:
        fh.write('// Сгенерировано tools/build_presets.py — не редактировать вручную\nwindow.PRIMERKA=')
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')


if __name__ == '__main__':
    main()
