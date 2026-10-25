"""Чтение ассетов MakeHuman (CC0): base.obj, .target, .mhclo. Только стандартная библиотека."""
import math


def load_obj(path):
    V, VT, F = [], [], []          # F: (group, [v...], [vt...])
    group = None
    with open(path, encoding='utf8', errors='replace') as fh:
        for line in fh:
            w = line.split()
            if not w:
                continue
            if w[0] == 'v':
                V.append([float(w[1]), float(w[2]), float(w[3])])
            elif w[0] == 'vt':
                VT.append((float(w[1]), float(w[2])))
            elif w[0] == 'g':
                group = w[1] if len(w) > 1 else None
            elif w[0] == 'f':
                vs, ts = [], []
                for t in w[1:]:
                    p = t.split('/')
                    vs.append(int(p[0]) - 1)
                    ts.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                F.append((group, vs, ts))
    return V, VT, F


def load_target(path):
    out = []
    with open(path) as fh:
        for line in fh:
            if line.startswith('#') or not line.strip():
                continue
            w = line.split()
            out.append((int(w[0]), float(w[1]), float(w[2]), float(w[3])))
    return out


def apply_target(V, target, k):
    for i, dx, dy, dz in target:
        v = V[i]
        v[0] += k * dx; v[1] += k * dy; v[2] += k * dz


def load_mhclo(path):
    """Возвращает (refs, scales, delete). refs[i] = ((i0,i1,i2),(w0,w1,w2),(d0,d1,d2))."""
    refs, scales, delete = [], {}, []
    mode = None
    with open(path) as fh:
        for line in fh:
            if line.startswith('#'):
                continue
            w = line.split()
            if not w:
                continue
            if w[0] in ('x_scale', 'y_scale', 'z_scale'):
                scales[w[0][0]] = (int(w[1]), int(w[2]), float(w[3]))
            elif w[0] == 'verts':
                mode = 'verts'
            elif w[0] == 'delete_verts':
                mode = 'delete'
            elif mode == 'verts' and w[0][0].isdigit():
                if len(w) == 1:
                    i = int(w[0]); refs.append(((i, i, i), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
                else:
                    refs.append(((int(w[0]), int(w[1]), int(w[2])),
                                 (float(w[3]), float(w[4]), float(w[5])),
                                 (float(w[6]), float(w[7]), float(w[8]))))
            elif mode == 'delete':
                # индексы или диапазоны "a - b"
                toks = line.split()
                j = 0
                while j < len(toks):
                    if j + 2 < len(toks) and toks[j + 1] == '-':
                        delete.extend(range(int(toks[j]), int(toks[j + 2]) + 1)); j += 3
                    else:
                        delete.append(int(toks[j])); j += 1
            elif w[0] in ('name', 'obj_file', 'material', 'uuid', 'basemesh', 'tag', 'z_depth'):
                mode = None if mode == 'verts' and False else mode
    return refs, scales, delete


def fit_proxy(B, refs, scales):
    """Посадка вещи на тело: барицентр трёх вершин тела + смещение с масштабом фигуры (как в MakeHuman)."""
    def sc(axis, comp):
        if axis not in scales:
            return 1.0
        a, b, d = scales[axis]
        return abs(B[a][comp] - B[b][comp]) / d
    s = (sc('x', 0), sc('y', 1), sc('z', 2))
    out = []
    for (i0, i1, i2), (w0, w1, w2), (d0, d1, d2) in refs:
        a, b, c = B[i0], B[i1], B[i2]
        out.append([w0 * a[k] + w1 * b[k] + w2 * c[k] + (d0, d1, d2)[k] * s[k] for k in range(3)])
    return out


def tri_faces(F, groups=None):
    tris = []
    for g, vs, ts in F:
        if groups is not None and g not in groups:
            continue
        for k in range(1, len(vs) - 1):
            tris.append(((vs[0], vs[k], vs[k + 1]), (ts[0], ts[k], ts[k + 1])))
    return tris


def vertex_normals(V, tris):
    N = [[0.0, 0.0, 0.0] for _ in V]
    for (a, b, c), _ in tris:
        A, Bv, C = V[a], V[b], V[c]
        ux, uy, uz = Bv[0] - A[0], Bv[1] - A[1], Bv[2] - A[2]
        vx, vy, vz = C[0] - A[0], C[1] - A[1], C[2] - A[2]
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        for i in (a, b, c):
            N[i][0] += n[0]; N[i][1] += n[1]; N[i][2] += n[2]
    for n in N:
        l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        n[0] /= l; n[1] /= l; n[2] /= l
    return N


# ---- срезы и обхваты (обхват = периметр выпуклой оболочки, как сантиметровая лента) ----

def slice_points(V, tris, y):
    pts = []
    for (a, b, c), _ in tris:
        for p, q in ((a, b), (b, c), (c, a)):
            ya, yb = V[p][1], V[q][1]
            if (ya - y) * (yb - y) < 0:
                t = (y - ya) / (yb - ya)
                pts.append((V[p][0] + t * (V[q][0] - V[p][0]), V[p][2] + t * (V[q][2] - V[p][2])))
    return pts


def hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def perimeter(h):
    return sum(math.dist(h[i], h[(i + 1) % len(h)]) for i in range(len(h))) if len(h) > 2 else 0.0


def clusters_x(pts, gap):
    """Разбивает точки среза на группы по зазорам вдоль X (торс / руки / ноги)."""
    pts = sorted(pts)
    out, cur = [], []
    for p in pts:
        if cur and p[0] - cur[-1][0] > gap:
            out.append(cur); cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def girth(V, tris, y, x0=None, gap=0.25):
    """Обхват на высоте y. x0 — выбрать группу точек, содержащую эту X (0 = торс)."""
    pts = slice_points(V, tris, y)
    if not pts:
        return 0.0
    if x0 is None:
        return perimeter(hull(pts))
    groups = clusters_x(pts, gap)
    best = min(groups, key=lambda g: min(abs(p[0] - x0) for p in g))
    return perimeter(hull(best))
