# 🛠️ Módulo: Generador e Importador de Mock Dataset (`/scripts` y `/mock_data`)

Este módulo proporciona el entorno de datos inicial para el TPI de **BeMyGuest**, implementando un dataset estático pre-generado y determinista que reemplaza la antigua generación de datos aleatorios "al vuelo" basados en Faker.

---

## 🏗️ Estructura del Módulo

### 1. `/mock_data` (Almacenamiento de Datos)
* **`bemyguest_dataset.json`**:
  * Es el archivo fuente que almacena **1,500 documentos** estructurados bajo una jerarquía estricta.
  * Todas las relaciones entre colecciones (ej. `reserva_id` -> `habitacion_id` y `usuario_id`) están perfectamente cuadradas y validadas matemáticamente en el archivo JSON.
  * Utiliza textos localizados en español (`es_AR`), lo que provee de nombres realistas y soporte completo para caracteres con **tildes y eñes**.

---

### 2. `/scripts` (Herramientas de Automatización)

#### A. `generate_mock_dataset.py` (Script Generador)
Es la herramienta técnica para construir el dataset desde cero utilizando una **semilla matemática fija**:
* **Semilla Reproducible**: Usa `seed = 20260522`. Esto asegura que el dataset resultante sea idéntico en cada ejecución, eliminando discrepancias de datos aleatorios entre los desarrolladores del equipo.
* **Flujo de Construcción Jerárquico**:
  1. Genera **60 Hoteles** con servicios aleatorios del pool.
  2. Genera **300 Habitaciones** distribuyendo de forma equitativa 5 habitaciones por cada hotel registrado, definiendo amenities, metros cuadrados y precios realistas.
  3. Genera **300 Usuarios** asegurándose de no repetir emails bajo un set de control único.
  4. Genera **600 Reservas** seleccionando usuarios y habitaciones al azar, calculando la diferencia exacta en días de check-in/check-out y validando que la cantidad de huéspedes no supere el límite de la habitación.
  5. Genera **240 Reseñas** vinculando un usuario con un hotel calificado.
* **Capa de Validación Fuerte**: Antes de escribir el archivo JSON, el script simula la base de datos completa en memoria y ejecuta tests de integridad referencial:
  * Comprobación de unicidad absoluta de todos los IDs (`USRXXXX`, `HOTXXXX`, `HABXXXX`, etc.).
  * Verificación de consistencia de fechas (ej: check-out estrictamente posterior a check-in).
  * Validación de correspondencia de llaves foráneas (`hotel_id` de reserva coincide exactamente con el `hotel_id` de la habitación reservada).

#### B. `import_mock_dataset.py` (Script Importador CLI)
Una utilidad CLI que permite al programador restaurar su base de datos local con un solo comando rápido en la terminal:
* **Uso**: `python scripts/import_mock_dataset.py [--dataset <ruta_personalizada>]`.
* **Seguridad**: Captura de forma segura excepciones de red, como el tiempo de espera por servidor MongoDB no disponible (`ServerSelectionTimeoutError`) o errores internos de driver (`PyMongoError`), imprimiendo reportes informativos limpios por consola.
* **Consolidación**: Imprime la lista de registros inyectados detallados por cada colección al terminar la importación de manera limpia.
