# Centro Deportivo Universitario

Aplicacion de consola para registrar socios, gestionar membresias, importar
alumnos y clases, controlar accesos y reservas, y generar reportes.

## Requisitos

- Python 3.10 o posterior.
- No requiere paquetes externos.

## Instalacion y ejecucion

Abre una terminal en esta carpeta y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m centro_deportivo.main menu
```

Para ver los comandos disponibles:

```powershell
python -m centro_deportivo.main -h
```

Para ejecutar las pruebas:

```powershell
python -m unittest discover -s tests -v
```

## Datos de ejemplo

El estado inicial de `datos/state.json` esta vacio. Importa los datos de
ejemplo desde la raiz de esta carpeta:

```powershell
python -m centro_deportivo.main importar-alumnos datos/alumnos.csv
python -m centro_deportivo.main clase-cargar datos/clases.csv
python -m centro_deportivo.main clase-listar
```

`datos/alumnos_errores.csv` contiene filas incompletas para probar los mensajes
de validacion. El programa guarda los cambios en `datos/state.json` y crea
automaticamente la carpeta `reportes` cuando se genera un reporte.

Los horarios de `datos/clases.csv` son ejemplos; actualizalos a fechas futuras
si vas a demostrar reservaciones.
