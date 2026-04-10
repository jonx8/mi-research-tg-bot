class BotException(Exception):
    """Базовое исключение бота"""
    pass


class DatabaseError(BotException):
    """Ошибка базы данных"""
    pass


class UserNotFoundError(BotException):
    """Пользователь не найден"""
    pass


class TechniqueNotFoundError(BotException):
    """Техника не найдена"""
    pass


class ValidationError(BotException):
    """Ошибка валидации данных"""
    pass