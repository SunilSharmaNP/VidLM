from sys import exit
# `config.py` is the new Python configuration source. Importing it makes
# the user's settings available as module attributes. The defensive loader
# below then pushes every UPPERCASE non-empty constant into os.environ so
# the rest of this script (and the bot) keeps using `environ.get(...)`
# exactly as before -- regardless of whether the user supplied the full
# template `config.py` (with built-in helpers) or a minimal hand-written
# / Colab-generated one.
import config as _bot_config  # noqa: F401  (side-effect import)
from dotenv import load_dotenv, dotenv_values
from logging import (
    FileHandler,
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
    getLogger,
    ERROR,
)
from os import path, environ, remove


def _push_config_to_environ(mod):
    """Push every UPPERCASE, non-empty, non-callable attr of *mod* to os.environ.

    Skips empty strings / None so that downstream `environ.get(KEY, default)`
    calls fall back to the in-code default instead of crashing on int('')."""
    for _k in dir(mod):
        if not _k.isupper() or _k.startswith("_"):
            continue
        _v = getattr(mod, _k)
        if callable(_v) or _v is None:
            continue
        _t = str(_v)
        if _t == "":
            continue
        environ[_k] = _t


def _config_settings_dict():
    """Snapshot all UPPERCASE constants of the user `config.py` to a dict.

    Falls back to walking module attrs when the user's `config.py` does not
    define `settings_to_dict()` (typical for minimal Colab-generated files)."""
    fn = getattr(_bot_config, "settings_to_dict", None)
    if callable(fn):
        return fn()
    out = {}
    for _k in dir(_bot_config):
        if not _k.isupper() or _k.startswith("_"):
            continue
        _v = getattr(_bot_config, _k)
        if callable(_v):
            continue
        out[_k] = "" if _v is None else str(_v)
    return out


_push_config_to_environ(_bot_config)
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from subprocess import run as srun

getLogger("pymongo").setLevel(ERROR)

var_list = ['BOT_TOKEN', 'TELEGRAM_API', 'TELEGRAM_HASH', 'OWNER_ID', 'DATABASE_URL', 'BASE_URL', 'UPSTREAM_REPO', 'UPSTREAM_BRANCH']

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

# Optional legacy fallback: if `config.env` is still around, load it on top
# of the values that `config.py` already populated. New deployments only need
# `config.py`.
if path.exists("config.env"):
    load_dotenv("config.env", override=True)

try:
    if bool(environ.get("_____REMOVE_THIS_LINE_____")):
        log_error("The README.md file there to be read! Exiting now!")
        exit(1)
except:
    pass

BOT_TOKEN = environ.get("BOT_TOKEN", "")
if len(BOT_TOKEN) == 0:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

BOT_ID = BOT_TOKEN.split(":", 1)[0]

DATABASE_URL = environ.get("DATABASE_URL", "")
if len(DATABASE_URL) == 0:
    DATABASE_URL = None

if DATABASE_URL is not None:
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn.mltb
        old_config = db.settings.deployConfig.find_one({"_id": BOT_ID})
        config_dict = db.settings.config.find_one({"_id": BOT_ID})
        if old_config is not None:
            del old_config["_id"]
        # Compare against the active deploy config. Use config.env's values
        # when that file exists (legacy installs), otherwise pull the snapshot
        # from config.py.
        if path.exists("config.env"):
            _active_deploy_config = dict(dotenv_values("config.env"))
        else:
            _active_deploy_config = _config_settings_dict()
        if (
            old_config is not None
            and old_config == _active_deploy_config
            or old_config is None
        ) and config_dict is not None:
            environ["UPSTREAM_REPO"] = config_dict["UPSTREAM_REPO"]
            environ["UPSTREAM_BRANCH"] = config_dict["UPSTREAM_BRANCH"]
        conn.close()
    except Exception as e:
        log_error(f"Database ERROR: {e}")

UPSTREAM_REPO = environ.get("UPSTREAM_REPO", "")
if len(UPSTREAM_REPO) == 0:
    UPSTREAM_REPO = None

UPSTREAM_BRANCH = environ.get("UPSTREAM_BRANCH", "hk")
if len(UPSTREAM_BRANCH) == 0:
    UPSTREAM_BRANCH = "hk"

if UPSTREAM_REPO is not None:
    if path.exists(".git"):
        srun(["rm", "-rf", ".git"])

    # ---- IMPORTANT ----
    # `git reset --hard origin/{branch}` mirrors the upstream tree exactly.
    # If the upstream repo tracks a `config.py` (with empty placeholder
    # values) it will OVERWRITE the user's filled-in `config.py`, wiping
    # BOT_TOKEN and crashing the bot. Working repos like SilentDemonSD/WZML-X
    # avoid this by listing config.py in their .gitignore so the upstream
    # tree never contains it. To stay compatible with upstream repos that
    # DO track a template `config.py` (such as fixvid:hk), back the file up
    # before the reset and restore it after.
    from shutil import copy2 as _copy2
    _CONFIG_BACKUP = "/tmp/_vidlm_user_config.py"
    _user_cfg_saved = False
    if path.exists("config.py"):
        try:
            _copy2("config.py", _CONFIG_BACKUP)
            _user_cfg_saved = True
            log_info("User config.py backed up before upstream pull")
        except Exception as _e:
            log_error(f"Could not back up config.py: {_e}")

    update = srun(
        [
            f"git init -q \
                     && git config --global user.email e.anastayyar@gmail.com \
                     && git config --global user.name mltb \
                     && git add . \
                     && git commit -sm update -q \
                     && git remote add origin {UPSTREAM_REPO} \
                     && git fetch origin -q \
                     && git reset --hard origin/{UPSTREAM_BRANCH} -q"
        ],
        shell=True,
    )

    if update.returncode == 0:
        log_info("Successfully updated with latest commit from UPSTREAM_REPO")
    else:
        log_error(
            "Something went wrong while updating, check UPSTREAM_REPO if valid or not!"
        )

    # Restore the user's filled config.py on top of whatever the upstream
    # template provided. This makes the next `python3 -m bot` find the real
    # BOT_TOKEN / TELEGRAM_API / etc. from the user's Colab-generated file.
    if _user_cfg_saved and path.exists(_CONFIG_BACKUP):
        try:
            _copy2(_CONFIG_BACKUP, "config.py")
            log_info("User config.py restored after upstream pull")
        except Exception as _e:
            log_error(f"Could not restore config.py: {_e}")
