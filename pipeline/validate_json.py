"""validate_json.py — M1 gate validator for web/data/graph_data.json.

Checks (per plan task 1.7):
  (a) every link source/target exists in nodes
  (b) no duplicate node ids
  (c) link values within [0,1], no NaN coordinates
  (d) every node has all required fields incl. a non-empty neighbors list
  (e) every clusterLabels key corresponds to an existing cluster
  (f) prints counts: nodes, links per type, cluster distribution

Exit code 0 = green (gate passes), 1 = at least one check failed.
"""
import json
import math
import os
import sys
from collections import Counter

import config as C

REQUIRED_NODE_FIELDS = ["id", "name", "category", "cluster", "tokens",
                        "x", "y", "z", "text", "truncated", "neighbors"]
REQUIRED_LINK_FIELDS = ["source", "target", "value", "type"]

path = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), C.OUTPUT_JSON))

errors: list[str] = []

if not os.path.exists(path):
    print(f"FAIL: {path} does not exist — run build_graph.py first.")
    sys.exit(1)

with open(path, encoding="utf-8") as f:
    data = json.load(f)

meta = data.get("meta", {})
nodes = data.get("nodes", [])
links = data.get("links", [])

# (b) no duplicate ids
ids = [n.get("id") for n in nodes]
dupes = [i for i, c in Counter(ids).items() if c > 1]
if dupes:
    errors.append(f"(b) duplicate node ids: {dupes[:10]}")
id_set = set(ids)

# (a) every source/target exists
for l in links:
    if l.get("source") not in id_set or l.get("target") not in id_set:
        errors.append(f"(a) dangling link: {l}")
        break

# (c) values in [0,1], no NaN coordinates
for l in links:
    v = l.get("value")
    if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
        errors.append(f"(c) link value out of [0,1]: {l}")
        break
for n in nodes:
    for axis in ("x", "y", "z"):
        v = n.get(axis)
        if not isinstance(v, (int, float)) or math.isnan(v):
            errors.append(f"(c) NaN/invalid coordinate on node {n.get('id')}")
            break

# (d) all fields present, neighbors non-empty
for n in nodes:
    missing = [f for f in REQUIRED_NODE_FIELDS if f not in n]
    if missing:
        errors.append(f"(d) node {n.get('id')} missing fields: {missing}")
        break
    if not n["neighbors"]:
        errors.append(f"(d) node {n['id']} has an empty neighbors list")
        break
    for nb in n["neighbors"]:
        if nb["id"] not in id_set:
            errors.append(f"(d) node {n['id']} neighbor {nb['id']} not in nodes")
            break
for l in links:
    missing = [f for f in REQUIRED_LINK_FIELDS if f not in l]
    if missing:
        errors.append(f"link missing fields: {missing} in {l}")
        break

# (e) clusterLabels keys correspond to existing clusters
clusters_present = {str(n.get("cluster")) for n in nodes}
label_keys = set(meta.get("clusterLabels", {}).keys())
if label_keys != clusters_present:
    errors.append(f"(e) clusterLabels keys {sorted(label_keys)} != "
                  f"clusters in data {sorted(clusters_present)}")

# (g) schema v1.1 flags: optional knn / struct must be booleans when present
for l in links:
    for flag in ("knn", "struct"):
        if flag in l and not isinstance(l[flag], bool):
            errors.append(f"(g) link flag '{flag}' is not a bool: {l}")
            break

# (f) counts
print(f"file: {path}  ({os.path.getsize(path)/1e6:.2f} MB)")
print(f"nodes: {len(nodes)}")
print("links per type:", dict(Counter(l['type'] for l in links)))
print("cluster distribution:",
      dict(sorted(Counter(n['cluster'] for n in nodes).items())))
print("meta:", {k: (v if k != 'clusterLabels' else f'{len(v)} labels')
                for k, v in meta.items()})

if errors:
    print("\nVALIDATION FAILED:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("\nVALIDATION GREEN — graph_data.json conforms to schema v1.1.")
