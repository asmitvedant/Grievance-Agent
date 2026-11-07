import os
import sys
from pathlib import Path

# Tests never need a model server or downloads: use the offline stand-ins.
os.environ.update(LLM_BACKEND="mock", EMBED_BACKEND="hashing", NLI_BACKEND="lexical", DATABASE_URL="sqlite://",
                  USE_LLM_URGENCY_JUDGE="1", REVIEWER_PASSWORD="test-pass")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from grievance_agent.config import reload_settings  # noqa: E402

reload_settings()


@pytest.fixture
def agent():
    from grievance_agent.harness import GrievanceAgent
    return GrievanceAgent()
