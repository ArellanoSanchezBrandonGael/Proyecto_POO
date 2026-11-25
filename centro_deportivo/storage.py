"""Carga y persistencia de la informacion."""

import csv
import json
from datetime import datetime
from pathlib import Path
from threading import RLock

from .exceptions import PersistenciaError

DATE_FORMAT = "%Y-%m-%d %H:%M"


class JsonRepository:
    """Repositorio JSON con acceso protegido por lock."""

    def __init__(self, ruta: Path):
        """Recibe la ubicacion donde se conserva el estado de la aplicacion."""
        self.ruta = ruta
        self.lock = RLock()

    def cargar(self) -> dict:
        """Lee el JSON; un archivo aun inexistente representa un estado vacio."""
        if not self.ruta.exists():
            return {}
        try:
            with self.lock:
                with self.ruta.open("r", encoding="utf-8") as archivo:
                 datos = json.load(archivo)
                 if not isinstance(datos, dict):
                    raise PersistenciaError("El archivo JSON tiene una estructura invalida.")
                return datos
        except (json.JSONDecodeError, OSError, UnicodeError) as exc:
            raise PersistenciaError(f"No se pudo cargar {self.ruta}: {exc}")

    def guardar(self, datos: dict) -> None:
        """Escribe primero un temporal y despues sustituye el archivo anterior."""
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.ruta.with_suffix(".tmp")
            with self.lock:
                with temporal.open("w", encoding="utf-8") as archivo:
                    json.dump(datos, archivo, ensure_ascii=False, indent=2)
                temporal.replace(self.ruta)
        except OSError as exc:
            raise PersistenciaError(f"No se pudo guardar {self.ruta}: {exc}")


def parse_datetime(texto: str) -> datetime:
    """Convierte una fecha del formato acordado a un objeto datetime."""
    try:
        return datetime.strptime(texto.strip(), DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(f"Fecha invalida '{texto}'. Use YYYY-MM-DD HH:MM.") from exc


def dt_to_text(valor: datetime) -> str:
    """Convierte una fecha a texto para guardarla en JSON."""
    return valor.strftime(DATE_FORMAT)


def leer_alumnos(ruta: Path) -> tuple[list[dict], list[str]]:
    """Lee el CSV, devuelve filas completas y explica las filas rechazadas."""
    validos: list[dict] = []
    errores: list[str] = []
    try:
        with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            if not lector.fieldnames:
                errores.append("El CSV de alumnos esta vacio o no tiene encabezado.")
            else:
                faltantes = {"id", "nombre", "apellido"} - set(lector.fieldnames)
                if faltantes:
                    columnas = ", ".join(sorted(faltantes))
                    errores.append(
                        f"Faltan columnas obligatorias en el CSV de alumnos: {columnas}.")
                else:
                    filas = 0
                    for numero, fila in enumerate(lector, start=2):
                        filas += 1
                        id_alumno = (fila.get("id") or "").strip()
                        nombre = (fila.get("nombre") or "").strip()
                        apellido = (fila.get("apellido") or "").strip()
                        if not id_alumno or not nombre or not apellido:
                            errores.append(
                                f"Fila {numero}: id, nombre y apellido son obligatorios.")
                        else:
                            validos.append({
                                "id": id_alumno, "nombre": nombre,
                                "apellido": apellido})
                    if filas == 0:
                        errores.append("El CSV de alumnos no contiene registros.")
    except FileNotFoundError:
        errores.append(f"Archivo no encontrado: {ruta}")
    except (OSError, csv.Error, UnicodeError) as exc:
        errores.append(f"No se pudo leer {ruta}: {exc}")
    return validos, errores


def leer_clases(ruta: Path) -> tuple[list[dict], list[str]]:
    """Valida fechas, cupos y campos obligatorios de cada clase del CSV."""
    validos: list[dict] = []
    errores: list[str] = []
    try:
        with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            if not lector.fieldnames:
                errores.append("El CSV de clases esta vacio o no tiene encabezado.")
            else:
                requeridas = {"id", "nombre", "instructor", "horario", "cupo"}
                faltantes = requeridas - set(lector.fieldnames)
                if faltantes:
                    columnas = ", ".join(sorted(faltantes))
                    errores.append(
                        f"Faltan columnas obligatorias en el CSV de clases: {columnas}.")
                else:
                    filas = 0
                    for numero, fila in enumerate(lector, start=2):
                        filas += 1
                        try:
                            clase_id = (fila.get("id") or "").strip()
                            nombre = (fila.get("nombre") or "").strip()
                            instructor = (fila.get("instructor") or "").strip()
                            horario = parse_datetime(fila.get("horario") or "")
                            cupo = int((fila.get("cupo") or "").strip())
                            if not clase_id or not nombre or not instructor:
                                raise ValueError(
                                    "id, nombre e instructor son obligatorios")
                            if cupo < 1:
                                raise ValueError("el cupo debe ser mayor que cero")
                            validos.append({
                                "id": clase_id, "nombre": nombre,
                                "instructor": instructor, "horario": horario,
                                "cupo": cupo})
                        except (ValueError, AttributeError) as exc:
                            errores.append(f"Fila {numero}: {exc}")
                    if filas == 0:
                        errores.append("El CSV de clases no contiene registros.")
    except FileNotFoundError:
        errores.append(f"Archivo no encontrado: {ruta}")
    except (OSError, csv.Error, UnicodeError) as exc:
        errores.append(f"No se pudo leer {ruta}: {exc}")
    return validos, errores
