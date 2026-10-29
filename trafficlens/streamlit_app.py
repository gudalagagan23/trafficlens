"""Entry point for Streamlit Community Cloud. It simply runs the real dashboard."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "dashboard" / "app.py"), run_name="__main__")
