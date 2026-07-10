"""
main.py
~~~~~~~~
CLI entry point for the Fantasy Basketball Optimizer pipeline.

Usage:
    python main.py [command]

Commands:
    pull        Fetch raw NBA stats → data/data.json
    rank        Calculate z-scores  → data/data_zscores.json, fantasy_rankings.csv
    roster      Filter roster data  → data/data_myteam.json, data_matchup.json, etc.
    evaluate    Evaluate drop trade → data/data_top_n_replacements.json
                  --player / -p <ID>  override the drop candidate (default: config.yaml)
    predict     Daily projections   → data/daily_projections*.json
    all         Run pull → rank → roster → evaluate in sequence (excludes predict)
"""

import argparse

from app.services import (
    data_ingestion_service,
    ranking_service,
    roster_service,
    evaluation_service,
    prediction_service,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fantasy Basketball Optimizer — pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["pull", "rank", "roster", "evaluate", "predict", "all"],
        help="Pipeline step to execute (default: all)",
    )
    parser.add_argument(
        "--player", "-p",
        type=int,
        default=None,
        metavar="PLAYER_ID",
        help="(evaluate only) Player ID to evaluate for dropping. "
             "Overrides the drop_candidate value in config.yaml.",
    )

    args = parser.parse_args()

    if args.command in ("pull", "all"):
        print("\n=== RUNNING DATA PULL ===")
        data_ingestion_service.run()

    if args.command in ("rank", "all"):
        print("\n=== RUNNING RANKING / Z-SCORES ===")
        ranking_service.run()

    if args.command in ("roster", "all"):
        print("\n=== GENERATING ROSTER STATS ===")
        roster_service.run()

    if args.command in ("evaluate", "all"):
        print("\n=== EVALUATING PLAYER ===")
        evaluation_service.run(drop_candidate_id=args.player)

    if args.command == "predict":
        # 'predict' is intentionally excluded from 'all' — it's a daily-only task.
        print("\n=== RUNNING DAILY PREDICTION ===")
        prediction_service.run()


if __name__ == "__main__":
    main()
