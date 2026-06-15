from flask import Flask, render_template, request, redirect, session, send_file, jsonify
import psycopg2
from datetime import datetime, timedelta
import os
import subprocess
import config
import logging
import re
import threading
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "segredo_muito_seguro_troque_em_producao"
app.permanent_session_lifetime = timedelta(hours=2)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")
LOG_FILE = os.path.join(os.path.dirname(__file__), "app.log")
os.makedirs(BACKUP_DIR, exist_ok=True)

# ================= LOGGING =================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_event(descricao, usuario=None):
    usuario_str = usuario or "sistema"
    logging.info(f"usuario={usuario_str} | {descricao}")

# ================= BANCO =================
def get_db():
    return psycopg2.connect(
        host=config.DB_HOST,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASS
    )

def init_db_extras():
    """Cria colunas/tabelas extras necessárias para os novos requisitos."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Tentativas de login e bloqueio
            cur.execute("""
                ALTER TABLE usuarios
                ADD COLUMN IF NOT EXISTS tentativas_falhas INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS bloqueado_ate TIMESTAMP DEFAULT NULL
            """)
            # Histórico das últimas 3 senhas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS historico_senhas (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                    password_hash TEXT NOT NULL,
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            """)
            # Backup agendado: configuração
            cur.execute("""
                CREATE TABLE IF NOT EXISTS backup_agendado (
                    id SERIAL PRIMARY KEY,
                    ativo BOOLEAN DEFAULT FALSE,
                    intervalo_horas INTEGER DEFAULT 24,
                    ultimo_backup TIMESTAMP DEFAULT NULL
                )
            """)
            # Garante que existe pelo menos uma linha de configuração
            cur.execute("SELECT COUNT(*) FROM backup_agendado")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO backup_agendado (ativo, intervalo_horas) VALUES (false, 24)")
        conn.commit()

# ================= POLÍTICA DE SENHA =================
def validar_senha(senha):
    erros = []
    if len(senha) < 10:
        erros.append("A senha deve ter pelo menos 10 caracteres.")
    if not re.search(r'[A-Z]', senha):
        erros.append("A senha deve conter pelo menos uma letra maiúscula.")
    if not re.search(r'[0-9]', senha):
        erros.append("A senha deve conter pelo menos um número.")
    if not re.search(r'[^A-Za-z0-9]', senha):
        erros.append("A senha deve conter pelo menos um caractere especial.")
    return erros

def senha_repetida(usuario_id, nova_senha):
    """Verifica se a nova senha é igual a alguma das 3 últimas."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT password_hash FROM historico_senhas
                WHERE usuario_id = %s
                ORDER BY criado_em DESC
                LIMIT 3
            """, (usuario_id,))
            for (h,) in cur.fetchall():
                if check_password_hash(h, nova_senha):
                    return True
    return False

def salvar_historico_senha(usuario_id, password_hash):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO historico_senhas (usuario_id, password_hash)
                VALUES (%s, %s)
            """, (usuario_id, password_hash))
        conn.commit()

# ================= BLOQUEIO DE LOGIN =================
MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 10

def verificar_bloqueio(username):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tentativas_falhas, bloqueado_ate FROM usuarios WHERE username=%s", (username,))
            row = cur.fetchone()
            if not row:
                return False, 0
            tentativas, bloqueado_ate = row
            if bloqueado_ate and datetime.now() < bloqueado_ate:
                return True, int((bloqueado_ate - datetime.now()).total_seconds() / 60) + 1
            return False, tentativas

def registrar_falha_login(username):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, tentativas_falhas FROM usuarios WHERE username=%s", (username,))
            row = cur.fetchone()
            if not row:
                return
            uid, tentativas = row
            tentativas += 1
            bloqueado_ate = None
            if tentativas >= MAX_TENTATIVAS:
                bloqueado_ate = datetime.now() + timedelta(minutes=BLOQUEIO_MINUTOS)
                log_event(f"Usuário bloqueado após {MAX_TENTATIVAS} falhas consecutivas.", usuario=username)
            cur.execute("""
                UPDATE usuarios SET tentativas_falhas=%s, bloqueado_ate=%s WHERE id=%s
            """, (tentativas, bloqueado_ate, uid))
        conn.commit()
    log_event(f"Falha de autenticação (tentativa {tentativas}).", usuario=username)

def resetar_falhas_login(username):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL WHERE username=%s", (username,))
        conn.commit()

# ================= BACKUP AGENDADO =================
_scheduler_thread = None

def _run_backup_scheduler():
    while True:
        import time
        time.sleep(60)
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT ativo, intervalo_horas, ultimo_backup FROM backup_agendado LIMIT 1")
                    row = cur.fetchone()
                    if not row or not row[0]:
                        continue
                    _, intervalo_horas, ultimo_backup = row
                    agora = datetime.now()
                    if ultimo_backup is None or (agora - ultimo_backup) >= timedelta(hours=intervalo_horas):
                        _executar_backup()
                        cur.execute("UPDATE backup_agendado SET ultimo_backup=%s", (agora,))
                conn.commit()
        except Exception as e:
            log_event(f"Erro no backup agendado: {e}")

def iniciar_scheduler():
    global _scheduler_thread
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_thread = threading.Thread(target=_run_backup_scheduler, daemon=True)
        _scheduler_thread.start()

def _executar_backup():
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    path = os.path.join(BACKUP_DIR, filename)
    env = os.environ.copy()
    env["PGPASSWORD"] = config.DB_PASS
    with open(path, "w") as f:
        subprocess.run([
            "pg_dump", "-U", config.DB_USER,
            "--no-owner", "--no-privileges", config.DB_NAME
        ], stdout=f, stderr=subprocess.PIPE, env=env, check=True)
    log_event(f"Backup criado: {filename}")
    return filename

# ================= LOGIN =================
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    user = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    bloqueado, info = verificar_bloqueio(user)
    if bloqueado:
        return render_template('login.html', erro=f"Usuário bloqueado. Tente novamente em {info} minuto(s).")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM usuarios WHERE username=%s", (user,))
            result = cur.fetchone()

    if result and check_password_hash(result[0], password):
        resetar_falhas_login(user)
        session.permanent = True
        session['user'] = user
        log_event("Login realizado com sucesso.", usuario=user)
        return redirect('/dashboard')

    registrar_falha_login(user)
    return render_template('login.html', erro="Usuário ou senha inválidos.")

# ================= DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html')

# ================= CADASTRAR PESSOA =================
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
            conn.commit()
        log_event(f"Nova pessoa cadastrada: nome={nome}, documento={documento}.", usuario=session['user'])
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
                    p.id, p.nome, p.documento,
                    CASE
                        WHEN a.id IS NULL THEN false
                        WHEN a.data_saida IS NULL THEN true
                        ELSE false
                    END AS dentro
                FROM pessoas p
                LEFT JOIN LATERAL (
                    SELECT * FROM acessos a
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
            cur.execute("SELECT nome FROM pessoas WHERE id=%s", (id,))
            row = cur.fetchone()
            nome = row[0] if row else str(id)
            cur.execute("SELECT 1 FROM acessos WHERE pessoa_id=%s AND data_saida IS NULL", (id,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO acessos (pessoa_id, data_entrada) VALUES (%s, %s)",
                    (id, datetime.now())
                )
            conn.commit()
    log_event(f"Entrada registrada para: {nome}.", usuario=session['user'])
    return redirect('/listar')

# ================= SAÍDA =================
@app.route('/saida/<int:id>')
def saida(id):
    if 'user' not in session:
        return redirect('/')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM pessoas WHERE id=%s", (id,))
            row = cur.fetchone()
            nome = row[0] if row else str(id)
            cur.execute("""
                UPDATE acessos SET data_saida=%s
                WHERE id=(
                    SELECT id FROM acessos
                    WHERE pessoa_id=%s AND data_saida IS NULL
                    ORDER BY data_entrada DESC LIMIT 1
                )
            """, (datetime.now(), id))
            conn.commit()
    log_event(f"Saída registrada para: {nome}.", usuario=session['user'])
    return redirect('/listar')

# ================= GERENCIAR USUÁRIOS =================
@app.route('/usuarios')
def usuarios():
    if 'user' not in session:
        return redirect('/')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username FROM usuarios ORDER BY username")
            usuarios = cur.fetchall()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/novo', methods=['GET', 'POST'])
def novo_usuario():
    if 'user' not in session:
        return redirect('/')
    erro = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        erros = validar_senha(password)
        if erros:
            erro = " | ".join(erros)
        else:
            hashed = generate_password_hash(password)
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO usuarios (username, password) VALUES (%s, %s) RETURNING id",
                            (username, hashed)
                        )
                        uid = cur.fetchone()[0]
                    conn.commit()
                salvar_historico_senha(uid, hashed)
                log_event(f"Novo usuário cadastrado: {username}.", usuario=session['user'])
                return redirect('/usuarios')
            except Exception:
                erro = "Nome de usuário já existe."
    return render_template('usuario_form.html', acao="Novo Usuário", erro=erro)

@app.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'user' not in session:
        return redirect('/')
    erro = None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM usuarios WHERE id=%s", (id,))
            row = cur.fetchone()
    if not row:
        return "Usuário não encontrado.", 404
    username_atual = row[0]

    if request.method == 'POST':
        novo_username = request.form.get('username', '').strip()
        nova_senha = request.form.get('password', '')

        if nova_senha:
            erros = validar_senha(nova_senha)
            if erros:
                erro = " | ".join(erros)
            elif senha_repetida(id, nova_senha):
                erro = "A nova senha não pode ser igual às 3 últimas senhas utilizadas."
            else:
                hashed = generate_password_hash(nova_senha)
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE usuarios SET username=%s, password=%s WHERE id=%s",
                            (novo_username, hashed, id)
                        )
                    conn.commit()
                salvar_historico_senha(id, hashed)
                log_event(f"Dados/senha do usuário '{username_atual}' alterados. Novo username: '{novo_username}'.", usuario=session['user'])
                return redirect('/usuarios')
        else:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE usuarios SET username=%s WHERE id=%s", (novo_username, id))
                conn.commit()
            log_event(f"Username do usuário '{username_atual}' alterado para '{novo_username}'.", usuario=session['user'])
            return redirect('/usuarios')

    return render_template('usuario_form.html', acao="Editar Usuário", username=username_atual, uid=id, erro=erro)

@app.route('/usuarios/excluir/<int:id>', methods=['POST'])
def excluir_usuario(id):
    if 'user' not in session:
        return redirect('/')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM usuarios WHERE id=%s", (id,))
            row = cur.fetchone()
            if row:
                username = row[0]
                cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))
                log_event(f"Usuário '{username}' excluído.", usuario=session['user'])
        conn.commit()
    return redirect('/usuarios')

# ================= REGISTER (mantido para compatibilidade) =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' not in session:
        return redirect('/')
    return redirect('/usuarios/novo')

# ================= BACKUP =================
@app.route('/backup')
def backup_page():
    if 'user' not in session:
        return redirect('/')
    files = sorted(os.listdir(BACKUP_DIR), reverse=True)[:10]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ativo, intervalo_horas FROM backup_agendado LIMIT 1")
            agendado = cur.fetchone()
    return render_template('backup.html', backups=files, agendado=agendado)

@app.route('/backup/create')
def create_backup():
    if 'user' not in session:
        return redirect('/')
    try:
        filename = _executar_backup()
        log_event(f"Backup manual realizado: {filename}.", usuario=session['user'])
    except subprocess.CalledProcessError as e:
        return f"Erro no backup: {e.stderr.decode()}"
    return redirect('/backup')

@app.route('/backup/agendar', methods=['POST'])
def agendar_backup():
    if 'user' not in session:
        return redirect('/')
    ativo = request.form.get('ativo') == 'on'
    intervalo = int(request.form.get('intervalo_horas', 24))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE backup_agendado SET ativo=%s, intervalo_horas=%s", (ativo, intervalo))
        conn.commit()
    status = "ativado" if ativo else "desativado"
    log_event(f"Backup agendado {status}. Intervalo: {intervalo}h.", usuario=session['user'])
    return redirect('/backup')

@app.route('/backup/restore', methods=['POST'])
def restore_backup():
    if 'user' not in session:
        return redirect('/')
    file = request.files.get('file')
    path = os.path.join(BACKUP_DIR, file.filename)
    file.save(path)
    env = os.environ.copy()
    env["PGPASSWORD"] = config.DB_PASS
    try:
        subprocess.run([
            "psql", "-U", config.DB_USER, "-d", config.DB_NAME,
            "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        ], env=env, check=True)
        subprocess.run([
            "psql", "-U", config.DB_USER, "-d", config.DB_NAME, "-f", path
        ], stderr=subprocess.PIPE, env=env, check=True)
        log_event(f"Restore realizado a partir de: {file.filename}.", usuario=session['user'])
    except subprocess.CalledProcessError as e:
        return f"Erro no restore: {e.stderr.decode()}"
    return redirect('/backup')

@app.route('/backup/download/<filename>')
def download_backup(filename):
    if 'user' not in session:
        return redirect('/')
    return send_file(os.path.join(BACKUP_DIR, filename), as_attachment=True)

# ================= GERENCIAR (pessoas + usuários legado) =================
@app.route('/gerenciar')
def gerenciar():
    if 'user' not in session:
        return redirect('/')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username FROM usuarios ORDER BY username")
            usuarios = cur.fetchall()
            cur.execute("SELECT id, nome, documento, telefone FROM pessoas ORDER BY nome")
            pessoas = cur.fetchall()
    return render_template('gerenciar.html', usuarios=usuarios, pessoas=pessoas)


# ================= ROTAS LEGADAS DO GERENCIAR =================
@app.route('/update_usuario/<int:id>', methods=['POST'])
def update_usuario_legacy(id):
    if 'user' not in session:
        return redirect('/')
    username = request.form.get('username', '').strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET username=%s WHERE id=%s", (username, id))
        conn.commit()
    return redirect('/gerenciar')

@app.route('/delete_usuario/<int:id>')
def delete_usuario_legacy(id):
    if 'user' not in session:
        return redirect('/')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))
        conn.commit()
    return redirect('/gerenciar')

@app.route('/update_pessoa/<int:id>', methods=['POST'])
def update_pessoa(id):
    if 'user' not in session:
        return redirect('/')

    nome = request.form.get('nome')
    documento = request.form.get('documento')
    telefone = request.form.get('telefone')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE pessoas
                   SET nome=%s,
                       documento=%s,
                       telefone=%s
                 WHERE id=%s
            """, (nome, documento, telefone, id))
        conn.commit()

    return redirect('/gerenciar')

@app.route('/delete_pessoa/<int:id>')
def delete_pessoa(id):
    if 'user' not in session:
        return redirect('/')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acessos WHERE pessoa_id=%s", (id,))
            cur.execute("DELETE FROM pessoas WHERE id=%s", (id,))
        conn.commit()

    return redirect('/gerenciar')


# ================= LOG VIEWER =================
@app.route('/logs')
def ver_logs():
    if 'user' not in session:
        return redirect('/')
    try:
        with open(LOG_FILE, 'r') as f:
            linhas = f.readlines()[-200:]
    except FileNotFoundError:
        linhas = []
    return render_template('logs.html', linhas=linhas)

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    user = session.get('user', 'desconhecido')
    session.clear()
    log_event("Logout realizado.", usuario=user)
    return redirect('/')

# ================= INIT =================
if __name__ == '__main__':
    init_db_extras()
    iniciar_scheduler()
    # HTTPS: use ssl_context em produção com certificado real
    # app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))
    app.run(host='0.0.0.0', port=5000)
