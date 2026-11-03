# Временный файл для доказательства маршрутизации Mypy (Issue #464).
# Будет удален после проверки.

def prove_mypy_catches_errors() -> int:
    # Намеренная ошибка типов: возвращаем str вместо int
    return "this is a string, not an int"
