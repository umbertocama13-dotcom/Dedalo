"""Measures matching quality on tests/fixtures/operator_queries.json and calibrates the settings.

Run from the backend/ folder, against a database loaded with database/seed.sql:

    .venv/bin/python -m scripts.evaluate_matching
    .venv/bin/python -m scripts.evaluate_matching --models intfloat/multilingual-e5-base --details

Sections:
1. v1 baseline: fuzzy matcher with threshold 0.80.
2. For every model, with and without the fuzzy score, one row per threshold:
   recall@k (an expected id among the top k), top1, no_match (unrelated queries with
   no result) and negation (negated queries that do not return the opposite symptom).
3. For the model in EMBEDDING_MODEL with the configured settings: how queries fall in the
   three answer tiers, the calibration of temperature and "none of these" score, and the
   score gaps between the first two hypotheses.
"""

import argparse
import json
import math
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.db import create_db_engine
from app.repositories import diagnostics_repository
from app.services.embeddings.embedding_cache import EmbeddingCache
from app.services.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder
from app.services.matching.base import Matcher, MatchCandidate, MatchResult
from app.services.matching.fuzzy_matcher import FuzzyMatcher
from app.services.matching.semantic_matcher import SemanticMatcher
from app.services.probability_service import relative_probabilities

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "operator_queries.json"
# e5 models were trained with these prefixes and lose accuracy without them.
E5_PREFIXES = ("query: ", "passage: ")
TEMPERATURES = (0.01, 0.02, 0.03, 0.05, 0.07, 0.10)
UNKNOWN_SCORES = (0.55, 0.60, 0.65, 0.70)

Outcome = tuple[dict[str, Any], list[MatchResult]]


def load_candidates(database: str, cases: Sequence[dict[str, Any]]) -> dict[str, list[MatchCandidate]]:
    """Loads the context candidates of every fixture query from the database.

    Args:
        database: Database name loaded with seed.sql.
        cases: Fixture queries.

    Returns:
        Candidates by query id.
    """
    engine = create_db_engine(get_settings(), database)
    try:
        with engine.connect() as connection:
            return {
                case["id"]: [
                    MatchCandidate(**row)
                    for row in diagnostics_repository.list_candidates(
                        connection, case["family_id"], case["cycle_phase_id"]
                    )
                ]
                for case in cases
            }
    finally:
        engine.dispose()


def run_queries(
    matcher: Matcher, cases: Sequence[dict[str, Any]], candidates: dict[str, list[MatchCandidate]]
) -> tuple[list[Outcome], float]:
    """Runs every query with a matcher configured with threshold 0 and no practical result limit.

    Args:
        matcher: Matcher to evaluate.
        cases: Fixture queries.
        candidates: Candidates by query id.

    Returns:
        The outcomes and the average time per query in milliseconds.
    """
    start = time.perf_counter()
    outcomes = [(case, matcher.match(case["query"], candidates[case["id"]])) for case in cases]
    return outcomes, (time.perf_counter() - start) * 1000 / len(cases)


def shown(results: list[MatchResult], threshold: float, top_k: int) -> list[MatchResult]:
    """Returns the results the operator would see."""
    return [result for result in results if result.score >= threshold][:top_k]


def rates(outcomes: Sequence[Outcome], threshold: float, top_k: int) -> dict[str, str]:
    """Computes recall@k, top1, no_match and negation at one threshold, as "hits/total"."""
    counts = {"recall": 0, "top1": 0, "no_match": 0, "negation": 0}
    totals = {"match": 0, "no_match": 0, "negation": 0}
    for case, results in outcomes:
        totals[case["kind"]] += 1
        ids = [result.candidate.diagnostic_id for result in shown(results, threshold, top_k)]
        if case["kind"] == "match":
            counts["recall"] += bool(set(case["expected"]) & set(ids))
            counts["top1"] += bool(ids) and ids[0] in case["expected"]
        elif case["kind"] == "no_match":
            counts["no_match"] += not ids
        else:
            counts["negation"] += not set(case["forbidden"]) & set(ids)
    return {
        "recall": f"{counts['recall']}/{totals['match']}",
        "top1": f"{counts['top1']}/{totals['match']}",
        "no_match": f"{counts['no_match']}/{totals['no_match']}",
        "negation": f"{counts['negation']}/{totals['negation']}",
    }


def print_threshold_table(outcomes: Sequence[Outcome], top_k: int) -> None:
    """Prints one row of rates per threshold between 0.30 and 0.90."""
    print(f"  {'threshold':>9} {'recall@' + str(top_k):>9} {'top1':>6} {'no_match':>9} {'negation':>9}")
    for step in range(13):
        threshold = round(0.30 + step * 0.05, 2)
        row = rates(outcomes, threshold, top_k)
        print(f"  {threshold:>9.2f} {row['recall']:>9} {row['top1']:>6} {row['no_match']:>9} {row['negation']:>9}")


def print_tiers(outcomes: Sequence[Outcome], settings: Settings) -> None:
    """Prints how the queries fall in the three answer tiers with the configured thresholds."""
    tiers: dict[str, dict[str, int]] = {"match": {}, "no_match": {}, "negation": {}}
    for case, results in outcomes:
        visible = shown(results, settings.semantic_recall_threshold, settings.max_candidates)
        if not visible:
            tier = "no_match"
        elif visible[0].score >= settings.semantic_match_threshold:
            tier = "high"
        else:
            tier = "low"
        tiers[case["kind"]][tier] = tiers[case["kind"]].get(tier, 0) + 1
    print(
        f"\n  tiers with recall {settings.semantic_recall_threshold} / match {settings.semantic_match_threshold} "
        "(high = hypotheses, low = uncertain hypotheses, no_match = nothing shown):"
    )
    for kind, counts in tiers.items():
        print(f"    {kind:<9} high {counts.get('high', 0):>2}  low {counts.get('low', 0):>2}  no_match {counts.get('no_match', 0):>2}")


def print_probability_calibration(outcomes: Sequence[Outcome], settings: Settings) -> None:
    """Prints the mean negative log-likelihood of the right answer for each temperature and "none of these" score.

    For a match query the right answer is its expected hypotheses; for an unrelated query
    it is "none of these". The lowest NLL gives the most faithful probabilities on the fixture.
    """
    print("\n  probability calibration: mean NLL of the right answer (lower = better, * = configured)")
    print(f"    {'T':>5} " + " ".join(f"{'none=' + format(score, '.2f'):>11}" for score in UNKNOWN_SCORES))
    for temperature in TEMPERATURES:
        cells = []
        for unknown_score in UNKNOWN_SCORES:
            nll = []
            for case, results in outcomes:
                visible = shown(results, settings.semantic_recall_threshold, settings.max_candidates)
                if case["kind"] == "negation" or not visible:
                    continue
                probabilities = relative_probabilities([*(result.score for result in visible), unknown_score], temperature)
                if case["kind"] == "match":
                    right = sum(
                        probability
                        for result, probability in zip(visible, probabilities[:-1], strict=True)
                        if result.candidate.diagnostic_id in case["expected"]
                    )
                else:
                    right = probabilities[-1]
                # A zero probability would give an infinite NLL: clamp it to a very small value.
                nll.append(-math.log(max(right, 1e-9)))
            configured = math.isclose(temperature, settings.probability_temperature) and math.isclose(
                unknown_score, settings.probability_unknown_score
            )
            cells.append(f"{sum(nll) / len(nll):>10.3f}{'*' if configured else ' '}")
        print(f"    {temperature:>5.2f} " + " ".join(cells))


def print_gaps(outcomes: Sequence[Outcome], settings: Settings) -> None:
    """Prints the score gap between the first two hypotheses with different symptoms.

    A good DISAMBIGUATION_SCORE_GAP is larger than the gaps of wrong first hypotheses
    and smaller than most gaps of right ones.
    """
    right, wrong = [], []
    for case, results in outcomes:
        visible = shown(results, settings.semantic_recall_threshold, settings.max_candidates)
        if case["kind"] != "match" or len(visible) < 2:
            continue
        first = visible[0]
        runner_up = next(
            (result for result in visible if result.candidate.symptom_description != first.candidate.symptom_description),
            None,
        )
        if runner_up is None:
            continue
        gap = round(first.score - runner_up.score, 3)
        (right if first.candidate.diagnostic_id in case["expected"] else wrong).append(gap)
    print(f"\n  gap 1st-2nd hypothesis (configured {settings.disambiguation_score_gap}):")
    print(f"    right first hypothesis: {sorted(right)}")
    print(f"    wrong first hypothesis: {sorted(wrong)}")


def print_details(outcomes: Sequence[Outcome]) -> None:
    """Prints, for every query, the best expected (or forbidden) score and the best other score."""
    for case, results in outcomes:
        wanted = set(case.get("expected") or case.get("forbidden") or [])
        good = [result.score for result in results if result.candidate.diagnostic_id in wanted]
        others = [result for result in results if result.candidate.diagnostic_id not in wanted]
        best_other = f"{others[0].score:.3f} (id {others[0].candidate.diagnostic_id})" if others else "-"
        best_good = f"{max(good):.3f}" if good else "-"
        print(f"    {case['id']} {case['kind']:<8} {best_good:>6} | other {best_other:<16} | {case['query']}")


def main() -> None:
    """Parses arguments, runs the evaluation and prints the tables."""
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", default=settings.db_test_name, help="database loaded with seed.sql")
    parser.add_argument("--models", nargs="+", default=[settings.embedding_model])
    parser.add_argument("--top-k", type=int, default=settings.max_candidates)
    parser.add_argument("--details", action="store_true", help="print the scores of every query")
    args = parser.parse_args()

    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["queries"]
    candidates = load_candidates(args.database, cases)

    baseline, _ = run_queries(FuzzyMatcher(threshold=0.0, max_results=100), cases, candidates)
    row = rates(baseline, 0.80, args.top_k)
    print(
        f"v1 baseline (fuzzy, threshold 0.80): recall@{args.top_k} {row['recall']}, top1 {row['top1']}, "
        f"no_match {row['no_match']}, negation {row['negation']}"
    )

    for model_name in args.models:
        if model_name == settings.embedding_model:
            prefixes = (settings.embedding_query_prefix, settings.embedding_document_prefix)
        else:
            prefixes = E5_PREFIXES if "e5" in model_name else ("", "")
        cache = EmbeddingCache(SentenceTransformerEmbedder(model_name, *prefixes))
        cache.warm_up([candidate.symptom_description for group in candidates.values() for candidate in group])

        for use_fuzzy in (False, True):
            matcher = SemanticMatcher(cache, threshold=0.0, max_results=100, use_fuzzy=use_fuzzy)
            outcomes, ms_per_query = run_queries(matcher, cases, candidates)
            mode = "semantic+fuzzy" if use_fuzzy else "semantic"
            print(f"\n{model_name} [{mode}] — {ms_per_query:.1f} ms/query")
            print_threshold_table(outcomes, args.top_k)
            if model_name == settings.embedding_model and use_fuzzy == settings.semantic_use_fuzzy:
                print_tiers(outcomes, settings)
                print_probability_calibration(outcomes, settings)
                print_gaps(outcomes, settings)
            if args.details:
                print_details(outcomes)


if __name__ == "__main__":
    main()
