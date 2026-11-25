"""Logica de aplicacion del centro deportivo."""

import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .exceptions import PersistenciaError, ValidacionError
from .models import (Clase, MembresiaEstudiante, MembresiaGeneral, MembresiaPremium, RegistroAcceso, Reserva, Socio, Visitante)
from .storage import (JsonRepository, dt_to_text, leer_alumnos, leer_clases, parse_datetime)


class CentroDeportivo:
    """Coordina las reglas del negocio, las entidades y el almacenamiento."""

    AFORO_MAXIMO = 60

    def __init__(self, ruta_datos: Path):
        """Crea las colecciones y recupera el ultimo estado guardado."""
        self.repository = JsonRepository(ruta_datos)
        self.lock = threading.RLock()
        self.socios: dict[str, Socio] = {}
        self.alumnos: dict[str, dict] = {}
        self.clases: dict[str, Clase] = {}
        self.visitantes: dict[str, Visitante] = {}
        self.accesos: list[RegistroAcceso] = []
        self.reservas: dict[str, Reserva] = {}
        self.ingresos: dict[str, float] = {}
        self.personas_en_gimnasio = 0
        self._contador_socio = 0
        self._contador_reserva = 0
        self._contador_acceso = 0
        self._cargar()

    def _cargar(self) -> None:
        """Reconstruye los objetos del dominio a partir del archivo JSON."""
        datos = self.repository.cargar()
        self._contador_socio = datos.get("contador_socio", 0)
        self._contador_reserva = datos.get("contador_reserva", 0)
        self._contador_acceso = datos.get("contador_acceso", 0)
        self.personas_en_gimnasio = datos.get("personas_en_gimnasio", 0)
        self.ingresos = datos.get("ingresos", {})
        self.alumnos = datos.get("alumnos", {})

        for item in datos.get("socios", []):
            socio = Socio(item["id"], item["nombre"], item["apellido"], item.get("es_alumno", False))
            socio._faltas_mes = item.get("faltas_mes", {})
            if item.get("reserva_bloqueada_hasta"):
                socio.reserva_bloqueada_hasta = parse_datetime(
                    item["reserva_bloqueada_hasta"])
            tipo = item.get("membresia_tipo")
            vigencia_texto = item.get("membresia_vigencia")
            if tipo and vigencia_texto:
                vigencia = parse_datetime(vigencia_texto)
                if tipo == "estudiante":
                    socio.membresia = MembresiaEstudiante(vigencia)
                elif tipo == "general":
                    socio.membresia = MembresiaGeneral(vigencia)
                elif tipo == "premium":
                    socio.membresia = MembresiaPremium(vigencia)
            self.socios[socio.socio_id] = socio

        for item in datos.get("clases", []):
            clase = Clase(item["id"], item["nombre"], item["instructor"], parse_datetime(item["horario"]), item["cupo"])
            self.clases[clase.clase_id] = clase

        for item in datos.get("reservas", []):
            socio = self.socios.get(item["socio_id"])
            clase = self.clases.get(item["clase_id"])
            if socio and clase:
                reserva = Reserva(item["folio"], socio, clase, parse_datetime(item["creada"]))
                reserva.estado = item["estado"]
                clase.reservas.append(reserva)
                socio.reservas.append(reserva)
                self.reservas[reserva.folio] = reserva

        for item in datos.get("visitantes", []):
            visitante = Visitante(item["id"], item["nombre"], parse_datetime(item["fecha"]))
            self.visitantes[visitante.visitante_id] = visitante

        for item in datos.get("accesos", []):
            registro = RegistroAcceso(
                item["id"], item["persona_id"], item["tipo_persona"],
                item["accion"], item["area"], parse_datetime(item["momento"]))
            self.accesos.append(registro)

    def _serializar(self) -> dict:
        """Convierte las entidades en tipos de datos que JSON puede guardar."""
        socios = []
        for socio in self.socios.values():
            membresia_tipo = socio.membresia.tipo if socio.membresia else None
            membresia_vigencia = (dt_to_text(socio.membresia.vigencia)if socio.membresia else None)
            socios.append({
                "id": socio.socio_id, "nombre": socio.nombre,
                "apellido": socio.apellido, "es_alumno": socio.es_alumno,
                "membresia_tipo": membresia_tipo,
                "membresia_vigencia": membresia_vigencia,
                "faltas_mes": socio._faltas_mes,
                "reserva_bloqueada_hasta": (
                    dt_to_text(socio.reserva_bloqueada_hasta)
                    if socio.reserva_bloqueada_hasta else None)
            })
        clases = [{"id": c.clase_id, "nombre": c.nombre,
                   "instructor": c.instructor, "horario": dt_to_text(c.horario),
                   "cupo": c.cupo} for c in self.clases.values()]
        reservas = [{"folio": r.folio, "socio_id": r.socio.socio_id,
                     "clase_id": r.clase.clase_id,
                     "creada": dt_to_text(r.creada),
                     "estado": r.estado} for r in self.reservas.values()]
        visitantes = [{"id": v.visitante_id, "nombre": v.nombre,
                       "fecha": dt_to_text(v.fecha)}
                      for v in self.visitantes.values()]
        accesos = [{"id": a.registro_id, "persona_id": a.persona_id,
                    "tipo_persona": a.tipo_persona, "accion": a.accion,
                    "area": a.area, "momento": dt_to_text(a.momento)}
                   for a in self.accesos]
        return {
            "contador_socio": self._contador_socio,
            "contador_reserva": self._contador_reserva,
            "contador_acceso": self._contador_acceso,
            "personas_en_gimnasio": self.personas_en_gimnasio,
            "ingresos": self.ingresos,
            "alumnos": self.alumnos,
            "socios": socios, "clases": clases, "reservas": reservas,
            "visitantes": visitantes, "accesos": accesos
        }

    def guardar(self) -> None:
        """Guarda el estado completo mediante el repositorio JSON."""
        self.repository.guardar(self._serializar())

    def importar_alumnos(self, ruta: Path) -> list[str]:
        """Carga alumnos validos y devuelve los errores de filas rechazadas."""
        validos, errores = leer_alumnos(ruta)
        with self.lock:
            for alumno in validos:
                self.alumnos[alumno["id"]] = alumno
            self.guardar()
        return errores

    def registrar_socio(self, nombre: str, apellido: str,
                        es_alumno: bool = False) -> Socio:
        """Valida y registra un socio con un identificador consecutivo."""
        if not nombre.strip() or not apellido.strip():
            raise ValidacionError("Nombre y apellido son obligatorios.")
        with self.lock:
            self._contador_socio += 1
            socio_id = f"SOC-{self._contador_socio:04d}"
            socio = Socio(socio_id, nombre.strip(), apellido.strip(), es_alumno)
            self.socios[socio_id] = socio
            self.guardar()
            return socio

    def contratar_membresia(self, socio_id: str, tipo: str,
                            ahora: datetime) -> float:
        """Aplica las reglas de elegibilidad, asigna membresia y registra ingreso."""
        tipo = tipo.lower()
        with self.lock:
            socio = self.socios.get(socio_id)
            if not socio:
                raise ValidacionError(f"No existe el socio {socio_id}.")
            if tipo == "estudiante":
                inscrito = any(
                    alumno.get("nombre", "").lower() == socio.nombre.lower()
                    and alumno.get("apellido", "").lower() == socio.apellido.lower()
                    for alumno in self.alumnos.values()
                )
                if not socio.es_alumno or not inscrito:
                    raise ValidacionError(
                        "El socio no aparece en el archivo de alumnos inscritos.")
                membresia = MembresiaEstudiante(ahora + timedelta(days=30))
            elif tipo == "general":
                membresia = MembresiaGeneral(ahora + timedelta(days=30))
            elif tipo == "premium":
                membresia = MembresiaPremium(ahora + timedelta(days=30))
            else:
                raise ValidacionError("Tipo invalido: estudiante, general o premium.")
            socio.membresia = membresia
            mes = ahora.strftime("%Y-%m")
            clave = f"{mes}:{tipo}"
            self.ingresos[clave] = self.ingresos.get(clave, 0.0) + membresia.precio
            self.guardar()
            return membresia.precio

    def renovar_membresia(self, socio_id: str, ahora: datetime) -> float:
        """Extiende la vigencia de la membresia actual y registra el cobro."""
        with self.lock:
            socio = self.socios.get(socio_id)
            if not socio or not socio.membresia:
                raise ValidacionError("El socio no tiene membresia.")
            socio.membresia.renovar(ahora)
            mes = ahora.strftime("%Y-%m")
            clave = f"{mes}:{socio.membresia.tipo}"
            self.ingresos[clave] = self.ingresos.get(clave, 0.0) + socio.membresia.precio
            self.guardar()
            return socio.membresia.precio

    def cambiar_membresia(self, socio_id: str, tipo: str, ahora: datetime) -> float:
        """Reemplaza la membresia del socio por el tipo solicitado."""
        return self.contratar_membresia(socio_id, tipo, ahora)

    def cargar_clases(self, ruta: Path) -> list[str]:
        """Importa las clases validas de un archivo CSV."""
        validos, errores = leer_clases(ruta)
        with self.lock:
            for item in validos:
                clase = Clase(item["id"], item["nombre"], item["instructor"], item["horario"], item["cupo"])
                self.clases[clase.clase_id] = clase
            self.guardar()
        return errores

    def registrar_acceso(self, persona_id: str, area: str, accion: str, ahora: datetime) -> str:
        """Valida un acceso, actualiza el aforo y guarda el movimiento."""
        accion = accion.lower()
        area = area.lower()
        if accion not in {"entrada", "salida"}:
            raise ValidacionError("Accion invalida: entrada o salida.")
        if area not in {"gimnasio", "alberca", "clase"}:
            raise ValidacionError("Area invalida.")
        with self.lock:
            socio = self.socios.get(persona_id)
            tipo_persona = "socio"
            if socio:
                if accion == "entrada":
                    if not socio.membresia:
                        raise ValidacionError("El socio no tiene membresia.")
                    if not socio.membresia.esta_vigente(ahora):
                        raise ValidacionError("Membresia vencida.")
                    if not socio.membresia.permite_area(area):
                        raise ValidacionError("La membresia no incluye esa area.")
                    if not socio.membresia.permite_entrada(ahora):
                        raise ValidacionError("Fuera del horario permitido.")
                    if area == "gimnasio" and self.personas_en_gimnasio >= self.AFORO_MAXIMO:
                        raise ValidacionError("Aforo completo.")
                    if area == "gimnasio":
                        self.personas_en_gimnasio += 1
            else:
                visitante = self.visitantes.get(persona_id)
                if visitante:
                    tipo_persona = "visitante"
                    if accion == "entrada":
                        if area != "gimnasio":
                            raise ValidacionError("El pase de visitante solo incluye gimnasio.")
                        if self.personas_en_gimnasio >= self.AFORO_MAXIMO:
                            raise ValidacionError("Aforo completo.")
                        if ahora - visitante.fecha > timedelta(days=1):
                            raise ValidacionError("El pase de visitante vencio.")
                        self.personas_en_gimnasio += 1
                elif accion == "entrada":
                    if area != "gimnasio":
                        raise ValidacionError(
                            "El pase de visitante solo incluye gimnasio.")
                    if self.personas_en_gimnasio >= self.AFORO_MAXIMO:
                        raise ValidacionError("Aforo completo.")
                    tipo_persona = "visitante"
                    visitante_id = persona_id
                    visitante = Visitante(visitante_id, "Visitante", ahora)
                    self.visitantes[visitante_id] = visitante
                    mes = ahora.strftime("%Y-%m")
                    clave = f"{mes}:visitante"
                    self.ingresos[clave] = self.ingresos.get(clave, 0.0) + 120.0
                    self.personas_en_gimnasio += 1
                else:
                    raise ValidacionError(f"No existe la persona {persona_id}.")

            if accion == "salida" and area == "gimnasio":
                self.personas_en_gimnasio = max(0, self.personas_en_gimnasio - 1)
            self._contador_acceso += 1
            registro = RegistroAcceso(
                f"ACC-{self._contador_acceso:06d}", persona_id,
                tipo_persona, accion, area, ahora)
            self.accesos.append(registro)
            self.guardar()
            return registro.registro_id

    def reservar(self, socio_id: str, clase_id: str,
                 ahora: datetime) -> Reserva:
        """Comprueba vigencia, beneficios, anticipacion y cupo antes de reservar."""
        with self.lock:
            socio = self.socios.get(socio_id)
            clase = self.clases.get(clase_id)
            if not socio:
                raise ValidacionError(f"No existe el socio {socio_id}.")
            if not clase:
                raise ValidacionError(f"No existe la clase {clase_id}.")
            if not socio.membresia or not socio.membresia.esta_vigente(ahora):
                raise ValidacionError("El socio no tiene una membresia vigente.")
            if not socio.membresia.permite_area("clase"):
                raise ValidacionError("La membresia no incluye clases grupales.")
            if socio.reserva_bloqueada_hasta and ahora < socio.reserva_bloqueada_hasta:
                raise ValidacionError("El socio tiene suspendida la reserva por siete dias.")
            self._contador_reserva += 1
            reserva = Reserva(f"RES-{self._contador_reserva:06d}",
                              socio, clase, ahora)
            clase.reservar(reserva, ahora)
            self.reservas[reserva.folio] = reserva
            self.guardar()
            return reserva

    def cancelar_reserva(self, folio: str, ahora: datetime) -> None:
        """Cancela una reserva si se respeta el limite de anticipacion."""
        with self.lock:
            reserva = self.reservas.get(folio)
            if not reserva:
                raise ValidacionError("No existe la reserva.")
            reserva.clase.cancelar_reserva(reserva, ahora)
            self.guardar()

    def pasar_lista(self, clase_id: str, socio_id: str,
                    asistio: bool, ahora: datetime) -> None:
        """Actualiza asistencia y acumula una falta cuando corresponde."""
        with self.lock:
            clase = self.clases.get(clase_id)
            if not clase:
                raise ValidacionError("No existe la clase.")
            clase.pasar_lista(socio_id, ahora, asistio)
            self.guardar()

    def estado_socio(self, socio_id: str) -> dict:
        """Entrega los datos del socio en una estructura lista para mostrar."""
        socio = self.socios.get(socio_id)
        if not socio:
            raise ValidacionError(f"No existe el socio {socio_id}.")
        membresia = None
        if socio.membresia:
            membresia = {"tipo": socio.membresia.tipo,
                         "precio": socio.membresia.precio,
                         "vigencia": dt_to_text(socio.membresia.vigencia)}
        return {
            "id": socio.socio_id, "nombre": socio.nombre_completo,
            "membresia": membresia,
            "reservas": [{"folio": r.folio, "clase": r.clase.nombre,
                          "estado": r.estado,
                          "horario": dt_to_text(r.clase.horario)}
                         for r in socio.reservas],
            "faltas": socio._faltas_mes,
            "bloqueado_hasta": (
                dt_to_text(socio.reserva_bloqueada_hasta)
                if socio.reserva_bloqueada_hasta else None)
        }

    def reporte_mes(self, mes: str, ruta: Path) -> str:
        """Resume ingresos, asistencias y movimientos de aforo del mes."""
        try:
            datetime.strptime(mes, "%Y-%m")
        except ValueError as exc:
            raise ValidacionError("Use el formato de mes YYYY-MM.") from exc
        ingresos = {clave: monto for clave, monto in self.ingresos.items()
                    if clave.startswith(mes + ":")}
        asistencias = {}
        for clase in self.clases.values():
            if clase.horario.strftime("%Y-%m") == mes:
                asistencias[clase.nombre] = sum(
                    r.estado == "asistio" for r in clase.reservas)

        aforo_por_hora: dict[str, int] = {}
        for registro in self.accesos:
            if registro.momento.strftime("%Y-%m") == mes and registro.area == "gimnasio":
                clave = f"{registro.momento.strftime('%Y-%m-%d')} "
                clave += f"{registro.momento.hour:02d}:00"
                aforo_por_hora[clave] = (
                    aforo_por_hora.get(clave, 0) + (1 if registro.accion == "entrada" else -1))

        lineas = [f"Reporte del centro deportivo - {mes}", ""]
        lineas.append("Ingresos:")
        if ingresos:
            for clave, monto in sorted(ingresos.items()):
                lineas.append(f"- {clave.split(':', 1)[1]}: ${monto:.2f}")
        else:
            lineas.append("- Sin ingresos registrados")
        lineas.append("")
        lineas.append("Asistencia por clase:")
        if asistencias:
            for nombre, cantidad in sorted(asistencias.items()):
                lineas.append(f"- {nombre}: {cantidad}")
        else:
            lineas.append("- Sin clases registradas")
        lineas.append("")
        lineas.append("Movimientos de personas por hora:")
        if aforo_por_hora:
            for hora, movimiento in sorted(aforo_por_hora.items()):
                lineas.append(f"- {hora}: {movimiento}")
        else:
            lineas.append("- Sin movimientos registrados")
        texto = "\n".join(lineas) + "\n"
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(texto, encoding="utf-8")
        except OSError as exc:
            raise PersistenciaError(f"No se pudo crear el reporte: {exc}")
        return texto

    def simular_hora_pico(self, ahora: datetime,
                          personas: int = 120) -> dict:
        """Simula entradas simultaneas y reservas para poner a prueba los cupos."""
        errores: list[str] = []

        for clase in self.clases.values():
            if clase.horario <= ahora:
                continue
            disponibles = clase.lugares_disponibles
            break

        def torniquete(indice: int) -> None:
            for i in range(personas // 4):
                persona_id = f"SIM-{indice}-{i}"
                if random.choice([True, False]):
                    try:
                        self.registrar_acceso(persona_id, "gimnasio",
                                              "entrada", ahora)
                    except ValidacionError as exc:
                        if "Aforo completo" not in str(exc):
                            errores.append(str(exc))
                else:
                    try:
                        self.registrar_acceso(persona_id, "gimnasio",
                                              "salida", ahora)
                    except ValidacionError:
                        pass

        hilos = [threading.Thread(target=torniquete, args=(i,))
                 for i in range(4)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        reservas = [h for h in hilos]
        reservas.clear()
        for clase in list(self.clases.values())[:4]:
            if clase.horario - ahora > timedelta(hours=48):
                continue
            socios_simulados = []
            for i in range(1, 10):
                socio = Socio(f"SIMSOC-{i}-{clase.clase_id}",
                              f"Socio{i}", "Simulado")
                socio.membresia = MembresiaPremium(ahora + timedelta(days=30))
                socios_simulados.append(socio)

            def reservar_clase(clase_obj: Clase, socios: list[Socio]) -> None:
                for socio in socios:
                    try:
                        self._contador_reserva += 1
                        reserva = Reserva(
                            f"SIM-{clase_obj.clase_id}-{socio.socio_id}",
                            socio, clase_obj, ahora)
                        clase_obj.reservar(reserva, ahora)
                        socio.reservas.append(reserva)
                    except ValidacionError:
                        pass

            for socios in [socios_simulados]:
                hilo = threading.Thread(target=reservar_clase,
                                        args=(clase, socios))
                reservas.append(hilo)
                hilo.start()
        for hilo in reservas:
            hilo.join()
        self.guardar()
        total_reservas = sum(len(c.reservas) for c in self.clases.values())
        total_activas = sum(
            r.estado in {"reservada", "asistio"}
            for c in self.clases.values() for r in c.reservas)
        return {"aforo": self.personas_en_gimnasio,
                "reservas_totales": total_reservas,
                "reservas_activas": total_activas,
                "errores": errores}
