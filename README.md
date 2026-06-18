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

#### Neo4j (Puertos `7687`)

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

### 2. Instalar Dependencias
Este proyecto utiliza `uv` para una gestión rápida y moderna de paquetes y entornos virtuales. Ejecuta en la raíz del proyecto:
```bash
uv sync
```
*Esto sincronizará el entorno virtual `.venv` instalando dependencias clave como `streamlit`, `pymongo` y `redis`.*

---

## 🏃‍♂️ Guía de Ejecución

El proyecto incluye scripts y herramientas de consola fáciles de operar:

### Paso A: Iniciar las Interfaces Web (Streamlit)
Las interfaces Streamlit estan en la raiz del proyecto. Cada una esta especializada por motor:

| Interfaz | Motor | Proposito | Comando |
| :--- | :--- | :--- | :--- |
| `mongo_app.py` | MongoDB + controlador multi-motor | CRUD operacional principal y sincronizacion hacia Redis, Neo4j y Cassandra. | `uv run streamlit run mongo_app.py` |
| `redis_app.py` | Redis | Inspeccion de keys, disponibilidad, locks, TTLs y metricas en memoria. | `uv run streamlit run redis_app.py` |
| `neo4j_app.py` | Neo4j | Exploracion del grafo, relaciones y recomendaciones. | `uv run streamlit run neo4j_app.py` |
| `cassandra_app.py` | Cassandra | Exploracion y consultas de tablas query-driven. | `uv run streamlit run cassandra_app.py` |

Para levantar una sola interfaz, ejecuta por ejemplo:
```bash
uv run streamlit run mongo_app.py
```

Para levantar todas al mismo tiempo, usa terminales separadas y puertos distintos:
```bash
uv run streamlit run mongo_app.py --server.port 8501
uv run streamlit run redis_app.py --server.port 8502
uv run streamlit run neo4j_app.py --server.port 8503
uv run streamlit run cassandra_app.py --server.port 8504
```

### Paso B: Importar Dataset Inicial
La inicializacion principal se realiza desde `mongo_app.py`, con el boton **Importar dataset**.

Ese flujo usa el controlador multi-motor (`services/multiengine_controller.py`) y lee directamente:

```text
mock_data/bemyguest_dataset.json
```

Al importar desde la interfaz de MongoDB:

* MongoDB recibe las colecciones completas (`usuarios`, `hoteles`, `habitaciones`, `reservas`, `resenas`).
* Redis se inicializa desde las habitaciones del mismo JSON, creando llaves como `habitacion:HAB0001:disponible`.
* Neo4j carga nodos y relaciones desde el mismo dataset.
* Cassandra carga sus tablas query-driven desde el mismo dataset.

### Paso C: Altas, Bajas y Sincronizacion Posterior
Despues de la importacion inicial, los cambios se hacen desde `mongo_app.py`.

MongoDB funciona como fuente operacional principal y el controlador sincroniza los motores complementarios:

* Si se crea una habitacion, se guarda en MongoDB y se crea/actualiza su disponibilidad en Redis.
* Si se crea una reserva confirmada, Redis marca la habitacion como no disponible, libera el lock e incrementa `stats:reservas:hoy`.
* Neo4j recibe nodos o relaciones para recomendaciones.
* Cassandra recibe las filas derivadas para consultas optimizadas.

---

## 📁 Estructura del Proyecto

* **`documentacion/`**: Carpeta dedicada que contiene la documentación técnica estructurada por versiones.
* **`mongodb/`**: Configuración de PyMongo y capas operacionales CRUD.
* **`redis_service/`**: Capa del servicio de Redis (`redis_service.py`).
* **`cassandradb/`**: Modelos (`models.py`), configuración e integración de Cassandra mediante `cassandra.cqlengine`.
* **`implementacion_neo4j/`**: Servicio de ingesta y validación para las recomendaciones en grafos.
* **`mock_data/`**: Almacena el dataset estático consolidado `bemyguest_dataset.json`.
* **`services/`**: Controlador de sincronizacion multi-motor usado por la interfaz de MongoDB para importar el dataset y reflejar altas/bajas.

* **`mongo_app.py`**: Interfaz operacional principal. Guarda primero en MongoDB y refleja altas/bajas en los motores complementarios.
* **`redis_app.py`**: Interfaz especializada para cache, disponibilidad, locks y TTLs.
* **`neo4j_app.py`**: Interfaz especializada para grafo, relaciones y recomendaciones.
* **`cassandra_app.py`**: Interfaz especializada para tablas query-driven y consultas optimizadas.

---
