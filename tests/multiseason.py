"""Two-season persistence proof: trophies, ageing, finances and inbox carry over.

Run: FM_DB=/tmp/season2.db python3 tests/multiseason.py
"""
import os
import sys

sys.path.insert(0, "/home/user")
sys.path.insert(0, "/home/user/tests")
os.environ.setdefault("FM_DB", "/tmp/season2.db")
import season_test

if __name__ == "__main__":
    season_test.run("RMA", seasons=2)
