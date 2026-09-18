"""Rebuild the current plain-language deck; export/verify with verify_readable.ps1."""
import runpy,sys
from pathlib import Path
root=Path(__file__).resolve().parent/'remake'
sys.path.insert(0,str(root))
runpy.run_path(str(root/'build_readable_deck.py'),run_name='__main__')
