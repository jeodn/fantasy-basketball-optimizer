import argparse
from scripts import data_pull, z_scores, generate_roster, evaluate_player

def main():
    parser = argparse.ArgumentParser(description="Fantasy Basketball Optimizer Orchestrator")
    parser.add_argument('command', nargs='?', default='all', choices=['pull', 'rank', 'roster', 'evaluate', 'all'], help="The command to run (default: all)")
    
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
        
if __name__ == "__main__":
    main()
