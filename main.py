import argparse
from scripts import data_pull, z_scores, generate_roster, evaluate_player, predict_daily

def main():
    parser = argparse.ArgumentParser(description="Fantasy Basketball Optimizer Orchestrator")
    parser.add_argument('command', nargs='?', default='all', choices=['pull', 'rank', 'roster', 'evaluate', 'predict', 'all'], help="The command to run (default: all)")
    
    args = parser.parse_args()
    
    if args.command == 'pull' or args.command == 'all':
        print("\n=== RUNNING DATA PULL ===")
        data_pull.main()
        
    if args.command == 'rank' or args.command == 'all':
        print("\n=== RUNNING RANKING/Z-SCORES ===")
        z_scores.main()
        
    if args.command == 'roster' or args.command == 'all':
        print("\n=== GENERATING ROSTER STATS ===")
        generate_roster.main()
        
    if args.command == 'evaluate' or args.command == 'all':
        print("\n=== EVALUATING PLAYER ===")
        evaluate_player.evaluate()
        
    if args.command == 'predict':
        print("\n=== RUNNING DAILY PREDICTION ===")
        # Note: 'all' does NOT include predict by default as it is a specific daily task, not part of the build pipeline.
        predict_daily.calculate_daily_projections()
        
if __name__ == "__main__":
    main()
