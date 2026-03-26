import re
import configparser
from pathlib import Path


class Config:
    def __init__(self, config_path: str | Path = "config.ini"):
        config = configparser.ConfigParser()
        config.read(Path(config_path))

        flask_section = config["Flask"] if "Flask" in config else {}
        self.flask_run_port = int(
            flask_section.get("flask_run_port", 5000)
        )
        self.flask_secret_key = str(
            flask_section.get("flask_secret_key", "dev-unsafe-secret-key-change-me")
        )

        self.scanner_poll_interval = parse_interval(flask_section.get("scanner_poll_interval", "5s"), to="ms")
        self.bg_client_idle_timeout = parse_interval(flask_section.get("bg_client_idle_timeout", "1m"), to="s")
        self.scanner_interval_seconds = parse_interval(flask_section.get("scanner_interval_seconds", "1m"), to="s")

        self.setups_dir = Path(flask_section.get("setups_dir", "setups"))

        ibkr_section = config["IBKR"] if "IBKR" in config else {}

        self.ibkr_live_port = int(
            ibkr_section.get("api_live_port", 7496)
        )

        self.ibkr_paper_port = int(
            ibkr_section.get("api_paper_port", 7497)
        )

        self.ibkr_preferred_env = str(
            ibkr_section.get("api_mode", "PAPER")
        )

        self.muted_ibapi_errors = ["version does not support", "data farm connection", "EId with tickerId"]

        self.enable_contract_cache = ibkr_section.get(
            "enable_contract_cache", "true"
        ).lower() in ("1", "true", "yes", "on")

        self.cache_path = Path(
            ibkr_section.get("cache_path", "ibkr_cache.json")
        )

        self.contract_cache_ttl_sec = int(
            ibkr_section.get("contract_cache_ttl_sec", 300)
        )

        self.contract_lookup_timeout_sec = int(
            ibkr_section.get("contract_lookup_timeout_sec", 10)
        )
        self.contract_lookup_poll_sec = float(
            ibkr_section.get("contract_lookup_poll_sec", 0.1)
        )
        self.contract_lookup_max_attempts = int(
            ibkr_section.get("contract_lookup_max_attempts", 2)
        )

        self.history_lookup_timeout_sec = int(
            ibkr_section.get("history_lookup_timeout_sec", 30)
        )
        self.history_lookup_poll_sec = float(
            ibkr_section.get("history_lookup_poll_sec", 0.1)
        )

        self.movers_timeout_sec = int(
            ibkr_section.get("movers_timeout_sec", 30)
        )

        self.location_code = str(
            ibkr_section.get("location_code", "STK.US")
        )

        self.scale_volume_metrics = ibkr_section.getboolean(
            "scale_volume_metrics", True
        )
    # changed to true 3/9/2026 testing
        self.force_min_volume = ibkr_section.getboolean(
            "force_min_volume", True
        )
#change FALSE to true 3/9/2026 testing
        self.cache_garbage_collection = ibkr_section.getboolean(
            "cache_garbage_collection", True
        )


def parse_interval(value: str, *, to: str = "s") -> int:
    """
    Parse duration string like: 15s, 2m, 1h, 1500ms

    to = "s"  -> return seconds (int)
    to = "ms" -> return milliseconds (int)
    """
    if not value:
        raise ValueError("Empty interval value")

    value = value.strip().lower()

    m = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m|h)", value)
    if not m:
        raise ValueError(f"Invalid interval format: {value}")

    number = float(m.group(1))
    unit = m.group(2)

    multipliers = {
        "ms": 0.001,
        "s": 1,
        "m": 60,
        "h": 3600,
    }

    seconds = number * multipliers[unit]

    if to == "s":
        return int(seconds)
    elif to == "ms":
        return int(seconds * 1000)
    else:
        raise ValueError("to must be 's' or 'ms'")
