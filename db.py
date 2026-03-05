import psycopg2

def get_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="ai_creative",
        user="postgres",
        password="282006",   # change if different
        port="5432"
    )
    return conn