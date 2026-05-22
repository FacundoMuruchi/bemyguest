from pymongo import MongoClient

client = MongoClient("localhost", 27017, serverSelectionTimeoutMS=2000)

db = client["bemyguest"]

col_hoteles = db["hoteles"]
col_habitaciones = db["habitaciones"]
col_reservas = db["reservas"]
col_resenas = db["resenas"]
col_usuarios = db["usuarios"]

doc_hoteles = col_hoteles.find()
doc_habitaciones = col_habitaciones.find()
doc_reservas = col_reservas.find()
doc_resenas = col_resenas.find()
doc_usuarios = col_usuarios.find()
