"""Task 0.2 smoke test.

Run:  conda activate vse && python smoke_test.py
Expected: shape (1, 384) and sim(similar pair) > sim(unrelated pair).
"""
from sentence_transformers import SentenceTransformer

m = SentenceTransformer("all-MiniLM-L6-v2")

# Basic smoke test
shape = m.encode(["test"]).shape
print("encode(['test']).shape =", shape, "-> expected (1, 384)")
assert shape == (1, 384), "Unexpected embedding shape!"

# Extended smoke test: two similar sentences, one unrelated.
sents = [
    "The rocket was launched into orbit around the Earth.",   # a
    "NASA sent a spacecraft into space last week.",           # b (similar to a)
    "My favorite pasta recipe uses garlic and olive oil.",    # c (unrelated)
]
E = m.encode(sents, normalize_embeddings=True)
sim_ab = float(E[0] @ E[1])
sim_ac = float(E[0] @ E[2])
print(f"cos(a,b) = {sim_ab:.3f}   cos(a,c) = {sim_ac:.3f}")
assert sim_ab > sim_ac, "Model is not semantically sane?!"
print("OK — model downloaded, cached, and semantically sane.")
