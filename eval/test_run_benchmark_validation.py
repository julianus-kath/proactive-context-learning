from eval.run_benchmark import artifact_validation_errors


def build_artifact(**overrides):
    base = {
        "final_answer_text": "Answer",
        "sql_executed": ["SELECT 1"],
        "tables_used": ["orders"],
        "row_count": 1,
        "result_preview": [{"id": 1}],
    }
    base.update(overrides)
    return base


def test_validation_passes_for_grounded_answer():
    artifact = build_artifact()
    assert artifact_validation_errors(artifact) == []


def test_validation_flags_internal_error():
    artifact = build_artifact(final_answer_text="Internal error occurred")
    assert "invalid_final_answer" in artifact_validation_errors(artifact)


def test_validation_flags_missing_sql():
    artifact = build_artifact(sql_executed=[" "])
    assert "missing_sql" in artifact_validation_errors(artifact)


def test_validation_flags_missing_tables():
    artifact = build_artifact(tables_used=[])
    assert "missing_tables" in artifact_validation_errors(artifact)


def test_validation_flags_missing_results():
    artifact = build_artifact(row_count=None, result_preview=[])
    assert "missing_results" in artifact_validation_errors(artifact)
