class CentroDeportivoError(Exception):
    """Error controlado del sistema."""


class ValidacionError(CentroDeportivoError):
    """Datos o una operacion no cumplen las reglas."""


class PersistenciaError(CentroDeportivoError):
    """No fue posible leer o guardar la informacion."""
