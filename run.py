import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent / "backend"


def main():
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("ERROR: No .env file found.")
        print("Run: cp .env.example .env")
        print("Then configure the provider API keys you plan to use in the .env file.")
        sys.exit(1)

    print("Starting Papertrail API on http://localhost:8000")
    print("Start the frontend separately: cd frontend && npm run dev")
    print()

    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
        ],
        cwd=BACKEND_DIR,
    )


if __name__ == "__main__":
    main()
