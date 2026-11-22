"""Desktop launcher and PyInstaller entry point for HydroPower Intelligence."""

import os
import sys
import webbrowser
from pathlib import Path


def launch():
    """Launches the Streamlit application as a local desktop process."""
    project_dir = Path(__file__).resolve().parent
    app_path = project_dir / "src" / "app.py"

    if not app_path.exists():
        print(f"Error: Could not locate app entry point at {app_path}")
        sys.exit(1)

    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    import streamlit.web.cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.port=8501",
        "--server.headless=false",
        "--browser.gatherUsageStats=false"
    ]

    print("====================================================================")
    print("      HYDROPOWER INTELLIGENCE - LOCAL DESKTOP APPLICATION")
    print("====================================================================")
    print("Running locally at: http://localhost:8501")
    print("Press Ctrl+C to terminate.")

    sys.exit(stcli.main())


if __name__ == "__main__":
    launch()
