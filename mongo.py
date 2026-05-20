from pymongo import MongoClient

client = MongoClient("localhost", 27017)
db = client["bemyguest"]
hoteles = db["hoteles"]
habitaciones = db["habitaciones"]
servicios = db["servicios"]