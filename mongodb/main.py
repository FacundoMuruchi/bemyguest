try:
    from .mongo import *
except:
    from mongo import *

eliminar_todos_documentos(col_hoteles)
eliminar_todos_documentos(col_habitaciones)
eliminar_todos_documentos(col_reservas)
eliminar_todos_documentos(col_reseñas)
eliminar_todos_documentos(col_usuarios)

insertar_usuarios_faker(4)
insertar_hoteles_faker(4)
insertar_habitaciones_faker(col_hoteles.distinct("_id"), 2)
insertar_reservas_faker(4)
insertar_resenas_faker(4)

mostrar_documentos(doc_usuarios)
mostrar_documentos(doc_hoteles)
mostrar_documentos(doc_habitaciones)
mostrar_documentos(doc_reservas)
mostrar_documentos(doc_reseñas)