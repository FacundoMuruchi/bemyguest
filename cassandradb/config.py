from cassandra.cluster import Cluster
from cassandra.cqlengine import connection


cluster = Cluster(["127.0.0.1"])

session = cluster.connect()

session.execute("""
CREATE KEYSPACE IF NOT EXISTS bemyguest
WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
}
""")

session.set_keyspace("bemyguest")

connection.register_connection("default", session=session)

connection.set_default_connection("default")