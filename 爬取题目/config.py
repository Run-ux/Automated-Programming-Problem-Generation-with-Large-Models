"""Central configuration for all scrapers."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

CF_OUTPUT_DIR = OUTPUT_DIR / "codeforces"
ATCODER_OUTPUT_DIR = OUTPUT_DIR / "atcoder"
LUOGU_OUTPUT_DIR = OUTPUT_DIR / "luogu"
ICPC_OUTPUT_DIR = OUTPUT_DIR / "icpc"

# ---------------------------------------------------------------------------
# Rate Limits (seconds between requests)
# ---------------------------------------------------------------------------

CF_API_RATE = 2.0        # Codeforces API: 1 request per 2 seconds
CF_HTML_RATE = 1.2       # Codeforces HTML: ~1 request per 1.2 seconds
ATCODER_RATE = 0.5       # AtCoder: 500ms between requests
LUOGU_RATE = 1.0         # Luogu: 1 second between requests
ICPC_GYM_RATE = 3.0      # Codeforces Gym (ICPC): slower to avoid Cloudflare rate-limiting

# ---------------------------------------------------------------------------
# User-Agent
# NOTE: Luogu blocks User-Agents containing "python-requests"
# ---------------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Codeforces Filters
# ---------------------------------------------------------------------------

# Contest name patterns to identify Div1 / Div2 contests
CF_DIV2_PATTERN = r"Div\.?\s*2"
CF_DIV1_PATTERN = r"Div\.?\s*1"

# Problem indices to crawl per division
CF_DIV2_INDICES = {"D", "D1", "D2", "E", "E1", "E2"}
CF_DIV1_INDICES = {"C", "C1", "C2", "D", "D1", "D2"}

# Optional: rating range filter (inclusive)
CF_MIN_RATING = 1500
CF_MAX_RATING = 3500

# ---------------------------------------------------------------------------
# AtCoder Filters
# ---------------------------------------------------------------------------

# Contest type prefixes
ATCODER_CONTEST_PREFIXES = {
    "abc": {"F", "G", "Ex"},          # ABC: F and harder
    "arc": {"C", "D", "E", "F"},      # ARC: C and harder
    "agc": None,                       # AGC: all problems (None = no filter)
}

# ---------------------------------------------------------------------------
# Luogu / NOI Filters
# ---------------------------------------------------------------------------

# Tag IDs for NOI/provincial selection on Luogu
LUOGU_NOI_TAGS = ["NOI", "省选"]
LUOGU_PROBLEM_TYPE = "P"  # Public problems

# ---------------------------------------------------------------------------
# ICPC Filters (via Codeforces Gym)
# ---------------------------------------------------------------------------

ICPC_GYM_NAME_PATTERNS = [
    r"ICPC",
    r"International Collegiate Programming Contest",
    r"World Finals",
    r"Regional",
    r"Asia.*Regional",
    r"Europe.*Regional",
    r"Latin America.*Regional",
    r"North America.*Regional",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
