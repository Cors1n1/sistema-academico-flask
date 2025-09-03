# app.py

from flask import Flask, render_template, request, redirect, url_for, Response, session, flash
from functools import wraps
from funcoes.funcoes import carregar_dados, salvar_dados, gerar_relatorio_dados
import json
from werkzeug.security import check_password_hash, generate_password_hash
import pandas as pd
from weasyprint import HTML
import io
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import re

app = Flask(__name__)
app.secret_key = 'chave-secreta-para-o-projeto-unip-12345'


handler = RotatingFileHandler('app.log', maxBytes=100000, backupCount=3, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

def carregar_usuarios():
    if not os.path.exists('usuarios.json'): return []
    with open('usuarios.json', 'r', encoding='utf-8') as f: return json.load(f)

def salvar_usuarios(usuarios):
    with open('usuarios.json', 'w', encoding='utf-8') as f: json.dump(usuarios, f, ensure_ascii=False, indent=4)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') != role:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ROTAS DE AUTENTICAÇÃO
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuarios = carregar_usuarios()
        user = next((u for u in usuarios if u['username'] == username), None)
        if user and check_password_hash(user['password_hash'], password):
            session['logged_in'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            app.logger.info(f"Usuário '{session['username']}' fez login.")
            return redirect(url_for('index'))
        else:
            app.logger.warning(f"Tentativa de login falhou para o usuário '{username}'.")
            flash('Usuário ou senha incorretos.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    app.logger.info(f"Usuário '{session['username']}' fez logout.")
    session.clear()
    return redirect(url_for('login'))

# ROTAS DA APLICAÇÃO
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/lista')
@login_required
def lista_alunos():
    alunos = carregar_dados()
    return render_template('lista_alunos.html', alunos=alunos)

@app.route('/adicionar', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def adicionar():
    if request.method == 'POST':
        nome = request.form['nome']
        idade = int(request.form['idade'])
        curso = request.form['curso']
        horas = float(request.form['horas_estudo'])
        alunos = carregar_dados()
        novo_aluno = { "nome": nome, "idade": idade, "curso": curso, "horas_estudo": horas }
        alunos.append(novo_aluno)
        salvar_dados(alunos)
        app.logger.info(f"Usuário '{session['username']}' ADICIONOU o aluno '{nome}'.")
        return redirect(url_for('lista_alunos'))
    return render_template('adicionar.html')

@app.route('/editar/<nome_do_aluno>', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def editar(nome_do_aluno):
    alunos = carregar_dados()
    aluno_para_editar = next((aluno for aluno in alunos if aluno['nome'] == nome_do_aluno), None)
    if not aluno_para_editar: return redirect(url_for('lista_alunos'))
    if request.method == 'POST':
        nome_original = request.form['nome_original']
        for aluno in alunos:
            if aluno['nome'] == nome_original:
                aluno['nome'] = request.form['nome']
                aluno['idade'] = int(request.form['idade'])
                aluno['curso'] = request.form['curso']
                aluno['horas_estudo'] = float(request.form['horas_estudo'])
                break
        salvar_dados(alunos)
        app.logger.info(f"Usuário '{session['username']}' EDITOU o cadastro de '{nome_original}'.")
        return redirect(url_for('lista_alunos'))
    return render_template('editar.html', aluno=aluno_para_editar)

@app.route('/deletar/<nome_do_aluno>')
@login_required
@permission_required('admin')
def deletar(nome_do_aluno):
    alunos = carregar_dados()
    alunos_filtrados = [aluno for aluno in alunos if aluno['nome'] != nome_do_aluno]
    salvar_dados(alunos_filtrados)
    app.logger.info(f"Usuário '{session['username']}' DELETOU o aluno '{nome_do_aluno}'.")
    return redirect(url_for('lista_alunos'))

@app.route('/relatorio')
@login_required
def relatorio():
    dados_relatorio = gerar_relatorio_dados()
    return render_template('relatorio.html', dados=dados_relatorio)

@app.route('/exportar/<formato>')
@login_required
def exportar(formato):
    app.logger.info(f"Usuário '{session['username']}' EXPORTOU os dados para {formato.upper()}.")
    alunos = carregar_dados()
    if formato == 'pdf':
        theme_color = request.args.get('color', '#4a90e2')
        dados_relatorio = gerar_relatorio_dados()
        data_atual = datetime.now().strftime("%d/%m/%Y")
        html_renderizado = render_template('relatorio_pdf.html', alunos=alunos, dados=dados_relatorio, data_hoje=data_atual, theme_color=theme_color)
        pdf = HTML(string=html_renderizado).write_pdf()
        return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=relatorio_alunos.pdf'})
    if formato == 'excel':
        df = pd.DataFrame(alunos)
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Alunos')
        writer.close()
        output.seek(0)
        return Response(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment;filename=relatorio_alunos.xlsx'})
    return redirect(url_for('lista_alunos'))

@app.route('/gerenciar_usuarios', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def gerenciar_usuarios():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        usuarios = carregar_usuarios()
        if any(u['username'] == username for u in usuarios):
            flash(f"O nome de usuário '{username}' já existe. Tente outro.", 'danger')
            return redirect(url_for('gerenciar_usuarios'))
        password_hash = generate_password_hash(password)
        novo_usuario = { "username": username, "password_hash": password_hash, "role": role }
        usuarios.append(novo_usuario)
        salvar_usuarios(usuarios)
        app.logger.info(f"Admin '{session['username']}' CRIOU o usuário '{username}' com a permissão '{role}'.")
        flash(f"Usuário '{username}' criado com sucesso!", 'success')
        return redirect(url_for('gerenciar_usuarios'))
    usuarios = carregar_usuarios()
    return render_template('gerenciar_usuarios.html', usuarios=usuarios)

@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def editar_usuario(username):
    if username == session['username']:
        flash('Você não pode editar sua própria conta.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))
    usuarios = carregar_usuarios()
    user_para_editar = next((u for u in usuarios if u['username'] == username), None)
    if not user_para_editar: return redirect(url_for('gerenciar_usuarios'))
    if request.method == 'POST':
        nova_permissao = request.form['role']
        for user in usuarios:
            if user['username'] == username: user['role'] = nova_permissao; break
        salvar_usuarios(usuarios)
        app.logger.info(f"Admin '{session['username']}' ALTEROU a permissão de '{username}' para '{nova_permissao}'.")
        flash(f"Permissão do usuário '{username}' atualizada com sucesso!", 'success')
        return redirect(url_for('gerenciar_usuarios'))
    return render_template('editar_usuario.html', user=user_para_editar)

@app.route('/deletar_usuario/<username>')
@login_required
@permission_required('admin')
def deletar_usuario(username):
    if username == session['username']:
        flash('Você não pode deletar sua própria conta!', 'danger')
        return redirect(url_for('gerenciar_usuarios'))
    usuarios = carregar_usuarios()
    usuarios_filtrados = [user for user in usuarios if user['username'] != username]
    if len(usuarios) == len(usuarios_filtrados):
        flash(f"Usuário '{username}' não encontrado.", 'danger')
    else:
        salvar_usuarios(usuarios_filtrados)
        app.logger.info(f"Admin '{session['username']}' DELETOU o usuário '{username}'.")
        flash(f"Usuário '{username}' deletado com sucesso!", 'success')
    return redirect(url_for('gerenciar_usuarios'))
    
@app.route('/logs')
@login_required
@permission_required('admin')
def view_logs():
    log_entries = []
    log_pattern = re.compile(r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) - (\w+) - (.*)', re.DOTALL)
    if os.path.exists('app.log'):
        with open('app.log', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            entries = re.split(r'(?=\d{2}/\d{2}/\d{4})', content)
            for entry_text in reversed(entries):
                if not entry_text.strip(): continue
                match = log_pattern.match(entry_text.strip())
                if match: log_entries.append({'timestamp': match.group(1), 'level': match.group(2), 'message': match.group(3)})
    return render_template('logs.html', log_entries=log_entries)

if __name__ == '__main__':
    app.run(debug=True)


@app.route('/meu_perfil')
@login_required
def meu_perfil():
    # Pega o nome de usuário da sessão
    username = session.get('username')
    
    # Carrega todos os alunos
    alunos = carregar_dados()
    
    # Encontra o aluno cujo nome corresponde ao nome de usuário
    aluno_correspondente = next((aluno for aluno in alunos if aluno['nome'] == username), None)
    
    # Renderiza a página do perfil, passando os dados do aluno (ou None se não encontrar)
    return render_template('meu_perfil.html', aluno=aluno_correspondente)


# (O resto de todas as outras rotas continua o mesmo)
# ...