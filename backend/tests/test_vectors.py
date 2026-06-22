"""GET /api/v1/vectors — detector discovery."""
from __future__ import annotations


EXPECTED = {
    "covered_text",
    "hidden_text",
    "revision_history",
    "embedded_files",
    "metadata",
    "redact_annotations",
}


def test_vectors_lists_all_six(client):
    r = client.get("/api/v1/vectors")
    assert r.status_code == 200
    body = r.json()
    assert "vectors" in body
    names = {v["name"] for v in body["vectors"]}
    assert names == EXPECTED


def test_vectors_have_descriptions(client):
    r = client.get("/api/v1/vectors")
    assert r.status_code == 200
    for v in r.json()["vectors"]:
        assert v["name"], "every vector must have a name"
        assert isinstance(v["description"], str), "description must be a string"


def test_vectors_descriptions_are_real_not_generic(client):
    """Descriptions must come from each detector's module docstring, not the
    generic '<name> detector' fallback."""
    r = client.get("/api/v1/vectors")
    vectors = {v["name"]: v["description"] for v in r.json()["vectors"]}
    for name, desc in vectors.items():
        assert desc, f"{name} has an empty description"
        assert desc != f"{name} detector", f"{name} fell back to a generic description"
    # Spot-check against a known module docstring first line.
    assert "extractable" in vectors["covered_text"].lower()