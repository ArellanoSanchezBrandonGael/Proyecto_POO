"""Logica de aplicacion del centro deportivo."""

import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .exceptions import PersistenciaError, ValidacionError
from .models import (Clase, MembresiaEstudiante, MembresiaGeneral, MembresiaPremium, RegistroAcceso, Reserva, Socio, Visitante)
from .storage import (JsonRepository, dt_to_text, leer_alumnos, leer_clases, parse_datetime)
from tempfile import TemporaryDirectory

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
        self.personas_dentro = set()
        self._contador_socio = 0
        self._contador_reserva = 0
        self._contador_acceso = 0
        try:
            self._cargar()
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise PersistenciaError("El archivo de estado contiene datos invalidos.") from exc

    def _cargar(self) -> None:
        """Reconstruye los objetos del dominio a partir del archivo JSON."""
        datos = self.repository.cargar()
        self._contador_socio = datos.get("contador_socio", 0)
        self._contador_reserva = datos.get("contador_reserva", 0)
        self._contador_acceso = datos.get("contador_acceso", 0)
        self.personas_en_gimnasio = datos.get("personas_en_gimnasio", 0)
        self.personas_dentro = set(
            tuple(persona) for persona in datos.get("personas_dentro", [])
        )
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
            "personas_dentro": list(self.personas_dentro),
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
            if socio.membresia.tipo == "estudiante":
                inscrito = any(
                    alumno.get("nombre", "").lower() == socio.nombre.lower()
                    and alumno.get("apellido", "").lower() == socio.apellido.lower()
                    for alumno in self.alumnos.values()
                )

                if not socio.es_alumno or not inscrito:
                    raise ValidacionError("El socio no aparece en el archivo de alumnos inscritos.")
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
        # Validar el horario del centro deportivo
        if accion == "entrada":
            if ahora.weekday() == 6 or not (6 <= ahora.hour < 22):
                 raise ValidacionError("Fuera del horario del centro deportivo.")
        if accion not in {"entrada", "salida"}:
            raise ValidacionError("Accion invalida: entrada o salida.")
        if area not in {"gimnasio", "alberca", "clase"}:
            raise ValidacionError("Area invalida.")
        with self.lock:
            clave_acceso = (persona_id, area)

            if accion == "entrada" and clave_acceso in self.personas_dentro:
             raise ValidacionError("La persona ya se encuentra dentro de esta area.")

            if accion == "salida" and clave_acceso not in self.personas_dentro:
                raise ValidacionError("La persona no se encuentra dentro de esta area.")
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
                        if ahora.date() < visitante.fecha.date():
                            raise ValidacionError("Fecha de acceso invalida.")

                        if ahora.date() > visitante.fecha.date():
                            visitante.fecha = ahora
                            mes = ahora.strftime("%Y-%m")
                            clave = f"{mes}:visitante"
                            self.ingresos[clave] = self.ingresos.get(clave, 0.0) + visitante.precio
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
            if accion == "entrada":
                    self.personas_dentro.add(clave_acceso)
            else:
                 self.personas_dentro.remove(clave_acceso)
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
                clave = f"{clase.clase_id} - {clase.nombre}"
                asistencias[clave] = sum(
                    r.estado == "asistio" for r in clase.reservas)
                

        aforo_por_hora = {}
        ocupacion = 0

        inicio = datetime.strptime(mes, "%Y-%m")

        if inicio.month == 12:
            fin = datetime(inicio.year + 1, 1, 1)
        else:
            fin = datetime(inicio.year, inicio.month + 1, 1)

        registros = sorted(
            [r for r in self.accesos if r.area == "gimnasio"],
            key=lambda r: r.momento
        )

        indice = 0
        hora = inicio

        while hora < fin:
            siguiente_hora = hora + timedelta(hours=1)

            while indice < len(registros) and registros[indice].momento < siguiente_hora:
                if registros[indice].accion == "entrada":
                    ocupacion += 1
                else:
                    ocupacion = max(0, ocupacion - 1)

                indice += 1

            if hora.weekday() < 6 and 6 <= hora.hour < 22:
                clave = hora.strftime("%Y-%m-%d %H:00")
                aforo_por_hora[clave] = ocupacion

            hora = siguiente_hora
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
        lineas.append("Ocupacion del gimnasio por hora:")
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
    def _ejecutar_simulacion(self, ahora: datetime,
                             personas: int = 120) -> dict:
    
        """Simula accesos y reservas simultaneas."""
        errores = []
        hilos = []

        def torniquete(indice):
            for i in range(personas // 4):
                persona_id = f"SIM-{indice}-{i}"

                try:
                    self.registrar_acceso(
                        persona_id, "gimnasio", "entrada", ahora)

                    if random.choice([True, False]):
                        self.registrar_acceso(
                            persona_id, "gimnasio", "salida", ahora)

                except ValidacionError as exc:
                    errores.append(str(exc))

        def reservar_clase(socio_id, clase_id):
            try:
                self.reservar(socio_id, clase_id, ahora)
            except ValidacionError as exc:
                errores.append(str(exc))

        for i in range(4):
            hilo = threading.Thread(
                target=torniquete, args=(i,))
            hilos.append(hilo)

        for clase in self.clases.values():
            anticipacion = clase.horario - ahora

            if timedelta(0) < anticipacion <= timedelta(hours=48):
                cantidad = clase.lugares_disponibles + 5

                for i in range(cantidad):
                    socio = self.registrar_socio(
                        f"Simulado{i}", "Prueba")

                    self.contratar_membresia(
                        socio.socio_id, "premium", ahora)

                    hilo = threading.Thread(
                        target=reservar_clase,
                        args=(socio.socio_id, clase.clase_id))

                    hilos.append(hilo)

                break

        for hilo in hilos:
            hilo.start()

        for hilo in hilos:
            hilo.join()

        self.guardar()

        return {
            "aforo": self.personas_en_gimnasio,
            "reservas_totales": len(self.reservas),
            "reservas_activas": sum(
                r.estado in {"reservada", "asistio"}
                for r in self.reservas.values()),
            "errores": errores
        }
    def simular_hora_pico(self, ahora: datetime,
                          personas: int = 120) -> dict:
        """Ejecuta una simulacion sin modificar los datos reales."""
        with TemporaryDirectory() as temporal:
            centro = CentroDeportivo(Path(temporal) / "state.json")

            for clase in self.clases.values():
                centro.clases[clase.clase_id] = Clase(
                    clase.clase_id,
                    clase.nombre,
                    clase.instructor,
                    clase.horario,
                    clase.cupo
                )

            return centro._ejecutar_simulacion(ahora, personas)