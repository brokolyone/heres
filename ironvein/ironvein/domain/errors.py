class GameError(Exception):
    """Ожидаемая игровая ошибка: текст показывается игроку как есть."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(GameError):
    pass


class Forbidden(GameError):
    pass


class AlreadyDone(GameError):
    """Повтор уже выполненной операции (идемпотентность)."""
