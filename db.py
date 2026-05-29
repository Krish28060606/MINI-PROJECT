<<<<<<< HEAD
import os
import psycopg2


def get_connection():
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is missing")

    return psycopg2.connect(db_url, sslmode="require")
=======
import os
import psycopg2


def get_connection():
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is missing")

    return psycopg2.connect(db_url, sslmode="require")
>>>>>>> 6812e93b1ddf4ed58ed91d9a4f073488da186c65
