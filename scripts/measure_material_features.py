#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path


def load_vertices(path):
    obj = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    for key in ('final_vertices', 'candidate_vertices', 'ordered_turn_vertex_points'):
        if key in obj:
            return [tuple(map(float, p)) for p in obj[key]]
    raise ValueError('No supported vertex array found')


def cyclic_dist(i, j, n):
    d = abs(i - j)
    return min(d, n - d)


def line_y_at_x(a, b, x):
    x1, y1 = a
    x2, y2 = b
    if abs(x2 - x1) < 1e-15:
        return None
    t = (x - x1) / (x2 - x1)
    return y1 + t * (y2 - y1)


def line_x_at_y(a, b, y):
    x1, y1 = a
    x2, y2 = b
    if abs(y2 - y1) < 1e-15:
        return None
    t = (y - y1) / (y2 - y1)
    return x1 + t * (x2 - x1)


def turn_angle_deg(prev_pt, cur_pt, next_pt):
    v1 = (prev_pt[0] - cur_pt[0], prev_pt[1] - cur_pt[1])
    v2 = (next_pt[0] - cur_pt[0], next_pt[1] - cur_pt[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 180.0
    cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cosv))


def build_segments(vertices):
    segs = []
    n = len(vertices)
    for i in range(n):
        j = (i + 1) % n
        a = vertices[i]
        b = vertices[j]
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        segs.append({
            'i': i,
            'j': j,
            'a': a,
            'b': b,
            'dx': dx,
            'dy': dy,
            'len': math.hypot(dx, dy),
            'h_ratio': abs(dy) / (abs(dx) + 1e-20),
            'v_ratio': abs(dx) / (abs(dy) + 1e-20),
        })
    return segs


def group_contiguous(indices, n):
    if not indices:
        return []
    indices = sorted(indices)
    groups = [[indices[0]]]
    for idx in indices[1:]:
        if idx == groups[-1][-1] + 1:
            groups[-1].append(idx)
        else:
            groups.append([idx])
    if len(groups) > 1 and groups[0][0] == 0 and groups[-1][-1] == n - 1:
        groups[0] = groups[-1] + groups[0]
        groups.pop()
    return groups


def build_edge_groups(vertices, segs, mode='horizontal', ratio_thr=0.35):
    n = len(vertices)
    if mode == 'horizontal':
        idxs = [k for k, s in enumerate(segs) if s['h_ratio'] <= ratio_thr]
    else:
        idxs = [k for k, s in enumerate(segs) if s['v_ratio'] <= ratio_thr]
    groups = []
    for g in group_contiguous(idxs, n):
        pts_idx = [g[0]] + [((idx + 1) % n) for idx in g]
        pts = [vertices[idx] for idx in pts_idx]
        groups.append({
            'mode': mode,
            'segment_indices': g,
            'vertex_indices': pts_idx,
            'points': pts,
            'start': pts[0],
            'end': pts[-1],
        })
    return groups


def choose_background_group(vertices, groups, cur_idx, axis='y'):
    cur = vertices[cur_idx]
    n = len(vertices)
    best = None
    for g in groups:
        if any(cyclic_dist(cur_idx, vidx, n) <= 1 for vidx in g['vertex_indices']):
            continue
        a = g['start']
        b = g['end']
        if axis == 'y':
            ref = line_y_at_x(a, b, cur[0])
            if ref is None:
                continue
            delta = cur[1] - ref
        else:
            ref = line_x_at_y(a, b, cur[1])
            if ref is None:
                continue
            delta = cur[0] - ref
        order_gap = min(cyclic_dist(cur_idx, vidx, n) for vidx in g['vertex_indices'])
        score = abs(delta) + 2e-4 * order_gap
        if best is None or score < best['score']:
            best = {'group': g, 'ref': ref, 'delta': delta, 'score': score}
    return best


def auto_detect(vertices, y_flat_tol=5e-4, x_flat_tol=5e-4, min_dev=1e-4):
    n = len(vertices)
    segs = build_segments(vertices)
    h_groups = build_edge_groups(vertices, segs, 'horizontal', ratio_thr=0.35)
    v_groups = build_edge_groups(vertices, segs, 'vertical', ratio_thr=0.35)
    features = []
    for i in range(n):
        prev = vertices[(i - 1) % n]
        cur = vertices[i]
        nxt = vertices[(i + 1) % n]
        candidates = []

        if cur[1] > prev[1] and cur[1] > nxt[1]:
            if abs(prev[1] - nxt[1]) <= y_flat_tol:
                ref_y = 0.5 * (prev[1] + nxt[1])
                candidates.append({
                    'axis': 'y', 'feature_type': 'protrusion', 'background_kind': 'local_y_chord',
                    'ref_value': ref_y, 'delta': cur[1] - ref_y, 'width_um': abs(nxt[0] - prev[0]),
                    'indices_1based': [((i - 1) % n) + 1, i + 1, ((i + 1) % n) + 1],
                    'background_edge_vertices_1based': [((i - 1) % n) + 1, ((i + 1) % n) + 1],
                })
            else:
                bg = choose_background_group(vertices, h_groups, i, 'y')
                if bg is not None:
                    g = bg['group']
                    candidates.append({
                        'axis': 'y', 'feature_type': 'protrusion', 'background_kind': 'horizontal_group',
                        'ref_value': bg['ref'], 'delta': bg['delta'], 'width_um': abs(g['end'][0] - g['start'][0]),
                        'indices_1based': [i + 1],
                        'background_edge_vertices_1based': [g['vertex_indices'][0] + 1, g['vertex_indices'][-1] + 1],
                    })

        if cur[1] < prev[1] and cur[1] < nxt[1]:
            if abs(prev[1] - nxt[1]) <= y_flat_tol:
                ref_y = 0.5 * (prev[1] + nxt[1])
                candidates.append({
                    'axis': 'y', 'feature_type': 'recess', 'background_kind': 'local_y_chord',
                    'ref_value': ref_y, 'delta': cur[1] - ref_y, 'width_um': abs(nxt[0] - prev[0]),
                    'indices_1based': [((i - 1) % n) + 1, i + 1, ((i + 1) % n) + 1],
                    'background_edge_vertices_1based': [((i - 1) % n) + 1, ((i + 1) % n) + 1],
                })
            else:
                bg = choose_background_group(vertices, h_groups, i, 'y')
                if bg is not None:
                    g = bg['group']
                    candidates.append({
                        'axis': 'y', 'feature_type': 'recess', 'background_kind': 'horizontal_group',
                        'ref_value': bg['ref'], 'delta': bg['delta'], 'width_um': abs(g['end'][0] - g['start'][0]),
                        'indices_1based': [i + 1],
                        'background_edge_vertices_1based': [g['vertex_indices'][0] + 1, g['vertex_indices'][-1] + 1],
                    })

        if cur[0] > prev[0] and cur[0] > nxt[0]:
            if abs(prev[0] - nxt[0]) <= x_flat_tol:
                ref_x = 0.5 * (prev[0] + nxt[0])
                candidates.append({
                    'axis': 'x', 'feature_type': 'protrusion', 'background_kind': 'local_x_chord',
                    'ref_value': ref_x, 'delta': cur[0] - ref_x, 'width_um': abs(nxt[1] - prev[1]),
                    'indices_1based': [((i - 1) % n) + 1, i + 1, ((i + 1) % n) + 1],
                    'background_edge_vertices_1based': [((i - 1) % n) + 1, ((i + 1) % n) + 1],
                })
            else:
                bg = choose_background_group(vertices, v_groups, i, 'x')
                if bg is not None:
                    g = bg['group']
                    candidates.append({
                        'axis': 'x', 'feature_type': 'protrusion', 'background_kind': 'vertical_group',
                        'ref_value': bg['ref'], 'delta': bg['delta'], 'width_um': abs(g['end'][1] - g['start'][1]),
                        'indices_1based': [i + 1],
                        'background_edge_vertices_1based': [g['vertex_indices'][0] + 1, g['vertex_indices'][-1] + 1],
                    })

        if cur[0] < prev[0] and cur[0] < nxt[0]:
            if abs(prev[0] - nxt[0]) <= x_flat_tol:
                ref_x = 0.5 * (prev[0] + nxt[0])
                candidates.append({
                    'axis': 'x', 'feature_type': 'recess', 'background_kind': 'local_x_chord',
                    'ref_value': ref_x, 'delta': cur[0] - ref_x, 'width_um': abs(nxt[1] - prev[1]),
                    'indices_1based': [((i - 1) % n) + 1, i + 1, ((i + 1) % n) + 1],
                    'background_edge_vertices_1based': [((i - 1) % n) + 1, ((i + 1) % n) + 1],
                })
            else:
                bg = choose_background_group(vertices, v_groups, i, 'x')
                if bg is not None:
                    g = bg['group']
                    candidates.append({
                        'axis': 'x', 'feature_type': 'recess', 'background_kind': 'vertical_group',
                        'ref_value': bg['ref'], 'delta': bg['delta'], 'width_um': abs(g['end'][1] - g['start'][1]),
                        'indices_1based': [i + 1],
                        'background_edge_vertices_1based': [g['vertex_indices'][0] + 1, g['vertex_indices'][-1] + 1],
                    })

        if candidates:
            best = max(candidates, key=lambda c: abs(c['delta']))
            best['height_or_depth_um'] = abs(best['delta'])
            best['turn_angle_deg'] = turn_angle_deg(prev, cur, nxt)
            best['vertex_index_1based'] = i + 1
            best['cur'] = cur
            best['prev_local'] = prev
            best['next_local'] = nxt
            if abs(best['delta']) >= min_dev:
                features.append(best)

    return {'horizontal_groups': h_groups, 'vertical_groups': v_groups, 'features': features}


def write_csv(path, features):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([
            'vertex_index_1based', 'feature_type', 'axis', 'background_kind', 'height_or_depth_um',
            'width_um', 'ref_value', 'cur_x_um', 'cur_y_um', 'turn_angle_deg', 'background_edge_vertices_1based'
        ])
        for item in features:
            w.writerow([
                item['vertex_index_1based'], item['feature_type'], item['axis'], item['background_kind'],
                item['height_or_depth_um'], item['width_um'], item['ref_value'], item['cur'][0], item['cur'][1],
                item['turn_angle_deg'], '-'.join(map(str, item['background_edge_vertices_1based']))
            ])


def main():
    ap = argparse.ArgumentParser(description='Auto detect protrusions and recesses from ordered material vertices.')
    ap.add_argument('--input', required=True)
    ap.add_argument('--json-out', required=True)
    ap.add_argument('--csv-out', required=True)
    ap.add_argument('--min-dev', type=float, default=1e-4)
    args = ap.parse_args()
    vertices = load_vertices(args.input)
    result = auto_detect(vertices, min_dev=args.min_dev)
    features = result['features']
    summary = {
        'feature_count': len(features),
        'protrusion_count': sum(1 for x in features if x['feature_type'] == 'protrusion'),
        'recess_count': sum(1 for x in features if x['feature_type'] == 'recess'),
        'largest_protrusion': max([x for x in features if x['feature_type'] == 'protrusion'], key=lambda x: x['height_or_depth_um']) if any(x['feature_type'] == 'protrusion' for x in features) else None,
        'largest_recess': max([x for x in features if x['feature_type'] == 'recess'], key=lambda x: x['height_or_depth_um']) if any(x['feature_type'] == 'recess' for x in features) else None,
    }
    payload = {
        'input': args.input,
        'vertex_count': len(vertices),
        'horizontal_groups': result['horizontal_groups'],
        'vertical_groups': result['vertical_groups'],
        'features': features,
        'summary': summary,
    }
    Path(args.json_out).write_text(json.dumps(payload, indent=2))
    write_csv(args.csv_out, features)
    print(json.dumps({'summary': summary, 'json_out': args.json_out, 'csv_out': args.csv_out}, indent=2))


if __name__ == '__main__':
    main()
