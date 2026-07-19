"""
main.py
~~~~~~~~
CLI entry point for the Fantasy Basketball Optimizer pipeline.

Usage:
    python main.py [command]

Commands:
    pull        Fetch raw NBA stats → data/data.json
    rank        Score all players   → data/data_zscores.json, fantasy_rankings.csv
    roster      Filter to rosters   → data/data_myteam.json, data_matchup.json, etc.
    evaluate    Rank replacements   → data/data_top_n_replacements.json
                  --player / -p <ID>  override the drop candidate (default: config.yaml)
    predict     Daily projections   → data/daily_projections*.json
    all         Run pull → rank → roster → evaluate (excludes predict)
"""

import argparse

from app.pipeline import commands


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
        help=(
            "(evaluate only) Player ID to evaluate for dropping. "
            "Overrides drop_candidate in config.yaml."
        ),
    )

    args = parser.parse_args()

    if args.command in ("pull", "all"):
        print("\n=== RUNNING DATA PULL ===")
        commands.pull()

    if args.command in ("rank", "all"):
        print("\n=== RUNNING RANKING / Z-SCORES ===")
        commands.rank()

    if args.command in ("roster", "all"):
        print("\n=== GENERATING ROSTER STATS ===")
        commands.roster()

    if args.command in ("evaluate", "all"):
        print("\n=== EVALUATING PLAYER ===")
        commands.evaluate(drop_candidate_id=args.player)

    if args.command == "predict":
        print("\n=== RUNNING DAILY PREDICTION ===")
        commands.predict()


if __name__ == "__main__":
    main()
