import unicodedata


def fold(s: str) -> str:
    """Bo dau tieng Viet va ha chu thuong ('Đà Nẵng' -> 'da nang').

    Rieng đ/Đ khong phai ky tu 'co dau' theo Unicode (khong tach duoc bang NFD) nen phai doi tay."""
    s = unicodedata.normalize("NFD", s).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
