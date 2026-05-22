# BeMyGuest

![Logo](be_my_guest.png)

Un sistema que permite a los usuarios buscar habitaciones, recibir recomendaciones personalizadas y gestionar sus reservas, similar a la aplicación Airbnb. A nivel backend, el sistema requiere manejar catálogos con descripciones variables, controlar la disponibilidad con latencia ultrabaja para evitar el overbooking (sobreventa), procesar recomendaciones basadas en el comportamiento de usuarios similares y registrar un historial inmutable y masivo de todas las transacciones y movimientos.

## Ejecutar la interfaz

1. Verificar que MongoDB este corriendo en `localhost:27017`.
2. Instalar dependencias con `uv sync`.
3. Iniciar Streamlit:

```bash
uv run streamlit run streamlit_app.py
```

La interfaz permite generar datos de prueba, explorar las colecciones y limpiar documentos seleccionados.
