import os


def getenv(name: str, default: str = "") -> str:
    """Doc bien moi truong ARGUS_<name>; van nhan ten cu AGENT_<name> de khong lam hong cau hinh da co."""
    return os.environ.get(f"ARGUS_{name}") or os.environ.get(f"AGENT_{name}") or default
