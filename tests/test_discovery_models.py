import pytest

from langgraph_integration.contracts.discovery_models import DiscoveryCandidate, DiscoveryOutput


def test_discovery_candidate_normalizes_full_name_and_scores():
    candidate = DiscoveryCandidate.model_validate(
        {
            "table_name": "KHKAdressen",
            "schema": "dbo",
            "type": "VIEW",
            "relevance_score": "0.83",
            "role_coverage": "0.72",
            "estimated_rows": "1200",
        }
    )

    assert candidate.full_name == "dbo.KHKAdressen"
    assert candidate.name == "KHKAdressen"
    assert candidate.schema == "dbo"
    assert candidate.is_view is True
    assert candidate.relevance_score == pytest.approx(0.83, rel=1e-5)
    assert candidate.role_coverage == pytest.approx(0.72, rel=1e-5)
    assert candidate.estimated_rows == 1200
    assert candidate.has_rows is True


def test_discovery_output_deduplicates_tables():
    detail_a = DiscoveryCandidate.model_validate({"full_name": "dbo.TableA"})
    detail_b = DiscoveryCandidate.model_validate({"full_name": "dbo.TableA"})

    output = DiscoveryOutput(
        relevant_tables=["dbo.TableA", "dbo.TableA"],
        schema_snippet="dbo.TableA: id (int)",
        candidate_views=[],
        relevant_table_details=[detail_a, detail_b],
        column_index={},
    )

    assert output.relevant_tables == ["dbo.TableA"]

