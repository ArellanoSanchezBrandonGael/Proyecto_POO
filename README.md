
# Centro Deportivo Universitario

## Proyecto integrador de Programación Orientada a Objetos

Tema 4: Centro deportivo universitario.

## Integrantes

- Arellano Sánchez Brandon Gael
- Arteaga Pérez Zabdiel Didier
- Hernández Coronado Andrea Paola
- Juárez Soto Julio César

## Descripción

El proyecto consiste en un sistema de gestión para un centro deportivo universitario desarrollado en Python mediante programación orientada a objetos.

El sistema permite administrar socios, membresías, visitantes, accesos a las instalaciones, clases grupales y reservas. También permite generar reportes mensuales y simular una hora pico mediante hilos.

La información se almacena en archivos para conservar los datos entre ejecuciones.

## Requisitos

- Python 3.10 o superior.
- Git.
- Terminal o símbolo del sistema.

El proyecto utiliza únicamente la biblioteca estándar de Python, por lo que no requiere instalar paquetes externos.

## Instalación

Clonar el repositorio:

```bash
git clone https://github.com/ArellanoSanchezBrandonGael/Proyecto_POO.git
```

Entrar a la carpeta del proyecto:

```bash
cd Proyecto_POO
```

Verificar la versión de Python:

```bash
python --version
```

## Ejecución

Para iniciar el menú interactivo:

```bash
python -m centro_deportivo.main menu
```

Para consultar los comandos disponibles:

```bash
python -m centro_deportivo.main -h
```

## Funcionalidades

### Membresías

| Tipo | Precio | Áreas | Horario |
| --- | --- | --- | --- |
| Estudiante | $300 al mes | Gimnasio | Lunes a viernes, 7:00 a 15:00 |
| General | $700 al mes | Gimnasio | Horario del centro |
| Premium | $1100 al mes | Gimnasio, alberca y clases | Horario del centro |
| Visitante | $120 por día | Gimnasio | Horario del centro |

El centro deportivo abre de lunes a sábado de 6:00 a 22:00.

Para contratar o renovar una membresía estudiantil, el socio debe aparecer en el padrón de alumnos inscritos.

Las membresías mensuales se manejan mediante periodos de 30 días.

### Control de accesos

El sistema valida la vigencia de la membresía, el horario, las áreas permitidas y el aforo del gimnasio.

El gimnasio tiene una capacidad máxima de 60 personas. No se permiten entradas duplicadas ni salidas de personas que no se encuentren dentro del área.

### Clases y reservas

Las clases cuentan con un identificador, nombre, instructor, horario y cupo.

Las reservas pueden realizarse hasta 48 horas antes de la clase y cancelarse hasta 2 horas antes de su inicio.

Los socios que acumulen tres faltas en un mes reciben una suspensión de siete días para realizar reservas.

### Reportes

Se pueden generar reportes mensuales que incluyen:

- Ingresos por tipo de membresía y pases de visitante.
- Asistencia por clase.
- Ocupación del gimnasio al final de cada hora de apertura.

Los reportes se guardan como archivos de texto.

### Simulación de hora pico

Se utilizan hilos para simular cuatro torniquetes y varios socios intentando reservar lugares de una clase.

Las operaciones compartidas se protegen mediante bloqueos para evitar que se exceda el aforo o el cupo de las clases.

La simulación utiliza datos temporales independientes y no modifica los registros reales del centro deportivo.

## Ejemplos de uso

Los siguientes ejemplos utilizan fechas de prueba para comprobar las reglas del sistema sin depender de la fecha actual.

### 1. Importar alumnos inscritos

```bash
python -m centro_deportivo.main importar-alumnos datos/alumnos.csv
```

### 2. Registrar un socio

```bash
python -m centro_deportivo.main socio-alta --nombre Ana --apellido Lopez
```

El sistema genera un identificador para el socio.

En los siguientes ejemplos se utiliza SOC-0001. Si el sistema genera otro identificador, debe utilizarse el correspondiente.

### 3. Contratar una membresía

```bash
python -m centro_deportivo.main --datetime "2026-11-23 10:00" membresia SOC-0001 premium
```

### 4. Renovar una membresía

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" membresia SOC-0001 premium --accion renovar
```

### 5. Cambiar una membresía

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" membresia SOC-0001 general --accion cambiar
```

### 6. Registrar una entrada

```bash
python -m centro_deportivo.main --datetime "2026-11-24 11:00" acceso SOC-0001
```

### 7. Registrar una salida

```bash
python -m centro_deportivo.main --datetime "2026-11-24 12:00" acceso SOC-0001 --accion salida
```

### 8. Registrar un visitante

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" acceso VISITA-001
```

El sistema registra el pase diario y su cobro cuando el visitante entra por primera vez en el día.

### 9. Cargar clases

```bash
python -m centro_deportivo.main clase-cargar datos/clases.csv
```

Consultar las clases disponibles:

```bash
python -m centro_deportivo.main clase-listar
```

### 10. Reservar una clase

El socio debe contar con una membresía premium vigente.

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" membresia SOC-0001 premium --accion cambiar
```

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" reservar SOC-0001 YOGA02
```

El identificador de la clase y la fecha de operación deben ajustarse a los horarios mostrados al consultar las clases.


### 11. Cancelar una reserva

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" cancelar-reserva RES-000001
```

Se debe utilizar el folio generado al realizar la reserva y respetar el límite de anticipación.

Después, volvemos a reservar la clase para probar el registro de asistencia:

```bash
python -m centro_deportivo.main --datetime "2026-11-24 11:00" reservar SOC-0001 YOGA02
```

### 12. Registrar asistencia

```bash
python -m centro_deportivo.main --datetime "2026-11-26 08:30" pasar-lista YOGA02 SOC-0001 asistio
```

Para registrar una falta se utiliza la opción `falto` en lugar de `asistio`.

La reserva debe estar activa y la clase debe haber iniciado.

### 13. Consultar el estado de un socio

```bash
python -m centro_deportivo.main estado-socio SOC-0001
```

### 14. Generar el reporte mensual

```bash
python -m centro_deportivo.main reporte 2026-11
```

El reporte se genera dentro de la carpeta `reportes`.

### 15. Ejecutar la simulación

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" simular
```

Para probar también las reservas simultáneas debe existir una clase programada dentro de las siguientes 48 horas.

## Casos de rechazo

### Entrada fuera del horario

```bash
python -m centro_deportivo.main --datetime "2026-11-29 10:00" acceso PRUEBA-01
```

El sistema rechaza la entrada porque el centro deportivo permanece cerrado los domingos.

### Entrada duplicada

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" acceso PRUEBA-02
python -m centro_deportivo.main --datetime "2026-11-24 10:00" acceso PRUEBA-02
```

La segunda entrada debe ser rechazada.

### Salida sin entrada previa

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" acceso PRUEBA-03 --accion salida
```

El sistema informa que la persona no se encuentra dentro del área.

### Área no permitida para visitantes

```bash
python -m centro_deportivo.main --datetime "2026-11-24 10:00" acceso VISITA-002 --area alberca
```

El pase de visitante solamente permite el acceso al gimnasio.

### Archivo CSV con errores

```bash
python -m centro_deportivo.main importar-alumnos datos/alumnos_errores.csv
```

El sistema informa las filas rechazadas y el motivo correspondiente.

### Archivo inexistente

```bash
python -m centro_deportivo.main importar-alumnos datos/inexistente.csv
```

El programa informa que el archivo no fue encontrado.

## Pruebas unitarias

Para ejecutar las pruebas:

```bash
python -m unittest discover -s tests -v
```

Las pruebas comprueban las reglas de membresías, horarios, aforo, reservas, asistencia, persistencia, importación de archivos, reportes y concurrencia.

Actualmente el proyecto cuenta con 25 pruebas unitarias.

## Estructura del proyecto

```text
Proyecto_POO/
├── centro_deportivo/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── main.py
│   ├── models.py
│   ├── service.py
│   └── storage.py
├── datos/
│   ├── alumnos.csv
│   ├── alumnos_errores.csv
│   └── clases.csv
├── tests/
│   └── test_centro.py
├── docs/
│   ├── diseno.md
│   └── uml/
├── .gitignore
├── README.md
└── requirements.txt
```

### Módulos

- `models.py`: contiene las clases del sistema y sus reglas.
- `service.py`: coordina las operaciones del centro deportivo.
- `storage.py`: se encarga de la lectura y escritura de archivos.
- `exceptions.py`: contiene las excepciones propias del sistema.
- `main.py`: contiene el menú y los comandos de terminal.
- `test_centro.py`: contiene las pruebas unitarias.
- `datos/`: contiene los archivos CSV de ejemplo.
- `docs/`: contiene el documento de diseño y los diagramas UML.

El archivo `datos/state.json` se genera automáticamente al guardar información. Los archivos de estado, respaldos, archivos temporales y reportes generados se excluyen del repositorio mediante `.gitignore`.
