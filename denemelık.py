import cx_Oracle

def get_db_connection():
    conn = None
    try:
        conn = cx_Oracle.connect(
            user='',
            password='',
            dsn='',
            mode=cx_Oracle.SYSDBA  # SYSDBA yetki
        )
        print("Connection successful")
    except cx_Oracle.DatabaseError as e:
        print("Error connecting to database:", e)
    return conn

conn = get_db_connection()
if conn:
    # Bağlantı başarılıysa yapılacak işlemler
    conn.close()
else:
    print("Failed to connect to the database")
