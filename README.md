# 🏨 BeMyGuest — Plataforma Administrativa de Hotelería NoSQL

![BeMyGuest Logo](be_my_guest.png)

**BeMyGuest** es una plataforma de gestión hotelera y alquileres temporales (estilo Airbnb) diseñada como solución integral multi-motor NoSQL para la asignatura **Ingeniería de Datos II** (UADE). 

El sistema demuestra cómo resolver las distintas necesidades de negocio (catálogos flexibles, transacciones en tiempo real, análisis de relaciones y auditorías masivas) acoplando cuatro motores de base de datos no relacionales, donde cada uno actúa bajo su especialidad técnica.

---

## 🏛️ Arquitectura de Motores NoSQL

| Motor | Rol en el Negocio | Justificación Técnica |
| :--- | :--- | :--- |
| **🗄️ MongoDB** | **Fuente Única de Verdad (operacional)** | Esquema flexible (JSON/BSON) para almacenar perfiles de habitaciones con amenities muy variables y datos operacionales principales. | **Implementado** |
| **⚡ Redis** | **Cache de disponibilidad y Concurrencia** | Gestión en memoria RAM con expiración de claves (TTL) para bloqueos temporales de habitación (*pessimistic locking*) y anti-overbooking. | **Implementado** |
| **🕸️ Neo4j** | **Relaciones y Recomendaciones** | Modelado en grafo de usuarios, hoteles y categorías para filtros colaborativos en tiempo real. | **Implementado** |
| **📊 Cassandra** | **Consultas Optimizadas** | Motor orientado a columnas optimizado para consultas rápidas precalculadas (Query-Driven Design). | **Implementado** |

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

#### Cassandra (Puerto `9042`)
Para las consultas optimizadas en columnas, levanta un nodo con:
```bash
docker run --name cassandra-bemyguest -p 9042:9042 -d cassandra:latest
```

#### Neo4j (Puertos `7687` y `7474`)
Para el motor de recomendaciones basado en grafos:
```bash
docker run --name neo4j-bemyguest -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=none -d neo4j:latest
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

### Paso C: Iniciar la Interfaz Web (Streamlit)
Lanza el panel administrativo interactivo de BeMyGuest:
```bash
uv run streamlit run streamlit_app.py
```

---

## 📁 Estructura del Proyecto

* **`documentacion/`**: Carpeta dedicada que contiene la documentación técnica estructurada por versiones.
* **`mongodb/`**: Configuración de PyMongo y capas operacionales CRUD.
* **`redis_service/`**: Capa del servicio de Redis (`redis_service.py`), plano técnico (`plan_redis.md`) y cargador inicial (`seed_redis.py`).
* **`cassandradb/`**: Modelos (`models.py`), configuración e integración de Cassandra mediante `cassandra.cqlengine`.
* **`implementacion_neo4j/`**: Servicio de ingesta y validación para las recomendaciones en grafos.
* **`mock_data/`**: Almacena el dataset estático consolidado `bemyguest_dataset.json`.
* **`scripts/`**: Utilidades CLI para generación e importación reproducible de datos de prueba.
* **`streamlit_app.py`**: Interfaz de usuario interactiva y panel de administración unificado.

---