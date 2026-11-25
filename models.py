"""Modelos de dominio del centro deportivo."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from .exceptions import ValidacionError


class Membresia(ABC):
    """Contrato comun para las reglas de cada plan de membresia."""

    def __init__(self, tipo: str, precio: float, vigencia: datetime):
        self.tipo = tipo
        self.precio = precio
        self.vigencia = vigencia

    def esta_vigente(self, ahora: datetime) -> bool:
        """Indica si la fecha actual no ha superado la fecha de vencimiento."""
        return ahora <= self.vigencia

    @abstractmethod
    def permite_area(self, area: str) -> bool:
        """Indica si el socio puede usar un area."""

    @abstractmethod
    def permite_entrada(self, ahora: datetime) -> bool:
        """Indica si el socio puede entrar a las instalaciones."""

    def renovar(self, ahora: datetime) -> None:
        """Agrega treinta dias desde el vencimiento o desde la fecha actual."""
        inicio = max(self.vigencia, ahora)
        self.vigencia = inicio + timedelta(days=30)


class MembresiaEstudiante(Membresia):
    """Plan economico limitado al gimnasio y al horario universitario."""

    def __init__(self, vigencia: datetime):
        super().__init__("estudiante", 300.0, vigencia)

    def permite_area(self, area: str) -> bool:
        return area.lower() == "gimnasio"

    def permite_entrada(self, ahora: datetime) -> bool:
        return ahora.weekday() < 5 and 7 <= ahora.hour < 15


class MembresiaGeneral(Membresia):
    """Plan general con acceso al gimnasio durante todo el horario."""

    def __init__(self, vigencia: datetime):
        super().__init__("general", 700.0, vigencia)

    def permite_area(self, area: str) -> bool:
        return area.lower() == "gimnasio"

    def permite_entrada(self, ahora: datetime) -> bool:
        return True


class MembresiaPremium(Membresia):
    """Plan completo con acceso al gimnasio, alberca y clases."""

    def __init__(self, vigencia: datetime):
        super().__init__("premium", 1100.0, vigencia)

    def permite_area(self, area: str) -> bool:
        return area.lower() in {"gimnasio", "alberca", "clase"}

    def permite_entrada(self, ahora: datetime) -> bool:
        return True


class Socio:
    """Persona registrada, su plan, sus reservas y sus faltas."""

    def __init__(self, socio_id: str, nombre: str, apellido: str,
                 es_alumno: bool = False):
        self.socio_id = socio_id
        self.nombre = nombre
        self.apellido = apellido
        self.es_alumno = es_alumno
        self.membresia: Optional[Membresia] = None
        self.reservas: list["Reserva"] = []
        self._faltas_mes: dict[str, int] = {}
        self.reserva_bloqueada_hasta: Optional[datetime] = None

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()

    def contar_faltas(self, mes: str) -> int:
        return self._faltas_mes.get(mes, 0)

    def agregar_falta(self, ahora: datetime) -> None:
        mes = ahora.strftime("%Y-%m")
        total = self.contar_faltas(mes) + 1
        self._faltas_mes[mes] = total
        if total >= 3:
            self.reserva_bloqueada_hasta = ahora + timedelta(days=7)


class Visitante:
    """Persona sin membresia que compra un pase diario al gimnasio."""

    def __init__(self, visitante_id: str, nombre: str, fecha: datetime):
        self.visitante_id = visitante_id
        self.nombre = nombre
        self.fecha = fecha
        self.precio = 120.0


class Clase:
    """Actividad grupal que controla su horario, cupo y reservas."""

    def __init__(self, clase_id: str, nombre: str, instructor: str,
                 horario: datetime, cupo: int):
        self.clase_id = clase_id
        self.nombre = nombre
        self.instructor = instructor
        self.horario = horario
        self.cupo = cupo
        self.reservas: list["Reserva"] = []

    @property
    def lugares_disponibles(self) -> int:
        """Calcula el cupo libre contando reservas activas y asistencias."""
        activas = [r for r in self.reservas
                   if r.estado in {"reservada", "asistio"}]
        return max(0, self.cupo - len(activas))

    def reservar(self, reserva: "Reserva", ahora: datetime) -> None:
        """Valida las reglas de la clase y agrega la reserva si es posible."""
        if reserva.socio.reserva_bloqueada_hasta and ahora < reserva.socio.reserva_bloqueada_hasta:
            raise ValidacionError("El socio tiene suspendida la reserva por siete dias.")
        anticipacion = self.horario - ahora
        if anticipacion <= timedelta(0):
            raise ValidacionError("La clase ya inicio.")
        if anticipacion > timedelta(hours=48):
            raise ValidacionError("Solo se puede reservar hasta 48 horas antes.")
        if self.lugares_disponibles <= 0:
            raise ValidacionError("La clase no tiene lugares disponibles.")
        if any(r.socio.socio_id == reserva.socio.socio_id and r.estado == "reservada"
               for r in self.reservas):
            raise ValidacionError("El socio ya tiene una reserva activa para esta clase.")
        self.reservas.append(reserva)
        reserva.socio.reservas.append(reserva)

    def cancelar_reserva(self, reserva: "Reserva", ahora: datetime) -> None:
        """Actualiza el estado cuando se cancela con suficiente anticipacion."""
        if self.horario - ahora < timedelta(hours=2):
            raise ValidacionError("La reserva solo se puede cancelar hasta 2 horas antes.")
        reserva.estado = "cancelada"

    def pasar_lista(self, socio_id: str, ahora: datetime, asistio: bool) -> None:
        """Marca asistencia o falta y actualiza la cuenta mensual del socio."""
        reserva = next((r for r in self.reservas
                        if r.socio.socio_id == socio_id and r.estado == "reservada"), None)
        if reserva is None:
            raise ValidacionError("No existe una reserva activa para ese socio.")
        reserva.estado = "asistio" if asistio else "falto"
        if not asistio:
            reserva.socio.agregar_falta(ahora)


class Reserva:
    """Relacion entre un socio y una clase con estado de asistencia."""

    def __init__(self, folio: str, socio: Socio, clase: Clase,
                 creada: datetime):
        self.folio = folio
        self.socio = socio
        self.clase = clase
        self.creada = creada
        self.estado = "reservada"


class RegistroAcceso:
    """Movimiento de entrada o salida guardado por el sistema."""

    def __init__(self, registro_id: str, persona_id: str, tipo_persona: str,
                 accion: str, area: str, momento: datetime):
        self.registro_id = registro_id
        self.persona_id = persona_id
        self.tipo_persona = tipo_persona
        self.accion = accion
        self.area = area
        self.momento = momento
