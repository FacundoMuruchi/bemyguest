from pymongo import MongoClient

client = MongoClient("localhost", 27017)

db = client["bemyguest"]

col_hoteles = db["hoteles"]
col_habitaciones = db["habitaciones"]
col_reservas = db["reservas"]
col_reseñas = db["reseñas"]

doc_hoteles = col_hoteles.find()
doc_habitaciones = col_habitaciones.find()
doc_reservas = col_reservas.find()
doc_reseñas = col_reseñas.find()