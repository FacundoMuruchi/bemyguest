# 🗄️ Módulo: Persistencia MongoDB (`/mongodb`)

Este módulo encapsula todas las llamadas, configuraciones y operaciones lógicas destinadas a **MongoDB**, el cual funciona como el motor de persistencia relacional-documental principal (Source of Truth) de **BeMyGuest**.

---

## 🏗️ Componentes del Módulo

### 1. `config.py` (Configuración e Inicialización)
* **Instanciación**: Crea el cliente de PyMongo (`MongoClient`) parametrizado por defecto en `localhost` con el puerto `27017` y un timeout estricto de conexión de 2 segundos (`serverSelectionTimeoutMS=2000`).
* **Base de Datos**: Selecciona la base de datos principal denominada `bemyguest`.
* **Colecciones Declaradas**:
  * `col_usuarios`: Almacena documentos de usuarios.
  * `col_hoteles`: Almacena la información de los establecimientos hoteleros.
  * `col_habitaciones`: Estructura las habitaciones asociadas a sus hoteles.
  * `col_reservas`: Guarda el historial de transacciones de reservas de estadías.
  * `col_resenas`: Resguarda las calificaciones y comentarios escritos de los huéspedes.

> [!IMPORTANT]
> **Cambio Crítico en v.1**: Se renombró la variable y referencia física de la colección de reseñas. Pasó de denominarse `reseñas` (con eñe) a `resenas` (con `n`) para garantizar total compatibilidad de nombres de base de datos en múltiples entornos operativos.

---

### 2. `mongo.py` (Librería de Funciones CRUD y Utilidades)
Centraliza las operaciones del driver para mantener un código limpio y desacoplado del frontend:

* **`crear_coleccion(nombre)`**: Verifica de forma segura si una colección ya existe en la base de datos antes de intentar crearla, evitando excepciones en caliente.
* **`insertar_documento(collection, documento)`**: Wrapper de inserción directa de documentos individuales (`insert_one`).
* **`eliminar_documento(collection, criterio)`**: Permite eliminar un documento específico usando filtros de MongoDB (`delete_one`).
* **`eliminar_todos_documentos(collection)`**: Wrapper de eliminación masiva (`delete_many({})`).
* **`importar_dataset_json(path, reset_first)`**:
  * Lee un archivo JSON del dataset estático.
  * Valida la estructura mediante `validar_dataset()`.
  * Si `reset_first` es `True`, limpia de forma segura las 5 colecciones operativas.
  * Ejecuta una inserción masiva y atómica por colección utilizando `insert_many()`, lo que acelera dramáticamente los tiempos de carga del seeding de la aplicación.

---

### 3. `main.py` (Script de Entrada Directo)
* Proporciona un punto de acceso directo de consola para el módulo.
* Al ejecutar `python mongodb/main.py`, se lee automáticamente el dataset ubicado en `mock_data/bemyguest_dataset.json`, se limpia la base de datos MongoDB local, se inyectan los 1,500 registros y se imprime un reporte consolidado con el conteo final de cada colección en la consola.
