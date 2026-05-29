**Hotelería (Airbnb) - BeMyGuest**

MongoDB: habitaciones, fotos y servicios

\- Los hoteles, habitaciones y servicios tienen atributos muy variables (por ejemplo, una suite VIP tiene características distintas a una habitación estándar o a una cabaña). MongoDB, al tener un esquema flexible basado en JSON/BSON, permite almacenar estos perfiles estructurados de forma jerárquica sin las restricciones de las tablas rígidas

Redis: disponibilidad en tiempo real

\- Para la disponibilidad de las habitaciones en tiempo real y el carrito temporal de reservas, se requiere velocidad extrema

. Redis gestionará la información de la sesión del usuario (quién está logueado)

y bloqueará temporalmente una habitación mientras el usuario completa el pago, aprovechando su estructura en memoria y sus capacidades de expiración de claves (TTL)

Neo4j: relaciones y preferencias de clientes

\- Es el motor ideal para modelar relaciones complejas

. Se modelarán nodos de tipo Usuario, Hotel y Categoria, conectados por relaciones como SE_HOSPEDÓ_EN, LE_GUSTA o VIAJA_CON. Esto permite aplicar algoritmos de filtrado colaborativo (sistemas de recomendación), sugiriendo a un usuario hoteles que visitaron otros clientes con gustos o perfiles similares

Cassandra: registros masivos de reservas y actividad

\- En una plataforma global de hotelería, se generan millones de eventos diarios (búsquedas, cancelaciones, facturación, auditorías). Cassandra está diseñada para alta escritura, alta disponibilidad y escalabilidad masiva

. Almacenará el registro histórico inmutable de toda la actividad del sistema, permitiendo consultas rápidas por columnas específicas (como fechas o IDs de usuario)