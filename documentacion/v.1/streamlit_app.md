# 🖥️ Módulo: Interfaz Streamlit (`streamlit_app.py`)

La interfaz de usuario del proyecto está construida sobre **Streamlit**, lo que permite tener un panel administrativo interactivo, ágil y de rápida visualización para gestionar todos los motores de base de datos desde un único punto.

---

## 📌 Funcionalidad Principal

El archivo `streamlit_app.py` expone el flujo administrativo del sistema a través de cuatro pestañas principales:

### 1. Cabecera y Dashboard Métrico
* **Control de Conexión**: En cada carga de página se ejecuta una validación rápida (`ping`) hacia MongoDB para asegurar que el motor de persistencia esté arriba. Si el ping falla, la UI muestra un aviso amigable y detiene la aplicación.
* **Métricas en Tiempo Real**: Muestra dinámicamente un contador de documentos activos en cada una de las colecciones principales mediante tarjetas visuales (`st.metric`).

### 2. Explorar Datos (Pestaña "Explorar datos")
* Permite al usuario seleccionar cualquier colección del sistema (`Usuarios`, `Hoteles`, `Habitaciones`, `Reservas`, `Reseñas`).
* Proporciona un buscador de texto completo en tiempo real (`search_text`) parametrizado para buscar dentro de múltiples campos clave de cada documento (por ejemplo: nombres de usuarios, ciudades de hoteles, números de habitación, etc.).
* Ofrece dos modos de visualización dinámica:
  1. **Vista de Tabla**: Mediante `pd.json_normalize(docs)` aplana las subestructuras JSON (como los amenities) en columnas estructuradas de un Dataframe interactivo de pandas.
  2. **Vista JSON**: Muestra los documentos crudos de manera formateada e interactiva para fines de auditoría técnica.

### 3. Registro de Documentos (Pestaña "Registrar documento")
Formularios interactivos que validan las reglas de negocio antes de enviar a MongoDB:
* **Usuarios**: Formulario básico (nombre, apellido, email, teléfono, ciudad, país).
* **Hoteles**: Formulario con multiselección de servicios e inputs específicos para categorías.
* **Habitaciones**: Selección dinámica basada en hoteles existentes en el sistema. Configuración de amenities avanzados (cama, metros cuadrados, vistas, TV smart, jacuzzi, terraza, etc.).
* **Reservas**: Selección dinámica de usuarios y habitaciones existentes. Automatiza el cálculo numérico de la estadía (`noches` basadas en check-in/out) y valida la capacidad permitida de huéspedes.
* **Reseñas**: Asocia usuarios con hoteles y permite calificar con sliders dinámicos múltiples aspectos (limpieza, atención, ubicación).

> [!NOTE]
> Todos los formularios permiten inyectar atributos personalizados ilimitados en formato JSON a través del campo **"Atributos adicionales en JSON"**, manteniendo la flexibilidad natural de MongoDB.

### 4. Generación y Carga de Datos (Pestaña "Cargar datos")
* Permite disparar el seeding masivo a MongoDB.
* Cuenta con soporte para importar el dataset estático limpio y estructurado de la versión 1.0.

### 5. Pestaña "Administrar"
* Permite la depuración masiva y controlada. Se pueden seleccionar colecciones específicas a limpiar mediante checkboxes de confirmación de seguridad para evitar pérdida de datos accidental.

---

## 🛠️ Estructura del Código Clave

* **`serialize_value` & `serialize_docs`**: Traducen tipos de datos complejos de BSON (como `ObjectId` de MongoDB) a strings estándar para que puedan ser renderizados por Streamlit o mostrados como JSON sin provocar fallos de serialización.
* **`run_engine_action`**: Redirecciona la salida de consola (`redirect_stdout`) a un objeto en memoria (`StringIO`), permitiendo capturar el output detallado del backend para mostrarlo al usuario directamente en la UI.
