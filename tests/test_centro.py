import argparse
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from centro_deportivo.exceptions import ValidacionError
from centro_deportivo.main import ejecutar_args, pedir_opcion
from centro_deportivo.service import CentroDeportivo
from centro_deportivo.storage import leer_alumnos, leer_clases


class CentroDeportivoTests(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.centro = CentroDeportivo(Path(temporal.name) / "state.json")
        self.ahora = datetime(2026, 11, 23, 10, 0)

    def test_estudiante_requiere_alumno_inscrito(self):
        socio = self.centro.registrar_socio("Ana", "Lopez", True)
        with self.assertRaises(ValidacionError):
            self.centro.contratar_membresia(
                socio.socio_id, "estudiante", self.ahora)

    def test_membresia_estudiante_horario(self):
        socio = self.centro.registrar_socio("Ana", "Lopez", True)
        socio_id = socio.socio_id
        self.centro.alumnos[socio_id] = {
            "id": socio_id, "nombre": "Ana", "apellido": "Lopez"}
        self.centro.contratar_membresia(
            socio_id, "estudiante", datetime(2026, 11, 24, 10, 0))
        registro = self.centro.registrar_acceso(
            socio_id, "gimnasio", "entrada",
            datetime(2026, 11, 24, 10, 0))
        self.assertTrue(registro.startswith("ACC-"))

    def test_aforo_no_se_excede(self):
        for i in range(61):
            self.centro.socios[f"V{i}"] = None
        self.centro.personas_en_gimnasio = 60
        with self.assertRaises(ValidacionError):
            self.centro.registrar_acceso(
                "VISITA-NUEVA", "gimnasio", "entrada", self.ahora)

    def test_reserva_ultimo_lugar(self):
        socio1 = self.centro.registrar_socio("Uno", "Prueba")
        socio2 = self.centro.registrar_socio("Dos", "Prueba")
        self.centro.contratar_membresia(
            socio1.socio_id, "premium", self.ahora)
        self.centro.contratar_membresia(
            socio2.socio_id, "premium", self.ahora)
        from centro_deportivo.models import Clase
        clase = Clase("CL1", "Yoga", "Instructora",
                      datetime(2026, 11, 23, 12, 0), 1)
        self.centro.clases["CL1"] = clase
        self.centro.reservar(socio1.socio_id, "CL1", self.ahora)
        with self.assertRaises(ValidacionError):
            self.centro.reservar(socio2.socio_id, "CL1", self.ahora)

    def test_no_se_reserva_una_clase_que_ya_inicio(self):
        socio = self.centro.registrar_socio("Ana", "Lopez")
        self.centro.contratar_membresia(socio.socio_id, "premium", self.ahora)
        from centro_deportivo.models import Clase
        self.centro.clases["CL1"] = Clase(
            "CL1", "Yoga", "Instructora", self.ahora, 10)

        with self.assertRaisesRegex(ValidacionError, "ya inicio"):
            self.centro.reservar(socio.socio_id, "CL1", self.ahora)

    def test_opcion_invalida_muestra_error_y_vuelve_a_preguntar(self):
        salida = StringIO()
        with patch("builtins.input", side_effect=["incorrecta", "premium"]):
            with redirect_stdout(salida):
                respuesta = pedir_opcion(
                    "Tipo: ", ("estudiante", "general", "premium"))

        self.assertEqual(respuesta, "premium")
        self.assertIn("Error: opcion invalida.", salida.getvalue())

    def test_csv_alumnos_informa_columnas_obligatorias_ausentes(self):
        ruta = Path(self.centro.repository.ruta.parent) / "alumnos_incompleto.csv"
        ruta.write_text("id,nombre\nA001,Ana\n", encoding="utf-8")

        validos, errores = leer_alumnos(ruta)

        self.assertEqual(validos, [])
        self.assertTrue(any("apellido" in error for error in errores))

    def test_csv_clases_informa_columnas_obligatorias_ausentes(self):
        ruta = Path(self.centro.repository.ruta.parent) / "clases_incompleto.csv"
        ruta.write_text("id,nombre,instructor,horario\nC1,Yoga,Ana,2026-11-25 10:00\n",
                        encoding="utf-8")

        validos, errores = leer_clases(ruta)

        self.assertEqual(validos, [])
        self.assertTrue(any("cupo" in error for error in errores))

    def test_csv_vacio_se_reporta_como_error(self):
        ruta = Path(self.centro.repository.ruta.parent) / "alumnos_vacio.csv"
        ruta.write_text("", encoding="utf-8")

        validos, errores = leer_alumnos(ruta)

        self.assertEqual(validos, [])
        self.assertTrue(any("vacio" in error for error in errores))

    def test_importar_csv_muestra_error_y_no_indica_exito(self):
        ruta = Path(self.centro.repository.ruta.parent) / "alumnos_sin_apellido.csv"
        ruta.write_text("id,nombre\nA001,Ana\n", encoding="utf-8")
        salida = StringIO()
        args = argparse.Namespace(
            comando="importar-alumnos", ruta=str(ruta), ahora=None)

        with redirect_stdout(salida):
            ejecutar_args(args, self.centro)

        self.assertIn("terminada con errores", salida.getvalue())
        self.assertIn("apellido", salida.getvalue())
        self.assertNotIn("importado correctamente", salida.getvalue())

    def test_entrada_visitante_invalida_no_registra_cobro_ni_visitante(self):
        with self.assertRaises(ValidacionError):
            self.centro.registrar_acceso(
                "VISITA-1", "alberca", "entrada", self.ahora)

        self.assertNotIn("VISITA-1", self.centro.visitantes)
        self.assertEqual(self.centro.ingresos, {})
        self.assertEqual(self.centro.personas_en_gimnasio, 0)
    def test_no_cancelar_reserva_inactiva(self):
            from centro_deportivo.models import Clase, Socio, Reserva

            clase = Clase("CL1", "Yoga", "Ana",
                      datetime(2026, 11, 23, 14, 0), 10)
            socio = Socio("SOC1", "Ana", "Lopez")
            reserva = Reserva("RES1", socio, clase, self.ahora)

            clase.reservar(reserva, self.ahora)
            clase.cancelar_reserva(reserva, self.ahora)

            with self.assertRaises(ValidacionError):
                clase.cancelar_reserva(reserva, self.ahora)

    def test_no_pasar_lista_antes_de_clase(self):
        from centro_deportivo.models import Clase, Socio, Reserva

        clase = Clase("CL1", "Yoga", "Ana",
                      datetime(2026, 11, 23, 14, 0), 10)
        socio = Socio("SOC1", "Ana", "Lopez")
        reserva = Reserva("RES1", socio, clase, self.ahora)

        clase.reservar(reserva, self.ahora)

        with self.assertRaises(ValidacionError):
            clase.pasar_lista("SOC1", self.ahora, True)
    def test_json_danado(self):
        from centro_deportivo.exceptions import PersistenciaError

        ruta = self.centro.repository.ruta
        ruta.write_text("{archivo incorrecto", encoding="utf-8")

        with self.assertRaises(PersistenciaError):
            CentroDeportivo(ruta)

    def test_json_estructura_invalida(self):
        from centro_deportivo.exceptions import PersistenciaError

        ruta = self.centro.repository.ruta
        ruta.write_text("[]", encoding="utf-8")

        with self.assertRaises(PersistenciaError):
            CentroDeportivo(ruta)

    def test_json_datos_invalidos(self):
        from centro_deportivo.exceptions import PersistenciaError

        ruta = self.centro.repository.ruta
        ruta.write_text('{"socios": [{}]}', encoding="utf-8")

        with self.assertRaises(PersistenciaError):
            CentroDeportivo(ruta)
    def test_simulacion_no_modifica_datos_reales(self):
        from centro_deportivo.models import Clase

        self.centro.clases["CL1"] = Clase(
            "CL1", "Yoga", "Ana",
            datetime(2026, 11, 23, 12, 0), 5)

        estado_original = self.centro._serializar()

        for i in range(2):
            resultado = self.centro.simular_hora_pico(
                self.ahora)

            self.assertLessEqual(resultado["aforo"], 60)
            self.assertGreaterEqual(resultado["aforo"], 0)
            self.assertEqual(resultado["reservas_activas"], 5)
            self.assertEqual(
                self.centro._serializar(), estado_original)
    def test_reporte_ocupacion_por_hora(self):
        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "entrada",
            datetime(2026, 11, 23, 10, 0))

        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "salida",
            datetime(2026, 11, 23, 13, 0))

        ruta = self.centro.repository.ruta.parent / "reporte.txt"
        reporte = self.centro.reporte_mes("2026-11", ruta)

        self.assertIn("2026-11-23 10:00: 1\n", reporte)
        self.assertIn("2026-11-23 11:00: 1\n", reporte)
        self.assertIn("2026-11-23 12:00: 1\n", reporte)
        self.assertIn("2026-11-23 13:00: 0\n", reporte)
        self.assertTrue(ruta.exists())
    def test_cobro_pase_visitante(self):
        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "entrada",
            datetime(2026, 11, 23, 10, 0))

        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "salida",
            datetime(2026, 11, 23, 11, 0))

        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "entrada",
            datetime(2026, 11, 23, 12, 0))

        self.assertEqual(
            self.centro.ingresos["2026-11:visitante"], 120.0)

        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "salida",
            datetime(2026, 11, 23, 13, 0))

        self.centro.registrar_acceso(
            "VISITA-1", "gimnasio", "entrada",
            datetime(2026, 11, 24, 10, 0))

        self.assertEqual(
            self.centro.ingresos["2026-11:visitante"], 240.0)
    def test_suspension_por_tres_faltas(self):
        from centro_deportivo.models import Clase, Socio, Reserva
        from datetime import timedelta

        socio = Socio("SOC1", "Ana", "Lopez")

        for i in range(3):
            horario = self.ahora + timedelta(hours=2 + i)

            clase = Clase(
                f"CL{i}", "Yoga", "Ana", horario, 10)

            reserva = Reserva(
                f"RES{i}", socio, clase, self.ahora)

            clase.reservar(reserva, self.ahora)
            clase.pasar_lista("SOC1", horario, False)

        self.assertEqual(socio.contar_faltas("2026-11"), 3)

        ultima_falta = self.ahora + timedelta(hours=4)
        fin_bloqueo = ultima_falta + timedelta(days=7)

        self.assertEqual(
            socio.reserva_bloqueada_hasta, fin_bloqueo)

        nueva_clase = Clase(
            "CL4", "Yoga", "Ana",
            ultima_falta + timedelta(hours=24), 10)

        reserva = Reserva(
            "RES4", socio, nueva_clase, ultima_falta)

        with self.assertRaises(ValidacionError):
            nueva_clase.reservar(reserva, ultima_falta)

        otra_clase = Clase(
            "CL5", "Yoga", "Ana",
            fin_bloqueo + timedelta(hours=2), 10)

        reserva = Reserva(
            "RES5", socio, otra_clase, fin_bloqueo)

        otra_clase.reservar(reserva, fin_bloqueo)

        self.assertEqual(len(otra_clase.reservas), 1)
    def test_renovacion_estudiante_no_inscrito(self):
        socio = self.centro.registrar_socio(
            "Ana", "Lopez", True)

        self.centro.alumnos["A001"] = {
            "id": "A001",
            "nombre": "Ana",
            "apellido": "Lopez"
        }

        self.centro.contratar_membresia(
            socio.socio_id, "estudiante", self.ahora)

        self.centro.alumnos.clear()

        with self.assertRaises(ValidacionError):
            self.centro.renovar_membresia(
                socio.socio_id, self.ahora)

if __name__ == "__main__":
    unittest.main()
