from evaluation.metrics import leaked, mcnemar_exact, wilson
from evaluation.rubric import krippendorff_alpha_interval
from grievance_agent.store import mysql_schema_sql


def test_alpha_perfect_and_disagreement():
    assert krippendorff_alpha_interval([[5, 5], [3, 3], [1, 1]]) == 1.0
    assert krippendorff_alpha_interval([[1, 5], [5, 1], [1, 5]]) < 0


def test_wilson_and_mcnemar():
    lo, hi = wilson(38, 40)
    assert 0.8 < lo < 0.95 < hi <= 1.0
    assert mcnemar_exact(0, 0) == 1.0 and mcnemar_exact(10, 0) < 0.01


def test_leak_matching_digits():
    assert leaked("98765 43210", "phone 9876543210 stored")
    assert not leaked("98765 43210", "phone [PHONE] stored")


def test_mysql_ddl_renders():
    ddl = mysql_schema_sql()
    assert "CREATE TABLE cases" in ddl and "ENGINE=InnoDB" in ddl and "JSON" in ddl
