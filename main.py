"""Interfaz de terminal del centro deportivo."""

import argparse
from datetime import datetime
from pathlib import Path
import sys

from .exceptions import CentroDeportivoError
from .service import CentroDeportivo
from .storage import parse_datetime


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"
STATE_FILE = DATA_DIR / "state.json"
REPORT_DIR = BASE_DIR / "reportes"


def construir_parser() -> argparse.ArgumentParser:
    """Define los comandos disponibles y valida sus argumentos."""
    parser = argparse.ArgumentParser(
        description="Sistema del Centro Deportivo Universitario")
    parser.add_argument("--datetime", dest="ahora",
                        help="Fecha operativa YYYY-MM-DD HH:MM")
    sub = parser.add_subparsers(dest="comando")

    sub.add_parser("menu", help="Abrir menu interactivo")
    sub.add_parser("clase-listar", help="Mostrar clases")

    cmd = sub.add_parser("importar-alumnos")
    cmd.add_argument("ruta")

    cmd = sub.add_parser("socio-alta")
    cmd.add_argument("--nombre", required=True)
    cmd.add_argument("--apellido", required=True)
    cmd.add_argument("--alumno", action="store_true")

    cmd = sub.add_parser("membresia")
    cmd.add_argument("socio_id")
    cmd.add_argument("tipo", choices=["estudiante", "general", "premium"])
    cmd.add_argument("--accion", choices=["contratar", "renovar", "cambiar"],
                     default="contratar")

    cmd = sub.add_parser("clase-cargar")
    cmd.add_argument("ruta")

    cmd = sub.add_parser("reservar")
    cmd.add_argument("socio_id")
    cmd.add_argument("clase_id")

    cmd = sub.add_parser("cancelar-reserva")
    cmd.add_argument("folio")

    cmd = sub.add_parser("pasar-lista")
    cmd.add_argument("clase_id")
    cmd.add_argument("socio_id")
    cmd.add_argument("resultado", choices=["asistio", "falto"])

    cmd = sub.add_parser("acceso")
    cmd.add_argument("persona_id")
    cmd.add_argument("--area", choices=["gimnasio", "alberca", "clase"],
                     default="gimnasio")
    cmd.add_argument("--accion", choices=["entrada", "salida"],
                     default="entrada")

    cmd = sub.add_parser("estado-socio")
    cmd.add_argument("socio_id")

    cmd = sub.add_parser("reporte")
    cmd.add_argument("mes", help="Mes YYYY-MM")

    sub.add_parser("simular", help="Simular hora pico")
    sub.add_parser("lista-socios", help="Mostrar socios registrados")
    return parser


def obtener_ahora(args: argparse.Namespace) -> datetime:
    """Obtiene la fecha operativa indicada o usa el reloj del sistema."""
    if args.ahora:
        try:
            return parse_datetime(args.ahora)
        except ValueError as exc:
            raise CentroDeportivoError(str(exc))
    return datetime.now()


def imprimir_estado(estado: dict) -> None:
    """Muestra en consola la informacion resumida de un socio."""
    print(f"Socio: {estado['nombre']} ({estado['id']})")
    if estado["membresia"]:
        membresia = estado["membresia"]
        print(f"Membresia: {membresia['tipo']} - vigencia hasta "
              f"{membresia['vigencia']} - ${membresia['precio']:.2f}")
    else:
        print("Membresia: ninguna")
    print("Reservas:")
    if estado["reservas"]:
        for reserva in estado["reservas"]:
            print(f"- {reserva['folio']} | {reserva['clase']} | "
                  f"{reserva['horario']} | {reserva['estado']}")
    else:
        print("- Ninguna")
    print(f"Faltas por mes: {estado['faltas'] or 'ninguna'}")
    print(f"Bloqueado hasta: {estado['bloqueado_hasta'] or 'no'}")


def ejecutar_args(args: argparse.Namespace, centro: CentroDeportivo) -> None:
    """Ejecuta el comando elegido y muestra el resultado correspondiente."""
    ahora = obtener_ahora(args)
    comando = args.comando

    if comando == "importar-alumnos":
        errores = centro.importar_alumnos(
            BASE_DIR / args.ruta if not Path(args.ruta).is_absolute()
            else Path(args.ruta))
        if errores:
            print("Importacion de alumnos terminada con errores.")
        else:
            print("Archivo de alumnos importado correctamente.")
        for error in errores:
            print(f"Rechazado: {error}")
    elif comando == "socio-alta":
        socio = centro.registrar_socio(args.nombre, args.apellido, args.alumno)
        print(f"Socio registrado: {socio.socio_id} - {socio.nombre_completo}")
    elif comando == "membresia":
        if args.accion == "renovar":
            monto = centro.renovar_membresia(args.socio_id, ahora)
        else:
            monto = centro.contratar_membresia(args.socio_id, args.tipo, ahora)
        print(f"Operacion completada. Cargo: ${monto:.2f}")
    elif comando == "clase-cargar":
        ruta = (BASE_DIR / args.ruta if not Path(args.ruta).is_absolute()
                else Path(args.ruta))
        errores = centro.cargar_clases(ruta)
        if errores:
            print("Carga de clases terminada con errores.")
        else:
            print("Clases cargadas correctamente.")
        for error in errores:
            print(f"Rechazado: {error}")
    elif comando == "clase-listar":
        if not centro.clases:
            print("No hay clases cargadas.")
        for clase in sorted(centro.clases.values(), key=lambda c: c.horario):
            print(f"{clase.clase_id} | {clase.nombre} | {clase.instructor} | "
                  f"{clase.horario.strftime('%Y-%m-%d %H:%M')} | "
                  f"{clase.lugares_disponibles}/{clase.cupo}")
    elif comando == "reservar":
        reserva = centro.reservar(args.socio_id, args.clase_id, ahora)
        print(f"Reserva creada: {reserva.folio}")
    elif comando == "cancelar-reserva":
        centro.cancelar_reserva(args.folio, ahora)
        print("Reserva cancelada.")
    elif comando == "pasar-lista":
        centro.pasar_lista(args.clase_id, args.socio_id,
                           args.resultado == "asistio", ahora)
        print("Lista registrada.")
    elif comando == "acceso":
        folio = centro.registrar_acceso(args.persona_id, args.area,
                                        args.accion, ahora)
        print(f"Acceso registrado: {folio}")
    elif comando == "estado-socio":
        imprimir_estado(centro.estado_socio(args.socio_id))
    elif comando == "reporte":
        ruta = REPORT_DIR / f"reporte_{args.mes}.txt"
        print(centro.reporte_mes(args.mes, ruta))
        print(f"Reporte guardado en {ruta}")
    elif comando == "simular":
        resultado = centro.simular_hora_pico(ahora)
        print("Simulacion terminada:")
        print(f"- Aforo final: {resultado['aforo']}/{CentroDeportivo.AFORO_MAXIMO}")
        print(f"- Reservas activas: {resultado['reservas_activas']}")
        print(f"- Reservas totales: {resultado['reservas_totales']}")
    elif comando == "lista-socios":
        if not centro.socios:
            print("No hay socios registrados.")
        for socio in centro.socios.values():
            membresia = socio.membresia.tipo if socio.membresia else "sin membresia"
            print(f"{socio.socio_id} | {socio.nombre_completo} | {membresia}")
    elif comando == "menu":
        menu(centro)


def pedir(texto: str) -> str:
    """Solicita una respuesta de texto y quita espacios sobrantes."""
    return input(texto).strip()


def pedir_opcion(texto: str, opciones: tuple[str, ...]) -> str:
    """Repite la pregunta hasta recibir una opcion permitida."""
    while True:
        respuesta = pedir(texto).lower()
        if respuesta in opciones:
            return respuesta
        opciones_texto = ", ".join(opciones)
        print(f"Error: opcion invalida. Elija una de estas opciones: {opciones_texto}.")


def menu(centro: CentroDeportivo) -> None:
    """Muestra el menu principal y mantiene la aplicacion activa."""
    while True:
        print("\nCENTRO DEPORTIVO UNIVERSITARIO")
        print("1. Importar alumnos")
        print("2. Registrar socio")
        print("3. Contratar/cambiar membresia")
        print("4. Cargar clases")
        print("5. Reservar clase")
        print("6. Cancelar reserva")
        print("7. Pasar lista")
        print("8. Registrar entrada/salida")
        print("9. Consultar estado")
        print("10. Generar reporte")
        print("11. Ejecutar simulacion")
        print("12. Mostrar clases")
        print("0. Salir")
        opcion = pedir("Seleccione una opcion: ")
        if opcion not in {"0", "1", "2", "3", "4", "5", "6",
                          "7", "8", "9", "10", "11", "12"}:
            print("Error: opcion invalida. Seleccione un numero del 0 al 12.")
            continue
        try:
            ahora = datetime.now()
            if opcion == "0":
                return
            if opcion == "1":
                errores = centro.importar_alumnos(Path(pedir("Ruta CSV: ")))
                print("Importacion terminada.")
                for error in errores:
                    print(f"Rechazado: {error}")
            elif opcion == "2":
                socio = centro.registrar_socio(
                    pedir("Nombre: "), pedir("Apellido: "),
                    pedir_opcion("¿Es alumno? (s/n): ", ("s", "n")) == "s")
                print(f"Socio registrado: {socio.socio_id}")
            elif opcion == "3":
                socio_id = pedir("ID socio: ")
                accion = pedir_opcion(
                    "Accion (contratar/cambiar/renovar): ",
                    ("contratar", "cambiar", "renovar"))
                if accion == "renovar":
                    monto = centro.renovar_membresia(socio_id, ahora)
                else:
                    tipo = pedir_opcion(
                        "Tipo de membresia (estudiante/general/premium): ",
                        ("estudiante", "general", "premium"))
                    monto = centro.contratar_membresia(socio_id, tipo, ahora)
                print(f"Operacion de membresia completada. Cargo: ${monto:.2f}")
            elif opcion == "4":
                errores = centro.cargar_clases(Path(pedir("Ruta CSV: ")))
                print("Carga terminada.")
                for error in errores:
                    print(f"Rechazado: {error}")
            elif opcion == "5":
                reserva = centro.reservar(pedir("ID socio: "),
                                          pedir("ID clase: "), ahora)
                print(f"Reserva creada: {reserva.folio}")
            elif opcion == "6":
                centro.cancelar_reserva(pedir("Folio: "), ahora)
                print("Reserva cancelada.")
            elif opcion == "7":
                clase_id = pedir("ID clase: ")
                socio_id = pedir("ID socio: ")
                resultado = pedir_opcion(
                    "Resultado (asistio/falto): ", ("asistio", "falto"))
                centro.pasar_lista(
                    clase_id, socio_id, resultado == "asistio", ahora)
                print("Lista registrada.")
            elif opcion == "8":
                persona_id = pedir("ID persona: ")
                area = pedir_opcion(
                    "Area (gimnasio/alberca/clase): ",
                    ("gimnasio", "alberca", "clase"))
                accion = pedir_opcion(
                    "Accion (entrada/salida): ", ("entrada", "salida"))
                registro = centro.registrar_acceso(
                    persona_id, area, accion, ahora)
                print(f"Acceso registrado: {registro}")
            elif opcion == "9":
                imprimir_estado(centro.estado_socio(pedir("ID socio: ")))
            elif opcion == "10":
                mes = pedir("Mes (YYYY-MM): ")
                ruta = REPORT_DIR / f"reporte_{mes}.txt"
                print(centro.reporte_mes(mes, ruta))
            elif opcion == "11":
                resultado = centro.simular_hora_pico(ahora)
                print(resultado)
            elif opcion == "12":
                ejecutar_args(argparse.Namespace(comando="clase-listar",
                                                ahora=None), centro)
            else:
                print("Opcion no valida.")
        except (CentroDeportivoError, OSError, ValueError) as exc:
            print(f"Error: {exc}")


def main() -> int:
    """Prepara el servicio, ejecuta el comando y reporta errores controlados."""
    parser = construir_parser()
    args = parser.parse_args()
    if not args.comando:
        parser.print_help()
        return 0
    try:
        centro = CentroDeportivo(STATE_FILE)
        ejecutar_args(args, centro)
        return 0
    except CentroDeportivoError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Error inesperado controlado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
