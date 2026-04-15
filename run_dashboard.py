"""Convenience launcher for the Streamlit dashboard.

Equivalent to:
    streamlit run dashboard.py --server.port 8501
"""
import sys
from streamlit.web import cli as stcli


if __name__ == "__main__":
    sys.argv = [
        "streamlit", "run", "dashboard.py",
        "--server.port", "8501",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    sys.exit(stcli.main())
