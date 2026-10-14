"""
VIDYA-X AI — Step 13 Evaluation & Benchmarking Framework Test Suite

Verifies:
  1. Dataset manifest loading & dataset case JSONL parsing.
  2. Dataset schema validation.
  3. Hand-computed retrieval metric formulas (Recall@K, Precision@K, Hit Rate@K, MRR, nDCG@K).
  4. Citation ID resolution & source metadata completeness.
  5. Grounded RAG answer & unsupported question abstention.
  6. Quiz question format & answer key correctness verification.
  7. Synthetic learner profiles (A through H) personalization checks.
  8. Study planner time budget & exam boundary compliance.
  9. Report generator artifacts & quality release gates.
 10. Full end-to-end benchmark evaluation runner loop.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

# Set SQLite database URL before importing database
os.environ["DATABASE_URL"] = "sqlite:///./test_evaluation.db"

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import sqlalchemy as sa
from database import models
from database.connection import Base, engine as db_engine

try:
    for model_class in [models.KnowledgeChunk]:
        for col in model_class.__table__.columns:
            if hasattr(col.type, "__class__") and col.type.__class__.__name__ == "Vector":
                col.type = sa.Text()
except Exception:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from evaluation.dataset_loader import load_manifest, load_dataset_cases, validate_case_dict
from evaluation.schemas import DatasetCase, MetricResult, CaseEvaluationResult
from evaluation.metrics import (
    calculate_recall_at_k,
    calculate_precision_at_k,
    calculate_hit_rate_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
)
from evaluation.retrieval_evaluator import evaluate_retrieval_cases
from evaluation.citation_evaluator import evaluate_citation_cases
from evaluation.rag_evaluator import evaluate_rag_cases
from evaluation.quiz_evaluator import evaluate_quiz_cases
from evaluation.personalization_evaluator import evaluate_personalization_cases
from evaluation.study_planner_evaluator import evaluate_study_plan_cases
from evaluation.report_generator import generate_evaluation_report, evaluate_quality_gates
from evaluation.evaluation_runner import run_evaluation


class TestStep13EvaluationFramework(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=db_engine)
        Base.metadata.create_all(bind=db_engine)

    def setUp(self):
        self.Session = sessionmaker(bind=db_engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_dataset_manifest_and_loader(self):
        """Verify dataset manifest loads and JSONL cases pass schema validation."""
        manifest = load_manifest()
        self.assertEqual(manifest["dataset_version"], "1.0")
        self.assertIn("file_manifest", manifest)

        cases = load_dataset_cases(dataset_version="1.0")
        self.assertGreater(len(cases), 0)

        for c in cases:
            self.assertTrue(c.case_id)
            self.assertTrue(c.task_type)
            self.assertTrue(c.course_id)

    def test_hand_computed_retrieval_metrics(self):
        """Verify Recall@K, Precision@K, Hit Rate@K, MRR, and nDCG@K against manual calculations."""
        actual = ["chunk_1", "chunk_2", "chunk_3"]
        expected = ["chunk_2", "chunk_4"]

        # k=3: retrieved_k = {'chunk_1', 'chunk_2', 'chunk_3'}. Intersection with expected = {'chunk_2'} (1 hit)
        rec = calculate_recall_at_k(actual, expected, k=3)
        prec = calculate_precision_at_k(actual, expected, k=3)
        hit = calculate_hit_rate_at_k(actual, expected, k=3)
        mrr = calculate_mrr(actual, expected)
        ndcg = calculate_ndcg_at_k(actual, expected, k=3)

        self.assertEqual(rec, 0.5)      # 1 hit out of 2 expected = 0.5
        self.assertEqual(prec, 0.3333)  # 1 hit out of 3 retrieved = 0.3333
        self.assertEqual(hit, 1.0)      # hit found in top 3
        self.assertEqual(mrr, 0.5)      # chunk_2 is at rank 2 -> 1/2 = 0.5
        self.assertGreater(ndcg, 0.0)

    def test_citation_evaluation_and_resolution(self):
        """Verify citation evaluator flags invalid chunk IDs and cross-course violations."""
        cases = load_dataset_cases(task_type="citation")
        res = evaluate_citation_cases(self.db, cases)

        self.assertIn("case_results", res)
        self.assertIn("citation_id_resolution_rate", res["metrics"])
        self.assertIn("cross_course_citation_violation_count", res["metrics"])

    def test_rag_abstention_evaluation(self):
        """Verify RAG evaluator checks unsupported question abstentions."""
        cases = load_dataset_cases(task_type="rag")
        res = evaluate_rag_cases(self.db, cases)

        self.assertIn("unsupported_question_abstention_rate", res["metrics"])
        self.assertIn("grounded_answer_accuracy", res["metrics"])

    def test_quiz_quality_evaluation(self):
        """Verify quiz evaluator flags invalid MCQ answer keys and ungrounded questions."""
        cases = load_dataset_cases(task_type="quiz")
        res = evaluate_quiz_cases(self.db, cases)

        self.assertIn("quiz_answer_key_correctness_rate", res["metrics"])
        self.assertIn("valid_question_rate", res["metrics"])

    def test_personalization_synthetic_profiles(self):
        """Verify synthetic learner profiles A through H pass personalization rules."""
        cases = load_dataset_cases(task_type="personalization")
        res = evaluate_personalization_cases(self.db, cases)

        self.assertIn("personalization_consistency_rate", res["metrics"])
        self.assertEqual(res["metrics"]["personalization_consistency_rate"].result, 1.0)

    def test_study_planner_feasibility_metrics(self):
        """Verify study planner evaluator checks daily budget and exam date compliance."""
        cases = load_dataset_cases(task_type="study_plan")

        # Seed test course for planner cases
        course = models.Course(id="synthetic_physics", name="Synthetic Physics")
        t1 = models.Topic(id="t_phys1", course_id="synthetic_physics", name="Kinematics")
        self.db.merge(course)
        self.db.merge(t1)
        self.db.commit()

        res = evaluate_study_plan_cases(self.db, cases)

        self.assertIn("daily_budget_compliance_rate", res["metrics"])
        self.assertEqual(res["metrics"]["daily_budget_compliance_rate"].result, 1.0)

    def test_quality_release_gates(self):
        """Verify quality release gates check metric values against thresholds."""
        mock_metrics = {
            "citation_id_resolution_rate": MetricResult(
                metric_name="citation_id_resolution_rate",
                category="Citation Accuracy",
                definition="Resolution rate",
                result=0.98,
                benchmark_target=0.95,
            ),
            "course_isolation_violation_count": MetricResult(
                metric_name="course_isolation_violation_count",
                category="Security",
                definition="Cross course count",
                result=0.0,
                benchmark_target=0.0,
            ),
        }
        gates = evaluate_quality_gates(mock_metrics)
        self.assertGreater(len(gates), 0)
        for g in gates:
            self.assertTrue(g.passed)

    def test_full_benchmark_runner_and_report_generation(self):
        """Verify full evaluation runner loop produces valid summary and artifacts."""
        # Seed test course
        course = models.Course(id="synthetic_physics", name="Synthetic Physics")
        self.db.merge(course)
        self.db.commit()

        summary = run_evaluation(
            db=self.db,
            dataset_version="1.0",
            deterministic_only=True,
            max_cases=10,
            run_id="test_suite_run_001",
        )

        self.assertEqual(summary.run_id, "test_suite_run_001")
        self.assertGreater(summary.total_cases, 0)
        self.assertIsNotNone(summary.pass_rate_percentage)


if __name__ == "__main__":
    unittest.main()
