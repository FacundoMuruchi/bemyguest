# 🏨 BeMyGuest — Plataforma Administrativa de Hotelería NoSQL

![BeMyGuest Logo](be_my_guest.png)

**BeMyGuest** es una plataforma de gestión hotelera y alquileres temporales (estilo Airbnb) diseñada como solución integral multi-motor NoSQL para la asignatura **Ingeniería de Datos II** (UADE). 

El sistema demuestra cómo resolver las distintas necesidades de negocio (catálogos flexibles, transacciones en tiempo real, análisis de relaciones y auditorías masivas) acoplando cuatro motores de base de datos no relacionales, donde cada uno actúa bajo su especialidad técnica.

---

## 🏛️ Arquitectura de Motores NoSQL

| Motor | Rol en el Negocio | Justificación Técnica | Estado (v1.0) |
| :--- | :--- | :--- | :--- |
| **🗄️ MongoDB** | **Fuente Única de Verdad (operacional)** | Esquema flexible (JSON/BSON) para almacenar perfiles de habitaciones con amenities muy variables y datos operacionales principales. | **Implementado** |
| **⚡ Redis** | **Cache de disponibilidad y Concurrencia** | Gestión en memoria RAM con expiración de claves (TTL) para bloqueos temporales de habitación (*pessimistic locking*) y anti-overbooking. | **Implementado** |
| **🕸️ Neo4j** | **Relaciones y Recomendaciones** | Modelado en grafo de usuarios, hoteles y categorías para filtros colaborativos en tiempo real. | *Próxima Fase* |
| **📊 Cassandra** | **Logs históricos y Auditoría masiva** | Motor orientado a columnas optimizado para alta tasa de escritura de eventos de actividad e historial inmutable. | *Próxima Fase* |

---

## 🚀 Funcionalidades Clave de la Versión Actual (v1.0)

1. **🔌 Panel de Diagnóstico NoSQL**: Indicadores en tiempo real en la barra lateral que analizan la conexión con MongoDB y Redis de manera automática.
2. **🔒 Flujo de Checkout Resiliente (Pessimistic Locking)**:
   * Al iniciar una reserva, se adquiere un **bloqueo temporal en Redis** con un **TTL de 10 minutos**.
   * Durante ese tiempo, la habitación se muestra visualmente como `BLOQUEADA (Reservando...)` en toda la interfaz, impidiendo que otros usuarios la compren (cero overbooking).
   * Al confirmar la transacción, se persiste la reserva en MongoDB, se actualiza el estado de disponibilidad y se libera el lock en Redis de forma atómica.
   * Cuenta con **modo degradado**: si Redis está apagado, el sistema sigue funcionando de forma directa contra MongoDB.
3. **📊 Métricas Rápidas**: Contador dinámico de reservas exitosas procesadas en el día, leídas velozmente desde la memoria caché.
4. **🛠️ Dataset Homologado de Calidad**:
   * Más de **1,500 registros** limpios de prueba (usuarios, hoteles, reservas y reseñas) interrelacionados.
   * Soporte completo para caracteres especiales (tildes, eñes) y nombres realistas localizados en español (`es_AR`).

---

## 💻 Requisitos y Preparación

### 1. Iniciar los Motores NoSQL
Asegúrate de tener corriendo los servicios en tu máquina local:

#### MongoDB (Puerto `27017`)
Asegúrate de tener MongoDB levantado en su puerto estándar.

#### Redis (Puerto `6379`)
Si usas **Docker Desktop**, puedes levantarlo en un segundo con:
```bash
docker run -d --name redis-bemyguest -p 6379:6379 redis:alpine
```
Si usas **WSL (Ubuntu)**:
```bash
sudo service redis-server start
```

### 2. Instalar Dependencias
Este proyecto utiliza `uv` para una gestión rápida y moderna de paquetes y entornos virtuales. Ejecuta en la raíz del proyecto:
```bash
uv sync
```
*Esto sincronizará el entorno virtual `.venv` instalando dependencias clave como `streamlit`, `pymongo` y `redis`.*

---

## 🏃‍♂️ Guía de Ejecución

El proyecto incluye scripts y herramientas de consola fáciles de operar:

### Paso A: Importar Dataset a MongoDB
Limpia la base de datos e inyecta el mock dataset de 1,500 registros:
```bash
uv run scripts/import_mock_dataset.py
```

### Paso B: Sincronizar Disponibilidad con Redis (*Seeding*)
Lee el catálogo de habitaciones de MongoDB y carga su estado en la caché de Redis:
```bash
uv run redis_service/seed_redis.py
```
*(También puedes realizar este seeding con un solo clic presionando el botón en la barra lateral de la interfaz gráfica).*

### Paso C: Iniciar la Interfaz Web (Streamlit)
Lanza el panel administrativo interactivo de BeMyGuest:
```bash
uv run streamlit run streamlit_app.py
```

---

## 📁 Estructura del Proyecto

* **`documentacion/`**: Carpeta dedicada **exclusivamente a archivos Markdown (`.md`)** que contiene la documentación técnica estructurada por versiones.
* **`mongodb/`**: Configuración de PyMongo y capas operacionales CRUD.
* **`redis_service/`**: Capa del servicio de Redis (`redis_service.py`), plano técnico (`plan_redis.md`) y cargador inicial (`seed_redis.py`).
* **`mock_data/`**: Almacena el dataset estático consolidado `bemyguest_dataset.json`.
* **`scripts/`**: Utilidades CLI para generación e importación reproducible de datos de prueba.
* **`streamlit_app.py`**: Interfaz de usuario interactiva y panel de administración unificado.

---

## 📖 Documentación Relacionada
Para profundizar en los aspectos técnicos de la arquitectura, revisa nuestra carpeta interna:
* [📚 Índice de Documentación](./documentacion/README.md)
* [📁 Detalle Técnico Versión 1.0 (v.1)](./documentacion/v.1/README.md)
