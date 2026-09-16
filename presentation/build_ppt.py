"""Sync the current user-edited deck's navigation; never recreate its slide order."""
import runpy,sys
from pathlib import Path
root=Path(__file__).resolve().parent/'remake'
sys.path.insert(0,str(root))
runpy.run_path(str(root/'sync_current_deck.py'),run_name='__main__')
