from flask import Flask, render_template, request, redirect, session, url_for
import cx_Oracle
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
from database import init_db, register_user, login_user, create_product, get_products, delete_product, get_sessions


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Güvenlik amacıyla rastgele bir anahtar kullanın

# Oracle veritabanı bağlantısını başlatın
def get_db_connection():
    conn = cx_Oracle.connect(
        user='',
        password='',
        dsn='',
        mode=cx_Oracle.SYSDBA  # SYSDBA yetkisiyle bağlanma
    )
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = login_user(conn, username, password)
        if user:
            session['user_id'] = user[0]
            session['role'] = user[3]

            # Kullanıcı oturum açarsa session'ı kaydedin
            cursor = conn.cursor()
            cursor.execute("INSERT INTO oturumlar (user_id, login_time) VALUES (:1, SYSTIMESTAMP)", (user[0],))
            conn.commit()
            cursor.close()

            conn.close()
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            return "Invalid username or password", 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        conn = get_db_connection()
        register_user(conn, username, password, role)
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user_id = session['user_id']
    role = session.get('role')

    if request.method == 'POST':
        product_name = request.form.get('product_name')
        if product_name:
            create_product(conn, user_id, product_name)

    # Admin ise tüm ürünleri listele, değilse sadece kendi ürünlerini listele
    if role == 'admin':
        products = get_products(conn, None)  # Admin tüm ürünleri görebilir
        sessions = get_sessions(conn)  # Admin tüm oturumları görebilir
        graph_url = generate_login_activity_graph(conn)
        candlestick_graph_url = generate_candlestick_chart_for_active_users(conn)
    else:
        products = get_products(conn, user_id)  # Normal kullanıcı sadece kendi ürünlerini görür
        sessions = None
        graph_url = None
        candlestick_graph_url = None

    conn.close()

    if role == 'admin':
        return render_template('admin_dashboard.html', products=products, sessions=sessions, graph_url=graph_url, candlestick_graph_url=candlestick_graph_url)

    return render_template('dashboard.html', products=products)

@app.route('/delete_product/<int:product_id>')
def delete_product_route(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_role = session.get('role')
    if user_role != 'admin':
        return "You do not have permission to perform this action", 403

    conn = get_db_connection()
    delete_product(conn, product_id)
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('index'))

def generate_login_activity_graph(conn):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.user_id, COUNT(*)
        FROM oturumlar o
        WHERE o.login_time > SYSDATE - INTERVAL '1' HOUR
        GROUP BY o.user_id
        HAVING COUNT(*) > 3
    """)

    data = cursor.fetchall()
    cursor.close()

    user_ids = [str(row[0]) for row in data]
    login_counts = [row[1] for row in data]

    plt.figure(figsize=(10, 6))
    plt.bar(user_ids, login_counts, color='green')
    plt.xlabel('User ID')
    plt.ylabel('Login Count')
    plt.title('Users with more than 3 logins in the last hour')

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    graph_url = base64.b64encode(img.getvalue()).decode()

    plt.close()

    return graph_url

def generate_candlestick_chart_for_active_users(conn):
    cursor = conn.cursor()

    # Son bir saatte 3'ten fazla giriş yapmış kullanıcıları bul
    cursor.execute("""
        SELECT user_id
        FROM oturumlar
        WHERE login_time > SYSDATE - INTERVAL '1' HOUR
        GROUP BY user_id
        HAVING COUNT(*) > 3
    """)
    active_users = [row[0] for row in cursor.fetchall()]

    if not active_users:
        return None

    # Sadece bugünün oturumlarını saat bazında grupluyoruz
    cursor.execute(f"""
        SELECT user_id, TO_CHAR(login_time, 'HH24') AS hour, COUNT(*) AS session_count
        FROM oturumlar
        WHERE TRUNC(login_time) = TRUNC(SYSDATE)
        AND user_id IN ({','.join(map(str, active_users))})
        GROUP BY user_id, TO_CHAR(login_time, 'HH24')
        ORDER BY user_id, hour
    """)

    data = cursor.fetchall()
    cursor.close()

    unique_users = sorted(set([row[0] for row in data]))

    plt.figure(figsize=(10, 6))
    for user_id in unique_users:
        user_data = [(int(row[1]), row[2]) for row in data if row[0] == user_id]

        hours = [d[0] for d in user_data]
        session_counts = [d[1] for d in user_data]

        plt.plot(hours, session_counts, marker='o', linestyle='-', label=f'User {user_id}')

    plt.fill_between(hours, session_counts, color='green', alpha=0.3)
    plt.xlabel('Hour of the Day')
    plt.ylabel('Number of Sessions')
    plt.title('24-Hour Session Activity for Active Users')
    plt.grid(True)
    plt.xticks(range(0, 24))
    plt.legend()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    candlestick_graph_url = base64.b64encode(img.getvalue()).decode()

    plt.close()

    return candlestick_graph_url

@app.route('/admin_dashboard')
def admin_dashboard():
    conn = get_db_connection()
    if conn is None:
        return "Database connection could not be established", 500  # Bağlantı hatası durumunda 500 hatası döndür

    try:
        products = get_products(conn, None)
        sessions = get_sessions(conn)
        graph_url = generate_login_activity_graph(conn)
        candlestick_graph_url = generate_candlestick_chart_for_active_users(conn)
        conn.close()
    except Exception as e:
        conn.close()
        return f"An error occurred: {str(e)}", 500

    return render_template('admin_dashboard.html', products=products, sessions=sessions, graph_url=graph_url, candlestick_graph_url=candlestick_graph_url)
def insert_sample_data_safe(conn):
    data = [
        (0, 1, 'A', 'transport lag', '0 00:00:07', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 1, 'A', 'apply lag', '0 00:00:09', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 1, 'A', 'apply finish time', '0 00:00:01', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 2, 'B', 'apply lag', '0 00:00:07', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 3, 'C', 'transport lag', '0 00:00:04', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 4, 'D', 'apply lag', '0 00:00:09', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 3, 'C', 'apply lag', '0 00:00:01', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 5, 'E', 'apply lag', '0 00:00:04', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 2, 'B', 'transport lag', '0 00:00:54', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 15, 'P', 'apply lag', '0 00:00:25', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 6, 'F', 'transport lag', '0 00:00:09', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 8, 'G', 'apply lag', '0 00:00:01', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 4, 'D', 'transport lag', '0 00:00:07', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 9, 'H', 'apply lag', '0 00:00:08', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 2, 'B', 'apply finish time', '0 00:00:01', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 17, 'T', ' apply lag ', '0 00:00:04', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 20, 'Y', 'transport lag', '0 00:00:09', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 26, 'U', 'apply lag ', '0 00:00:40', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 5, 'E', 'apply lag', '0 00:00:03', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 6, 'F', 'apply lag', '0 00:00:05', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 8, 'G', 'transport lag', '0 00:00:07', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 10, 'I', 'apply lag', '0 00:00:03', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 11, 'J', 'transport lag', '0 00:00:10', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 12, 'K', 'apply lag', '0 00:00:04', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 13, 'L', 'transport lag', '0 00:00:03', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0),
        (0, 14, 'M', 'apply lag', '0 00:00:09', 'day(2) to second(0) interval', '09-APR-2024 13:48:58',
         '09-APR-2024 13:48:58', 0)
    ]

    cursor = conn.cursor()
    for entry in data:
        # Veritabanında zaten var olan verileri kontrol et
        cursor.execute("""
            SELECT COUNT(*) FROM dataguard_gap_ekrani
            WHERE SOURCE_DB_UNIQUE_NAME = :1 AND NAME = :2
        """, (entry[2], entry[3]))

        result = cursor.fetchone()
        if result[0] == 0:  # Eğer veri yoksa, yeni veriyi ekle
            cursor.execute("""
                INSERT INTO dataguard_gap_ekrani (INST_ID, SOURCE_DBID, SOURCE_DB_UNIQUE_NAME, NAME, VALUE, UNIT, TIME_COMPUTED, DATUM_TIME, CON_ID)
                VALUES (:1, :2, :3, :4, TO_DSINTERVAL(:5), :6, TO_DATE(:7, 'DD-MON-YYYY HH24:MI:SS'), TO_DATE(:8, 'DD-MON-YYYY HH24:MI:SS'), :9)
            """, entry)
            conn.commit()
    cursor.close()






@app.route('/view_high_lag')
def view_high_lag():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Sadece 6 saniyeden büyük gecikmeleri çekiyoruz ve saniye cinsinden değer hesaplıyoruz
    cursor.execute("""
        SELECT SOURCE_DB_UNIQUE_NAME, NAME, EXTRACT(SECOND FROM VALUE) + EXTRACT(MINUTE FROM VALUE) * 60 AS total_seconds
        FROM dataguard_gap_ekrani
        WHERE EXTRACT(SECOND FROM VALUE) + EXTRACT(MINUTE FROM VALUE) * 60 > 6
    """)

    data = cursor.fetchall()
    cursor.close()
    conn.close()

    if not data:
        # Eğer uygun veri yoksa, kullanıcıya bilgi ver
        return render_template('view_high_lag.html', message="No data found with lag greater than 6 seconds.")

    # Verileri gruplama ve etiketleri formatlama
    labels = [f"{row[0]}-{row[1]}" for row in data]
    values = [row[2] for row in data]  # Saniye cinsinden değerler

    # Bar grafiği oluşturma
    plt.figure(figsize=(10, 6))  # Grafik boyutunu genişlet
    plt.bar(labels, values, color='orange')

    plt.ylabel('Lag (Seconds)')

    plt.ylim(1, 100)  # Y ekseni sınırlarını 1 ile 100 arasında ayarla

    # Etiketleri 90 derece döndürme ve boyut ayarlama
    plt.xticks(rotation=45, ha='right', fontsize=7)  # Etiketleri dik konumda ve küçük boyutta yap

    # Grafiği HTML sayfasında göstermek için resim oluşturma
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    graph_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return render_template('view_high_lag.html', graph_url=graph_url)






if __name__ == '__main__':
    conn = get_db_connection()
    init_db(conn)
    insert_sample_data_safe(conn)  # Verileri eklemek için fonksiyonu çağır
    conn.close()
    app.run(host='', port=, debug=True)
