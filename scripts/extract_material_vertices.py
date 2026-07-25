#!/usr/bin/env python3
import argparse
import csv
import json
import math
import re
from collections import defaultdict, deque
from pathlib import Path

REGION_HEADER = re.compile(r'^\s*Region \("([^"]+)"\) \{$')


def parse_vertices(lines, i):
    n = int(re.match(r'\s*Vertices \((\d+)\) \{', lines[i]).group(1))
    i += 1
    arr = []
    while len(arr) < n:
        s = lines[i].strip()
        if s == '}':
            break
        a, b = s.split()[:2]
        arr.append((float(a), float(b)))
        i += 1
    return arr, i


def parse_edges(lines, i):
    n = int(re.match(r'\s*Edges \((\d+)\) \{', lines[i]).group(1))
    i += 1
    arr = {}
    idx = 1
    while idx <= n:
        s = lines[i].strip()
        if s == '}':
            break
        a, b = s.split()[:2]
        arr[idx] = (int(a), int(b))
        idx += 1
        i += 1
    return arr, i


def parse_elements(lines, i):
    n = int(re.match(r'\s*Elements \((\d+)\) \{', lines[i]).group(1))
    i += 1
    arr = {}
    idx = 1
    while idx <= n:
        s = lines[i].strip()
        if s == '}':
            break
        arr[idx] = [int(x) for x in s.split()]
        idx += 1
        i += 1
    return arr, i


def parse_region(lines, i):
    name = REGION_HEADER.match(lines[i]).group(1)
    material = None
    elem_ids = []
    i += 1
    while i < len(lines):
        s = lines[i].rstrip('\n')
        if s.startswith('  Region ("'):
            break
        m = re.match(r'\s*material\s*=\s*(\S+)', s)
        if m:
            material = m.group(1)
        m = re.match(r'\s*Elements \((\d+)\) \{', s)
        if m:
            cnt = int(m.group(1))
            i += 1
            while len(elem_ids) < cnt:
                t = lines[i].strip()
                if t == '}':
                    break
                elem_ids.extend(int(tok) for tok in t.split())
                i += 1
            continue
        i += 1
    return name, material, elem_ids, i


def load_grd(path):
    lines = Path(path).read_text(errors='ignore').splitlines()
    verts = edges = elems = None
    regions = []
    i = 0
    while i < len(lines):
        s = lines[i]
        if verts is None and re.match(r'\s*Vertices \(\d+\) \{', s):
            verts, i = parse_vertices(lines, i)
        elif edges is None and re.match(r'\s*Edges \(\d+\) \{', s):
            edges, i = parse_edges(lines, i)
        elif elems is None and re.match(r'\s*Elements \(\d+\) \{', s):
            elems, i = parse_elements(lines, i)
        elif REGION_HEADER.match(s):
            reg = parse_region(lines, i)
            regions.append(reg[:3])
            i = reg[3]
        i += 1
    return verts, edges, elems, regions


def region_boundary_edges(region_elem_ids, elems):
    counts = defaultdict(int)
    for eid in region_elem_ids:
        if eid not in elems or eid == 0:
            continue
        for edge_id in elems[eid][1:]:
            counts[abs(edge_id)] += 1
    return [eid for eid, c in counts.items() if c == 1]


def build_vertex_region_map(edges, elems, regions):
    vertex_regions = defaultdict(set)
    vertex_materials = defaultdict(set)
    global_adj = defaultdict(set)
    for eid, pair in edges.items():
        a, b = pair
        a = abs(a)
        b = abs(b)
        if a == 0 or b == 0:
            continue
        global_adj[a].add(b)
        global_adj[b].add(a)
    for name, material, elem_ids in regions:
        for eid in elem_ids:
            row = elems.get(eid)
            if not row:
                continue
            for edge_id in row[1:]:
                edge_id = abs(edge_id)
                if edge_id == 0 or edge_id not in edges:
                    continue
                a, b = edges[edge_id]
                for vid in (abs(a), abs(b)):
                    vertex_regions[vid].add(name)
                    vertex_materials[vid].add(material)
    return vertex_regions, vertex_materials, global_adj


def point_dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def unit_vec_pts(a, b):
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    n = math.hypot(dx, dy)
    return (0.0, 0.0) if n == 0 else (dx / n, dy / n)


def cos_pts(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]


def build_boundary_graph(verts, edges, boundary_eids, roi):
    def in_roi(x, y):
        return roi['x_min'] <= x <= roi['x_max'] and roi['y_min'] <= y <= roi['y_max']
    adj = defaultdict(dict)
    for eid in boundary_eids:
        a, b = edges[eid]
        a = abs(a)
        b = abs(b)
        xa, ya = verts[a - 1]
        xb, yb = verts[b - 1]
        if not (in_roi(xa, ya) or in_roi(xb, yb)):
            continue
        w = math.hypot(xb - xa, yb - ya)
        adj[a][b] = {'kind': 'mesh', 'w': w, 'eid': eid}
        adj[b][a] = {'kind': 'mesh', 'w': w, 'eid': eid}
    return adj


def add_local_bridges(verts, adj, roi, bridge_dx=8.5e-4, bridge_dy=8.5e-4, bridge_d=8.75e-4):
    def in_roi(x, y):
        return roi['x_min'] <= x <= roi['x_max'] and roi['y_min'] <= y <= roi['y_max']
    vids = [vid for vid in adj if in_roi(*verts[vid - 1])]
    pts = [(vid, verts[vid - 1][0], verts[vid - 1][1]) for vid in vids]
    added = 0
    for i in range(len(pts)):
        v1, x1, y1 = pts[i]
        for j in range(i + 1, len(pts)):
            v2, x2, y2 = pts[j]
            if v2 in adj[v1]:
                continue
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dx > bridge_dx or dy > bridge_dy:
                continue
            d = math.hypot(dx, dy)
            if d == 0 or d > bridge_d:
                continue
            if dx <= 2.2e-4 or dy <= 2.2e-4:
                adj[v1][v2] = {'kind': 'local_bridge', 'w': d * 1.25, 'eid': None}
                adj[v2][v1] = {'kind': 'local_bridge', 'w': d * 1.25, 'eid': None}
                added += 1
    return added


def is_boundary_point(vid, verts, adj, vertex_regions, vertex_materials, global_adj, roi, target_region, target_material):
    x, y = verts[vid - 1]
    if not (roi['x_min'] <= x <= roi['x_max'] and roi['y_min'] <= y <= roi['y_max']):
        return False, 'out_of_roi'
    if vid not in adj or len(adj[vid]) == 0:
        return False, 'not_boundary'
    materials = vertex_materials.get(vid, set())
    regions = vertex_regions.get(vid, set())
    if target_material not in materials:
        return False, 'missing_target_material'
    if target_region not in regions:
        return False, 'missing_target_region'
    has_foreign_or_shared_neighbor = False
    for nvid in global_adj.get(vid, set()):
        n_mats = vertex_materials.get(nvid, set())
        n_regs = vertex_regions.get(nvid, set())
        if (target_material not in n_mats) or (target_region not in n_regs) or (len(n_mats) > 1) or (len(n_regs) > 1):
            has_foreign_or_shared_neighbor = True
            break
    if has_foreign_or_shared_neighbor:
        return True, 'ok_including_shared_neighbor'
    if len(adj.get(vid, {})) <= 1:
        return True, 'ok_endpoint_blank_like'
    return False, 'no_foreign_shared_or_blank_neighbor'


def point_boundary_qualification(vid, verts, adj, vertex_regions, vertex_materials, global_adj, roi, target_region, target_material):
    x, y = verts[vid - 1]
    ok, reason = is_boundary_point(vid, verts, adj, vertex_regions, vertex_materials, global_adj, roi, target_region, target_material)
    return {
        'vid': vid,
        'x': x,
        'y': y,
        'neighbor_count': len(adj.get(vid, {})),
        'materials': sorted(vertex_materials.get(vid, set())),
        'regions': sorted(vertex_regions.get(vid, set())),
        'qualified': ok,
        'reason': reason,
    }


def components(nodes, sub):
    seen = set()
    comps = []
    for v in nodes:
        if v in seen:
            continue
        dq = deque([v])
        seen.add(v)
        comp = []
        while dq:
            x = dq.popleft()
            comp.append(x)
            for n in sub[x]:
                if n not in seen:
                    seen.add(n)
                    dq.append(n)
        comps.append(comp)
    return comps


def dist_vid(a, b, verts):
    xa, ya = verts[a - 1]
    xb, yb = verts[b - 1]
    return math.hypot(xb - xa, yb - ya)


def cos_penalty(prev_vid, cur_vid, nxt_vid, verts):
    if prev_vid is None:
        return 0.0
    x0, y0 = verts[prev_vid - 1]
    x1, y1 = verts[cur_vid - 1]
    x2, y2 = verts[nxt_vid - 1]
    v1 = (x1 - x0, y1 - y0)
    v2 = (x2 - x1, y2 - y1)
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cosv = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return (1.0 - cosv) * 4.0e-4


def pick_start(comp, verts):
    return max(comp, key=lambda v: (verts[v - 1][1], verts[v - 1][0]))


def order_component(comp, sub, verts):
    unvisited = set(comp)
    start = pick_start(comp, verts)
    order = [start]
    unvisited.remove(start)
    prev_vid = None
    cur_vid = start
    while unvisited:
        neigh = [n for n in sub[cur_vid] if n in unvisited]
        if not neigh:
            neigh = sorted(unvisited, key=lambda n: (dist_vid(cur_vid, n, verts), -verts[n - 1][1], abs(verts[n - 1][0])))[:12]
        best = None
        for n in neigh:
            d = dist_vid(cur_vid, n, verts)
            score = d + cos_penalty(prev_vid, cur_vid, n, verts)
            if best is None or score < best[0]:
                best = (score, n)
        nxt = best[1]
        order.append(nxt)
        unvisited.remove(nxt)
        prev_vid, cur_vid = cur_vid, nxt
    return order


def stream_vertices(points, collinear_cos=0.992, min_seg=1.0e-4):
    if len(points) <= 2:
        return list(points), []
    verts = [points[0]]
    diagnostics = []
    seg_start = points[0]
    cur = points[1]
    for nxt in points[2:]:
        v1 = unit_vec_pts(seg_start, cur)
        v2 = unit_vec_pts(cur, nxt)
        cosv = cos_pts(v1, v2)
        seg1 = point_dist(seg_start, cur)
        seg2 = point_dist(cur, nxt)
        is_collinear = cosv >= collinear_cos and seg1 >= min_seg and seg2 >= min_seg
        diagnostics.append({
            'segment_start': seg_start,
            'current': cur,
            'next': nxt,
            'cos_similarity': cosv,
            'segment_in_um': seg1,
            'segment_out_um': seg2,
            'vertex_triggered': not is_collinear,
        })
        if is_collinear:
            cur = nxt
            continue
        verts.append(cur)
        seg_start = cur
        cur = nxt
    if not verts or verts[-1] != cur:
        verts.append(cur)
    if verts[-1] != points[-1]:
        verts.append(points[-1])
    out = [verts[0]]
    for p in verts[1:]:
        if point_dist(out[-1], p) > 1e-10:
            out.append(p)
    return out, diagnostics


def compress_vertices(points, cos_thr=0.996, min_leg=2.0e-4, lookahead=8):
    if len(points) <= 2:
        return list(points), []
    out = [points[0]]
    diag = []
    i = 1
    while i < len(points) - 1:
        prev = out[-1]
        cur = points[i]
        is_vertex = False
        for j in range(i + 1, min(len(points), i + lookahead + 1)):
            nxt = points[j]
            leg1 = point_dist(prev, cur)
            leg2 = point_dist(cur, nxt)
            if leg1 < min_leg or leg2 < min_leg:
                continue
            vin = unit_vec_pts(prev, cur)
            vout = unit_vec_pts(cur, nxt)
            cosv = cos_pts(vin, vout)
            diag.append({
                'prev': prev,
                'cur': cur,
                'nxt': nxt,
                'cos_similarity': cosv,
                'leg_in_um': leg1,
                'leg_out_um': leg2,
            })
            if cosv < cos_thr:
                is_vertex = True
                break
        if is_vertex:
            out.append(cur)
        i += 1
    if point_dist(out[-1], points[-1]) > 1.0e-12:
        out.append(points[-1])
    dedup = [out[0]]
    for pt in out[1:]:
        if point_dist(dedup[-1], pt) > 1.0e-12:
            dedup.append(pt)
    return dedup, diag


def write_csv(path, qualifications):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['vid', 'x', 'y', 'qualified', 'reason', 'neighbor_count', 'materials', 'regions'])
        for q in qualifications:
            w.writerow([q['vid'], q['x'], q['y'], q['qualified'], q['reason'], q['neighbor_count'], ';'.join(q['materials']), ';'.join(q['regions'])])


def main():
    ap = argparse.ArgumentParser(description='Generic material boundary extraction from Sprocess DF-ISE geometry.')
    ap.add_argument('--grd', required=True)
    ap.add_argument('--target-region', required=True)
    ap.add_argument('--target-material', required=True)
    ap.add_argument('--xmin', type=float, required=True)
    ap.add_argument('--xmax', type=float, required=True)
    ap.add_argument('--ymin', type=float, required=True)
    ap.add_argument('--ymax', type=float, required=True)
    ap.add_argument('--json-out', required=True)
    ap.add_argument('--csv-out', required=True)
    args = ap.parse_args()

    roi = {'x_min': args.xmin, 'x_max': args.xmax, 'y_min': args.ymin, 'y_max': args.ymax}
    verts, edges, elems, regions = load_grd(args.grd)
    region_map = {n: (m, ids) for n, m, ids in regions}
    if args.target_region not in region_map:
        raise ValueError('Target region not found: %s' % args.target_region)
    material, elem_ids = region_map[args.target_region]
    boundary_eids = region_boundary_edges(elem_ids, elems)
    adj = build_boundary_graph(verts, edges, boundary_eids, roi)
    local_bridge_count = add_local_bridges(verts, adj, roi)
    vertex_regions, vertex_materials, global_adj = build_vertex_region_map(edges, elems, regions)
    all_vids = sorted(adj)
    qualifications = [
        point_boundary_qualification(v, verts, adj, vertex_regions, vertex_materials, global_adj, roi, args.target_region, args.target_material)
        for v in all_vids
        if roi['x_min'] <= verts[v - 1][0] <= roi['x_max'] and roi['y_min'] <= verts[v - 1][1] <= roi['y_max']
    ]
    qualified_vids = [q['vid'] for q in qualifications if q['qualified']]
    qset = set(qualified_vids)
    sub = defaultdict(list)
    for v in qualified_vids:
        for n in adj.get(v, {}):
            if n in qset:
                sub[v].append(n)
    comps = components(qualified_vids, sub)
    ordered_comps = [order_component(comp, sub, verts) for comp in comps]
    remaining = ordered_comps[:]
    seed_idx = max(range(len(remaining)), key=lambda i: max(verts[v - 1][1] for v in remaining[i]))
    full = remaining.pop(seed_idx)
    while remaining:
        cur_end = full[-1]
        best = None
        for i, seq in enumerate(remaining):
            d0 = dist_vid(cur_end, seq[0], verts)
            d1 = dist_vid(cur_end, seq[-1], verts)
            cand = (d0, i, False) if d0 <= d1 else (d1, i, True)
            if best is None or cand[0] < best[0]:
                best = cand
        _, idx, rev = best
        seq = remaining.pop(idx)
        if rev:
            seq = list(reversed(seq))
        full = full + seq
    path_points = [verts[v - 1] for v in full]
    raw_turns, stream_diag = stream_vertices(path_points)
    filtered_turns, filter_diag = compress_vertices(raw_turns)
    write_csv(args.csv_out, qualifications)
    payload = {
        'grd': args.grd,
        'target_region': args.target_region,
        'target_material': args.target_material,
        'roi': roi,
        'n_boundary_edges_target': len(boundary_eids),
        'n_boundary_nodes_target': len(adj),
        'n_local_bridges_added': local_bridge_count,
        'qualified_boundary_points': qualifications,
        'component_sizes': [len(c) for c in comps],
        'ordered_candidate_points': path_points,
        'raw_turn_vertex_points': raw_turns,
        'ordered_turn_vertex_points': filtered_turns,
        'stream_diagnostics_count': len(stream_diag),
        'filter_diagnostics_count': len(filter_diag),
        'diagnostics_csv': args.csv_out,
    }
    Path(args.json_out).write_text(json.dumps(payload, indent=2))
    print(json.dumps({
        'qualified_count': len(qualified_vids),
        'component_sizes': [len(c) for c in comps],
        'ordered_points': len(path_points),
        'vertex_count': len(filtered_turns),
        'json_out': args.json_out,
        'csv_out': args.csv_out,
    }, indent=2))


if __name__ == '__main__':
    main()
