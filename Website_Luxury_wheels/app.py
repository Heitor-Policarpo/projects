from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3

app = Flask(__name__)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
app.config['SECRET_KEY'] = 'sua_chave_secreta'

# Função para carregar o usuário
def connect_db():
    conn = sqlite3.connect('luxury_wheels.db')
    conn.row_factory = sqlite3.Row  # Retorna resultados como dicionários
    return conn

@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return Usuario(id=user['id'], nome=user['nome'], email=user['email'])
    return None

class Usuario(UserMixin):
    def __init__(self, id, nome, email):
        self.id = id
        self.nome = nome
        self.email = email


@app.route('/')
def home():
    return render_template('index.html')

# Rota de registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')

        # Validação dos dados
        if not nome or not email or not senha or not confirmar_senha:
            flash('Todos os campos são obrigatórios.', 'danger')
            return redirect(url_for('register'))

        if senha != confirmar_senha:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('register'))

        # Criptografar a senha
        senha_hash = generate_password_hash(senha)

        # Conectar ao banco e verificar se o e-mail já existe
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user:
            flash('O e-mail já está cadastrado. Tente outro.', 'danger')
            conn.close()
            return redirect(url_for('register'))

        # Inserir o novo usuário no banco de dados
        cursor.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha_hash))
        conn.commit()
        conn.close()

        flash('Registro bem-sucedido! Faça login para continuar.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Rota de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        # Conectar ao banco e buscar o usuário pelo e-mail
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['senha'], senha):
            user_obj = Usuario(id=user['id'], nome=user['nome'], email=user['email'])
            login_user(user_obj)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('home'))
        else:
            flash('E-mail ou senha incorretos.', 'danger')

    return render_template('login.html')

# Rota de logout
@app.route('/logout', methods=['GET','POST'])
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))

# Rota de listagem de veículos
@app.route('/veiculos', methods=['GET', 'POST'])
@login_required
def veiculos():
    conn = connect_db()
    cursor = conn.cursor()

    # Filtros disponíveis
    filtros_disponiveis = {
        "categoria": request.form.get('categoria'),
        "transmissao": request.form.get('transmissao'),
        "tipo": request.form.get('tipo'),
        "valor_diaria_max": request.form.get('valor_diaria'),
        "quantidade_pessoas": request.form.get('quantidade_pessoas')
    }

    # Construção da query base
    query = "SELECT * FROM veiculos WHERE disponivel = 1"
    parametros = []

    # Adiciona condições baseadas nos filtros
    if filtros_disponiveis["categoria"]:
        query += " AND categoria = ?"
        parametros.append(filtros_disponiveis["categoria"])
    if filtros_disponiveis["transmissao"]:
        query += " AND transmissao = ?"
        parametros.append(filtros_disponiveis["transmissao"])
    if filtros_disponiveis["tipo"]:
        query += " AND tipo = ?"
        parametros.append(filtros_disponiveis["tipo"])
    if filtros_disponiveis["valor_diaria_max"]:
        query += " AND valor_diaria <= ?"
        parametros.append(float(filtros_disponiveis["valor_diaria_max"]))
    if filtros_disponiveis["quantidade_pessoas"]:
        query += " AND quantidade_pessoas >= ?"
        parametros.append(int(filtros_disponiveis["quantidade_pessoas"]))

    # Executa a consulta com os parâmetros
    cursor.execute(query, parametros)
    veiculos_disponiveis = cursor.fetchall()
    conn.close()

    return render_template('veiculos.html', veiculos=veiculos_disponiveis, filtros=filtros_disponiveis)

# Rota para detalhes de veículo
@app.route('/veiculo/<int:id>', methods=['GET'])
@login_required
def detalhes_veiculo(id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM veiculos WHERE id = ?", (id,))
    veiculo = cursor.fetchone()
    conn.close()

    if not veiculo:
        flash('Veículo não encontrado.', 'danger')
        return redirect(url_for('veiculos'))

    return render_template('detalhes_veiculo.html', veiculo=dict(veiculo))


# Rota de reservas
@app.route('/reservar/<int:veiculo_id>', methods=['GET', 'POST'])
@login_required
def reservar(veiculo_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM veiculos WHERE id = ?", (veiculo_id,))
    veiculo = cursor.fetchone()
    if not veiculo or not veiculo['disponivel']:
        flash('Veículo não disponível para reserva.', 'danger')
        conn.close()
        return redirect(url_for('veiculos'))

    if request.method == 'POST':
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        forma_pagamento = request.form.get('forma_pagamento')

        if forma_pagamento not in ['Cartão', 'Carteira Digital']:
            flash('Forma de pagamento inválida.', 'danger')
            return redirect(url_for('reservar', veiculo_id=veiculo_id))

        try:
            data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
            data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")
        except ValueError:
            flash('Formato de data inválido.', 'danger')
            return redirect(url_for('reservar', veiculo_id=veiculo_id))

        if data_inicio_dt >= data_fim_dt:
            flash('A data de fim deve ser posterior à data de início.', 'danger')
            return redirect(url_for('reservar', veiculo_id=veiculo_id))

        dias = (data_fim_dt - data_inicio_dt).days
        valor_total = dias * veiculo['valor_diaria']

        # Inserir a reserva no banco
        cursor.execute(
            "INSERT INTO reservas (usuario_id, veiculo_id, data_inicio, data_fim, valor_total, forma_pagamento) VALUES (?, ?, ?, ?, ?, ?)",
            (current_user.id, veiculo_id, data_inicio, data_fim, valor_total, forma_pagamento)
        )
        cursor.execute("UPDATE veiculos SET disponivel = 0 WHERE id = ?", (veiculo_id,))
        conn.commit()
        conn.close()

        flash('Reserva realizada com sucesso!', 'success')
        return redirect(url_for('minhas_reservas'))

    conn.close()
    return render_template('reservar.html', veiculo=dict(veiculo))

# Rota de listar reservas
@app.route('/minhas_reservas', methods=['GET'])
@login_required
def minhas_reservas():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id AS reserva_id, v.marca, v.modelo, r.data_inicio, r.data_fim, r.valor_total, r.forma_pagamento 
        FROM reservas r
        JOIN veiculos v ON r.veiculo_id = v.id
        WHERE r.usuario_id = ?
        """, (current_user.id,)
    )
    reservas = cursor.fetchall()

    # Converter as reservas em uma lista de dicionários
    reservas = [dict(reserva) for reserva in reservas]
    conn.close()

    return render_template('minhas_reservas.html', reservas=reservas)

# Rota para alterar uma reserva
@app.route('/alterar_reserva/<int:reserva_id>', methods=['GET', 'POST'])
@login_required
def alterar_reserva(reserva_id):
    conn = connect_db()
    cursor = conn.cursor()

    # Verifica se a reserva pertence ao usuário logado
    cursor.execute(
        """
        SELECT r.id, r.data_inicio, r.data_fim, r.valor_total, r.forma_pagamento, v.marca, v.modelo, v.valor_diaria 
        FROM reservas r
        JOIN veiculos v ON r.veiculo_id = v.id
        WHERE r.id = ? AND r.usuario_id = ?
        """, (reserva_id, current_user.id)
    )
    reserva = cursor.fetchone()

    if not reserva:
        conn.close()
        flash('Reserva não encontrada ou você não tem permissão para alterá-la.', 'danger')
        return redirect(url_for('minhas_reservas'))

    if request.method == 'POST':
        nova_data_inicio = request.form.get('data_inicio')
        nova_data_fim = request.form.get('data_fim')
        forma_pagamento = request.form.get('forma_pagamento')

        # Validação das datas
        try:
            nova_data_inicio_dt = datetime.strptime(nova_data_inicio, "%Y-%m-%d")
            nova_data_fim_dt = datetime.strptime(nova_data_fim, "%Y-%m-%d")
            if nova_data_inicio_dt >= nova_data_fim_dt:
                flash('A data de término deve ser posterior à data de início.', 'danger')
                return redirect(url_for('alterar_reserva', reserva_id=reserva_id))
        except ValueError:
            flash('Formato de data inválido.', 'danger')
            return redirect(url_for('alterar_reserva', reserva_id=reserva_id))

        # Calcular o novo valor total da reserva
        dias = (nova_data_fim_dt - nova_data_inicio_dt).days
        valor_total = dias * reserva['valor_diaria']

        # Atualiza a reserva no banco de dados
        cursor.execute(
            """
            UPDATE reservas 
            SET data_inicio = ?, data_fim = ?, valor_total = ?, forma_pagamento = ? 
            WHERE id = ? AND usuario_id = ?
            """, (nova_data_inicio, nova_data_fim, valor_total, forma_pagamento, reserva_id, current_user.id)
        )
        conn.commit()
        conn.close()

        flash('Reserva alterada com sucesso!', 'success')
        return redirect(url_for('minhas_reservas'))

    conn.close()
    return render_template('alterar_reserva.html', reserva=dict(reserva))

# Rota para cancelar uma reserva
@app.route('/cancelar_reserva/<int:reserva_id>', methods=['POST'])
@login_required
def cancelar_reserva(reserva_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT veiculo_id FROM reservas WHERE id = ? AND usuario_id = ?", (reserva_id, current_user.id))
    reserva = cursor.fetchone()
    if not reserva:
        conn.close()
        flash('Reserva não encontrada ou você não tem permissão para cancelá-la.', 'danger')
        return redirect(url_for('minhas_reservas'))

    veiculo_id = reserva['veiculo_id']
    cursor.execute("UPDATE veiculos SET disponivel = 1 WHERE id = ?", (veiculo_id,))
    cursor.execute("DELETE FROM reservas WHERE id = ?", (reserva_id,))
    conn.commit()
    conn.close()

    flash('Reserva cancelada com sucesso.', 'success')
    return redirect(url_for('minhas_reservas'))

# Rota para confirmar uma reserva
@app.route('/confirmar_reserva/<int:reserva_id>', methods=['POST'])
@login_required
def confirmar_reserva(reserva_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,))
    reserva = cursor.fetchone()
    if not reserva:
        conn.close()
        flash('Reserva não encontrada.', 'danger')
        return redirect(url_for('minhas_reservas'))

    if reserva['status'] == 'Pendente':
        cursor.execute("UPDATE reservas SET status = 'Confirmada' WHERE id = ?", (reserva_id,))
        conn.commit()
        flash('Reserva confirmada com sucesso!', 'success')
    else:
        flash('A reserva já está confirmada ou foi cancelada.', 'info')

    conn.close()
    return redirect(url_for('minhas_reservas'))

if __name__ == '__main__':
    app.run(debug=True)