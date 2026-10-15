import pathlib
import sys

APP_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
