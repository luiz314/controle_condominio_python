from flask import Flask, render_template, request, redirect, session, send_file
import psycopg2
from datetime import datetime, timedelta
import os
import subprocess
import config
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "segredo"
app.permanent_session_lifetime = timedelta(hours=2)

BACKUP_DIR = "/home/luiz/controle-condominio/backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

def get_db():
    return psycopg2.connect(
        host=config.DB_HOST,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASS
    )

# ================= LOGIN =================
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    user = request.form.get('username')
    password = request.form.get('password')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM usuarios WHERE username=%s", (user,))
            result = cur.fetchone()

    if result and check_password_hash(result[0], password):
        session['user'] = user
        return redirect('/dashboard')

    return "Login inválido"

# ================= DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html')

# ================= CADASTRAR =================
@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':
        nome = request.form.get('nome')
        documento = request.form.get('documento')
        telefone = request.form.get('telefone')

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO pessoas (nome, documento, telefone) VALUES (%s, %s, %s)",
                    (nome, documento, telefone)
                )

        return redirect('/listar')

    return render_template('cadastrar.html')

# ================= LISTAR =================
@app.route('/listar')
def listar():
    if 'user' not in session:
        return redirect('/')

    busca = request.args.get('busca', '')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id,
                    p.nome,
                    p.documento,
                    CASE 
                        WHEN a.id IS NULL THEN false
                        WHEN a.data_saida IS NULL THEN true
                        ELSE false
                    END AS dentro
                FROM pessoas p
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM acessos a
                    WHERE a.pessoa_id = p.id
                    ORDER BY a.data_entrada DESC
                    LIMIT 1
                ) a ON true
                WHERE p.nome ILIKE %s
                ORDER BY p.nome
            """, (f"%{busca}%",))

            pessoas = cur.fetchall()

    return render_template('listar.html', pessoas=pessoas, busca=busca)

# ================= ENTRADA =================
@app.route('/entrada/<int:id>')
def entrada(id):
    if 'user' not in session:
        return redirect('/')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM acessos
                WHERE pessoa_id = %s AND data_saida IS NULL
            """, (id,))

            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO acessos (pessoa_id, data_entrada)
                    VALUES (%s, %s)
                """, (id, datetime.now()))

    return redirect('/listar')

# ================= SAÍDA =================
@app.route('/saida/<int:id>')
def saida(id):
    if 'user' not in session:
        return redirect('/')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE acessos
                SET data_saida = %s
                WHERE id = (
                    SELECT id FROM acessos
                    WHERE pessoa_id = %s AND data_saida IS NULL
                    ORDER BY data_entrada DESC
                    LIMIT 1
                )
            """, (datetime.now(), id))

    return redirect('/listar')

# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':
        user = request.form.get('username')
        password = generate_password_hash(request.form.get('password'))

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO usuarios (username, password) VALUES (%s, %s)",
                    (user, password)
                )

        return redirect('/dashboard')

    return render_template('register.html')

# ================= BACKUP =================
@app.route('/backup')
def backup_page():
    if 'user' not in session:
        return redirect('/')

    files = sorted(os.listdir(BACKUP_DIR), reverse=True)[:5]
    return render_template('backup.html', backups=files)

@app.route('/backup/create')
def create_backup():
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    path = os.path.join(BACKUP_DIR, filename)

    env = os.environ.copy()
    env["PGPASSWORD"] = config.DB_PASS

    try:
        with open(path, "w") as f:
            subprocess.run([
                "pg_dump",
                "-U", config.DB_USER,
                "--no-owner",
                "--no-privileges",
                config.DB_NAME
            ], stdout=f, stderr=subprocess.PIPE, env=env, check=True)

    except subprocess.CalledProcessError as e:
        return f"Erro no backup: {e.stderr.decode()}"

    return redirect('/backup')

# ================= RESTORE (CORREÇÃO AQUI) =================
@app.route('/backup/restore', methods=['POST'])
def restore_backup():
    file = request.files.get('file')
    path = os.path.join(BACKUP_DIR, file.filename)
    file.save(path)

    env = os.environ.copy()
    env["PGPASSWORD"] = config.DB_PASS

    try:
        # 🔥 Limpa o banco antes (sem dropar database)
        subprocess.run([
            "psql",
            "-U", config.DB_USER,
            "-d", config.DB_NAME,
            "-c",
            """
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            """
        ], env=env, check=True)

        # 🔥 Restore limpo
        subprocess.run([
            "psql",
            "-U", config.DB_USER,
            "-d", config.DB_NAME,
            "-f", path
        ], stderr=subprocess.PIPE, env=env, check=True)

    except subprocess.CalledProcessError as e:
        return f"Erro no restore: {e.stderr.decode()}"

    return redirect('/backup')

@app.route('/backup/download/<filename>')
def download_backup(filename):
    return send_file(os.path.join(BACKUP_DIR, filename), as_attachment=True)

# ================= GERENCIAR =================
@app.route('/gerenciar')
def gerenciar():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username FROM usuarios ORDER BY username")
            usuarios = cur.fetchall()

            cur.execute("SELECT id, nome, documento, telefone FROM pessoas ORDER BY nome")
            pessoas = cur.fetchall()

    return render_template('gerenciar.html', usuarios=usuarios, pessoas=pessoas)

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)