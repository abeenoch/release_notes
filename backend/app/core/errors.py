
class AppError(Exception):
    """Base application error."""
    status_code: int = 500
    detail: str = "Internal server error"


class NotFoundError(AppError):
    status_code = 404

    def __init__(self, entity: str = "Resource") -> None:
        self.detail = f"{entity} not found"


class ConflictError(AppError):
    status_code = 409

    def __init__(self, detail: str = "Resource already exists") -> None:
        self.detail = detail