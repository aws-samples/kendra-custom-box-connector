from typing import Optional

import config


def get_ext(name: str) -> Optional[str]:
    if "." not in name:
        return
    ext = name.split(".")[-1].upper()
    return ext


def is_support_file(name: str) -> bool:
    ext = get_ext(name)
    if ext in config.SUPPORT_FILE_TYPES:
        return True
    else:
        return False


