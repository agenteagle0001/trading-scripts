#!/usr/bin/env python3
"""
Retrain SPY ML model weekly.
Pulls fresh data, retrains, commits to GitHub.
"""
import sys
sys.path.insert(0, '/home/colton/.openclaw/workspace/trading')
from spy_ml_model import train, MODEL_PATH
import subprocess

def main():
    print("=== SPY Model Retrain ===")
    result = train()
    
    if result:
        print(f"Model trained: {result['n_samples']} samples, CV accuracy: {result['cv_accuracy']:.3f}")
        
        # Git backup
        try:
            subprocess.run(["git", "add", MODEL_PATH], check=True, cwd="/home/colton/.openclaw/workspace")
            result_git = subprocess.run(
                ["git", "commit", "-m", f"Retrain SPY model: {result['n_samples']} samples, CV acc {result['cv_accuracy']:.3f}"],
                capture_output=True, text=True, cwd="/home/colton/.openclaw/workspace"
            )
            if result_git.returncode == 0:
                print("Git commit successful")
                push = subprocess.run(["git", "push"], capture_output=True, text=True, cwd="/home/colton/.openclaw/workspace")
                if push.returncode == 0:
                    print("Git push successful")
                else:
                    print(f"Git push failed: {push.stderr}")
            else:
                print(f"Git commit: {result_git.stdout} {result_git.stderr}")
        except Exception as e:
            print(f"Git backup failed: {e}")
    else:
        print("Training failed")

if __name__ == "__main__":
    main()
