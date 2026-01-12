import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# --- 路径配置 (Path Configuration) ---
# 基准路径：trendbot 目录 (core 的上一级)
BOT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = BOT_ROOT # 兼容旧变量名

# 加载 .env
# 1. 优先加载当前目录的 .env (TrendBot 专用配置)
load_dotenv(BOT_ROOT / ".env")

# 2. 尝试加载 ../docker/.env (TrendRadar 主配置) 以实现复用
# 这样可以共享 TELEGRAM_BOT_TOKEN 等配置
DOCKER_ENV_PATH = BOT_ROOT.parent / "docker" / ".env"
if DOCKER_ENV_PATH.exists():
    load_dotenv(DOCKER_ENV_PATH)

# 输出目录：优先读取环境变量，默认为项目根目录下的 output
# 假设 TrendRadar 根目录在 trendbot 上一层
PROJECT_ROOT = BOT_ROOT.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
DB_PATH = BOT_ROOT / "trendbot.sqlite3"

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- LLM 配置 (LLM Configuration) ---
# 支持 deepseek, openai, claude, etc.
# LiteLLM 格式: provider/model_name
# 例如: deepseek/deepseek-chat, openai/gpt-4o
LLM_MODEL = os.getenv("LLM_MODEL", "")

# 优先使用标准 LLM_API_KEY，其次尝试特定厂商的 Key (兼容旧配置)
LLM_API_KEY = (
    os.getenv("LLM_API_KEY")
    or os.getenv("DEEPSEEK_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("ANTHROPIC_API_KEY")
)

LLM_API_BASE = os.getenv("LLM_API_BASE")

if not LLM_MODEL:
    logger.warning("[Config] LLM_MODEL is not set. Please configure it in .env.")
if not LLM_API_KEY:
    logger.warning("[Config] LLM_API_KEY is not set. LLM features may fail.")

# --- RSS 配置 ---
RSS_TIMEOUT = int(os.getenv("RSS_TIMEOUT", "10"))
RSS_RETRY = int(os.getenv("RSS_RETRY", "2"))
RSS_USER_AGENT = os.getenv("RSS_USER_AGENT", "Mozilla/5.0 (compatible; TrendBot/1.0)")

DAILY_BRIEF_TIME = os.getenv("DAILY_BRIEF_TIME", "09:00")  # HH:MM
TIMEZONE = os.getenv("TIMEZONE", os.getenv("DEFAULT_TZ", "Asia/Shanghai"))

# --- Bot 配置 ---
# 优先读取 BOT_TOKEN，如果没有，尝试读取 TELEGRAM_BOT_TOKEN (来自 docker/.env)
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

# --- 安全配置 ---
SECRET_KEY = os.getenv("SECRET_KEY")

# --- 打印关键配置 (Debug) ---
logger.info("[Config] BASE_DIR: %s", BASE_DIR)
logger.info("[Config] OUTPUT_DIR: %s", OUTPUT_DIR)
logger.info("[Config] LLM_MODEL: %s", LLM_MODEL)
