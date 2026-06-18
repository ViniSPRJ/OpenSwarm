import logging
import os

from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

from swarm import create_agency
from agency_swarm.integrations.fastapi import run_fastapi


if __name__ == "__main__":
    allowed_dirs = [
        item.strip()
        for item in os.getenv("OPENSWARM_ALLOWED_LOCAL_FILE_DIRS", "./uploads").split(",")
        if item.strip()
    ]

    run_fastapi(
        agencies={
            "open-swarm": create_agency,
        },
        host=os.getenv("OPENSWARM_HOST", "0.0.0.0"),
        port=int(os.getenv("OPENSWARM_PORT", "18080")),
        enable_logging=True,
        logs_dir=os.getenv("OPENSWARM_LOGS_DIR", "activity-logs"),
        allowed_local_file_dirs=allowed_dirs,
    )
