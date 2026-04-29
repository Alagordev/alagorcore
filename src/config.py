import json, os

APP_NAME    = "AlagorCore"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Alagor"

GITHUB_REPO         = "Alagordev/alagorcore"
GITHUB_API_URL      = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
PAYPAL_DONATE_URL   = "https://www.paypal.com/donate?business=bu.7abeeb@gmail.com&currency_code=USD"

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".alagorcore", "settings.json")

DEFAULT_SETTINGS = {
    "theme": "dark",
    "language": "en",
    "polling_mode": "manual",
    "polling_interval": 2,
    "auto_update_check": True,
    "confirm_destructive": True,
    "paypal_url": PAYPAL_DONATE_URL,
    "github_repo": GITHUB_REPO,
}

def load_settings():
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                s = DEFAULT_SETTINGS.copy()
                s.update(data)
                return s
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
