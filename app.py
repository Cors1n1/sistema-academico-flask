from flask import Flask, render_template, request, redirect, url_for, Response, session, flash, jsonify
from functools import wraps
from funcoes.funcoes import (
    carregar_dados, salvar_dados, gerar_relatorio_dados,
    carregar_usuarios, salvar_usuarios, carregar_aulas, salvar_aulas,
    carregar_exercicios, salvar_exercicios, carregar_provas, salvar_provas,
    carregar_resultados_provas, salvar_resultados_provas,
    buscar_resultados_por_prova_id, buscar_prova_por_id,
    gerar_senha_aleatoria, gerar_token_recuperacao, verificar_token_recuperacao, carregar_alunos,
    verificar_e_atribuir_conquistas, carregar_conquistas_definidas, calcular_ranking_por_curso,
    calcular_media_horas_estudo_por_curso, calcular_progresso_por_curso_e_topico,
    calcular_media_notas_por_prova, identificar_questoes_criticas, identificar_alunos_com_baixo_desempenho,
    carregar_forum, salvar_forum, buscar_post_por_id
)
from flask_mail import Mail, Message
import json
from werkzeug.security import check_password_hash, generate_password_hash
import pandas as pd
from weasyprint import HTML
import io
from datetime import datetime, date, timedelta
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time
import random
from werkzeug.utils import secure_filename
import requests
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO, emit
from collections import defaultdict


# Carrega as variáveis de ambiente do arquivo .env
# Adicionei o caminho explícito para garantir que o arquivo seja encontrado.
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path)

app = Flask(__name__)
app.secret_key = 'chave-secreta-para-o-projeto-unip-12345'

# Inicializa a proteção CSRF
csrf = CSRFProtect(app)

# Inicializa o SocketIO
socketio = SocketIO(app)

UPLOAD_FOLDER = 'static/uploads/profile_pics'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configurações do Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# CONFIGURAÇÃO DO LOG - CORRIGIDO PARA EVITAR ERRO DE PERMISSÃO
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    handler = RotatingFileHandler('app.log', maxBytes=100000, backupCount=3, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

# DECORATORS DE PERMISSÃO
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Você não tem permissão para aceder a esta página.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuarios = carregar_usuarios()
        user = next((u for u in usuarios if u['username'] == username), None)
        if user and check_password_hash(user.get('password_hash', ''), password):
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

@app.route('/esqueci_a_senha', methods=['GET', 'POST'])
def esqueci_a_senha():
    if request.method == 'POST':
        username = request.form['username']
        alunos = carregar_dados()
        aluno_correspondente = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        
        if aluno_correspondente and aluno_correspondente.get('email'):
            token = gerar_token_recuperacao(username, app.secret_key)
            
            usuarios = carregar_usuarios()
            user_to_update = next((u for u in usuarios if u['username'] == username), None)
            if user_to_update:
                user_to_update['reset_token'] = token
                salvar_usuarios(usuarios)

            link_redefinicao = url_for('redefinir_senha', token=token, _external=True)
            
            msg = Message('Redefinição de Senha do Sistema Acadêmico', recipients=[aluno_correspondente['email']])
            msg.body = f'''
Olá {aluno_correspondente.get('nome')},

Recebemos uma solicitação para redefinir a senha da sua conta.
Para prosseguir, clique no link abaixo. Ele expirará em 1 hora.

{link_redefinicao}

Se você não solicitou esta redefinição, por favor, ignore este e-mail.
Sua senha permanecerá a mesma.

Atenciosamente,
Equipe do Sistema Acadêmico
'''
            try:
                mail.send(msg)
                flash(f'Um link de redefinição de senha foi enviado para o e-mail de "{username}".', 'success')
                app.logger.info(f"E-mail de recuperação de senha enviado para '{username}'.")
            except Exception as e:
                flash('Não foi possível enviar o e-mail de redefinição de senha. Por favor, verifique as configurações.', 'danger')
                app.logger.error(f"Erro ao enviar e-mail de recuperação para '{username}': {e}")
        else:
            flash('Usuário ou e-mail não encontrado no sistema.', 'danger')
        
        return redirect(url_for('login'))
    return render_template('esqueci_a_senha.html')

@app.route('/redefinir_senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    username = verificar_token_recuperacao(token, app.secret_key)
    
    if username == 'expired':
        flash('O token de redefinição de senha expirou. Por favor, solicite uma nova redefinição.', 'danger')
        return redirect(url_for('esqueci_a_senha'))
    
    usuarios = carregar_usuarios()
    user = next((u for u in usuarios if u['username'] == username), None)

    if not user or user.get('reset_token') != token:
        flash('O token de redefinição de senha é inválido.', 'danger')
        return redirect(url_for('esqueci_a_senha'))

    if request.method == 'POST':
        nova_senha = request.form['nova_senha']
        confirmar_nova_senha = request.form['confirmar_nova_senha']
        
        if nova_senha != confirmar_nova_senha:
            flash('A nova senha e a confirmação não coincidem.', 'danger')
            return redirect(url_for('redefinir_senha', token=token))
        
        user['password_hash'] = generate_password_hash(nova_senha)
        user.pop('reset_token', None)
        salvar_usuarios(usuarios)
        
        flash('Sua senha foi redefinida com sucesso! Por favor, faça login com a nova senha.', 'success')
        app.logger.info(f"Senha do usuário '{username}' redefinida com sucesso.")
        return redirect(url_for('login'))

    return render_template('redefinir_senha.html', token=token)

@app.route('/alterar_senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    if request.method == 'POST':
        username = session.get('username')
        senha_atual = request.form['senha_atual']
        nova_senha = request.form['nova_senha']
        confirmar_nova_senha = request.form['confirmar_nova_senha']

        usuarios = carregar_usuarios()
        user = next((u for u in usuarios if u['username'] == username), None)

        if not user or not check_password_hash(user.get('password_hash', ''), senha_atual):
            flash('A senha atual está incorreta.', 'danger')
            return redirect(url_for('alterar_senha'))
        
        if nova_senha != confirmar_nova_senha:
            flash('A nova senha e a confirmação não coincidem.', 'danger')
            return redirect(url_for('alterar_senha'))

        user['password_hash'] = generate_password_hash(nova_senha)
        salvar_usuarios(usuarios)
        flash('Sua senha foi alterada com sucesso!', 'success')
        app.logger.info(f"Senha do usuário '{username}' alterada com sucesso.")
        return redirect(url_for('meu_perfil'))

    return render_template('alterar_senha.html')

# --- ROTAS DA APLICAÇÃO GERAL ---
@app.route('/')
@login_required
def index():
    # Carrega o perfil do aluno para a barra de conquistas
    aluno = None
    if session.get('role') == 'aluno':
        todos_alunos = carregar_dados()
        aluno = next((p for p in todos_alunos if p.get('nome') == session.get('username')), None)

    return render_template('index.html', aluno=aluno)

@app.route('/save_card_order', methods=['POST'])
@login_required
def save_card_order():
    if request.is_json:
        session['card_order'] = request.json.get('order')
        return '', 204
    return 'Bad Request', 400

@app.route('/reset_card_order', methods=['POST'])
@login_required
def reset_card_order():
    if 'card_order' in session:
        session.pop('card_order', None)
    return '', 204

@app.route('/meu_perfil', methods=['GET', 'POST'])
@login_required
def meu_perfil():
    username = session.get('username')
    todos_dados = carregar_dados()
    aluno_correspondente = next((aluno for aluno in todos_dados if aluno.get('nome') == username), None)

    if request.method == 'POST':
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(f"{username}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                if aluno_correspondente:
                    aluno_correspondente['profile_pic'] = filename
                    salvar_dados(todos_dados)
                    flash('Foto de perfil atualizada com sucesso!', 'success')
                else:
                    flash('Perfil de usuário não encontrado para salvar a foto.', 'danger')
        
        # Lógica para salvar a meta de estudo
        meta_estudo = request.form.get('meta_estudo')
        if meta_estudo and aluno_correspondente:
            aluno_correspondente['meta_estudo'] = float(meta_estudo)
            salvar_dados(todos_dados)
            flash('Meta de estudo atualizada com sucesso!', 'success')
            
        return redirect(url_for('meu_perfil'))

    return render_template('meu_perfil.html', aluno=aluno_correspondente)

@app.route('/remover_foto_perfil', methods=['POST'])
@login_required
def remover_foto_perfil():
    username = session.get('username')
    todos_dados = carregar_dados()
    aluno_correspondente = next((aluno for aluno in todos_dados if aluno.get('nome') == username), None)

    if aluno_correspondente and aluno_correspondente.get('profile_pic'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], aluno_correspondente['profile_pic'])
        if os.path.exists(filepath):
            os.remove(filepath)
            
        aluno_correspondente['profile_pic'] = None
        salvar_dados(todos_dados)
        flash('Foto de perfil removida com sucesso!', 'success')
    else:
        flash('Nenhuma foto de perfil encontrada para remover.', 'warning')
        
    return redirect(url_for('meu_perfil'))


@app.route('/lista_alunos')
@login_required
def lista_alunos():
    search_query = request.args.get('search_query', '').lower()
    
    if session.get('role') in ['admin', 'professor']:
        alunos_por_curso = {}
        todos_alunos = carregar_alunos()
        for aluno in todos_alunos:
            cursos = aluno.get('curso', [])
            if not cursos:
                if "Sem Curso Definido" not in alunos_por_curso:
                    alunos_por_curso["Sem Curso Definido"] = []
                alunos_por_curso["Sem Curso Definido"].append(aluno)
            else:
                for curso in cursos:
                    if curso not in alunos_por_curso:
                        alunos_por_curso[curso] = []
                    alunos_por_curso[curso].append(aluno)
    else: # aluno
        username = session.get('username')
        todos_alunos = carregar_alunos()
        alunos_do_usuario = [aluno for aluno in todos_alunos if aluno.get('nome') == username]
        if alunos_do_usuario:
            cursos_do_aluno = alunos_do_usuario[0].get('curso')
            colegas_de_turma = [
                aluno for aluno in todos_alunos
                if any(curso in aluno.get('curso', []) for curso in cursos_do_aluno)
            ]
            alunos_por_curso = {}
            for aluno in colegas_de_turma:
                cursos = aluno.get('curso', [])
                if not cursos:
                    if "Sem Curso Definido" not in alunos_por_curso:
                        alunos_por_curso["Sem Curso Definido"] = []
                    alunos_por_curso["Sem Curso Definido"].append(aluno)
                else:
                    for curso in cursos:
                        if curso not in alunos_por_curso:
                            alunos_por_curso[curso] = []
                        alunos_por_curso[curso].append(aluno)
        else:
            return render_template('lista_alunos.html', alunos_por_curso={})

    # Lógica de filtragem
    if search_query:
        for curso, alunos_list in list(alunos_por_curso.items()):
            filtered_alunos = [
                aluno for aluno in alunos_list
                if search_query in aluno.get('nome', '').lower() or
                   any(search_query in c.lower() for c in aluno.get('curso', []))
            ]
            if filtered_alunos:
                alunos_por_curso[curso] = filtered_alunos
            else:
                del alunos_por_curso[curso]

    return render_template('lista_alunos.html', alunos_por_curso=alunos_por_curso)

# --- ROTAS DE AULAS ---
@app.route('/aulas')
@login_required
def lista_aulas():
    todas_as_aulas = carregar_aulas()
    aulas_por_curso = {}
    if session.get('role') in ['admin', 'professor']:
        for aula in todas_as_aulas:
            curso = aula.get('curso')
            if curso not in aulas_por_curso:
                aulas_por_curso[curso] = []
            aulas_por_curso[curso].append(aula)
    else: # aluno
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            cursos_do_aluno = aluno_atual.get('curso')
            # Adiciona aulas de todos os cursos que o aluno está matriculado
            for curso_do_aluno in cursos_do_aluno:
                aulas_do_curso = [aula for aula in todas_as_aulas if aula.get('curso') == curso_do_aluno]
                if aulas_do_curso:
                    aulas_por_curso[curso_do_aluno] = aulas_do_curso
    return render_template('aulas.html', aulas_por_curso=aulas_por_curso)

@app.route('/aula/<aula_id>')
@login_required
def ver_aula(aula_id):
    todas_as_aulas = carregar_aulas()
    aula_selecionada = next((a for a in todas_as_aulas if a.get('id') == aula_id), None)
    if not aula_selecionada:
        flash('Aula não encontrada.', 'danger')
        return redirect(url_for('lista_aulas'))

    if session.get('role') not in ['admin', 'professor']:
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if not aluno_atual or aula_selecionada.get('curso') not in aluno_atual.get('curso', []):
            flash('Você não tem permissão para ver esta aula.', 'danger')
            return redirect(url_for('lista_aulas'))
    return render_template('ver_aula.html', aula=aula_selecionada)


# --- ROTAS DE EXERCÍCIOS (ALUNO) ---
@app.route('/lista_exercicios')
@login_required
def lista_exercicios():
    todos_exercicios = carregar_exercicios()
    exercicios_por_curso = {}

    if session.get('role') in ['admin', 'professor']:
        for exercicio in todos_exercicios:
            curso = exercicio.get('curso', 'Sem Curso')
            if curso not in exercicios_por_curso:
                exercicios_por_curso[curso] = []
            exercicios_por_curso[curso].append(exercicio)
    else: # aluno
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            cursos_do_aluno = aluno_atual.get('curso')
            # Adiciona exercícios de todos os cursos que o aluno está matriculado
            for curso_do_aluno in cursos_do_aluno:
                exercicios_do_curso = [ex for ex in todos_exercicios if ex.get('curso') == curso_do_aluno]
                if exercicios_do_curso:
                    exercicios_por_curso[curso_do_aluno] = exercicios_do_curso

    return render_template('lista_exercicios.html', exercicios_por_curso=exercicios_por_curso)

@app.route('/exercicio/<exercicio_id>')
@login_required
def ver_exercicio(exercicio_id):
    todos_exercicios = carregar_exercicios()
    exercicio_selecionado = next((ex for ex in todos_exercicios if ex.get('id') == exercicio_id), None)
    
    if not exercicio_selecionado:
        flash('Exercício não encontrado.', 'danger')
        return redirect(url_for('lista_exercicios'))

    if session.get('role') not in ['admin', 'professor']:
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if not aluno_atual or exercicio_selecionado.get('curso') not in aluno_atual.get('curso', []):
            flash('Você não tem permissão para ver este exercício.', 'danger')
            return redirect(url_for('lista_exercicios'))
    return render_template('ver_exercicio.html', exercicio=exercicio_selecionado)

@app.route('/corrigir_exercicio/<exercicio_id>', methods=['POST'])
@login_required
def corrigir_exercicio(exercicio_id):
    todos_exercicios = carregar_exercicios()
    exercicio_selecionado = next((ex for ex in todos_exercicios if ex.get('id') == exercicio_id), None)
    
    if not exercicio_selecionado:
        flash('Exercício não encontrado.', 'danger')
        return redirect(url_for('lista_exercicios'))
    
    resposta_usuario = request.form.get('resposta')
    resposta_correta = exercicio_selecionado.get('resposta_correta')
    
    correto = (resposta_usuario == resposta_correta)
    
    return render_template('resultado_exercicio.html', 
                           exercicio=exercicio_selecionado,
                           resposta_usuario=resposta_usuario,
                           correto=correto)


# --- ROTAS DE PROVAS (ALUNO) ---
@app.route('/provas')
@login_required
def lista_provas():
    todas_as_provas = carregar_provas()
    provas_por_curso = {}
    resultados_anteriores = carregar_resultados_provas()
    provas_realizadas = {res['prova_id'] for res in resultados_anteriores if res['usuario'] == session.get('username')}
    hoje = datetime.now().date()

    if session.get('role') in ['admin', 'professor']:
        for prova in todas_as_provas:
            curso = prova.get('curso', 'Sem Curso')
            if curso not in provas_por_curso:
                provas_por_curso[curso] = []
            provas_por_curso[curso].append(prova)
    else: # aluno
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            cursos_do_aluno = aluno_atual.get('curso')
            for curso_do_aluno in cursos_do_aluno:
                provas_do_curso = [p for p in todas_as_provas if p.get('curso') == curso_do_aluno]
                
                for prova in provas_do_curso:
                    prova['status'] = 'Disponível'
                    
                    data_inicio_prova = datetime.strptime(prova.get('data_inicio'), '%Y-%m-%d').date() if prova.get('data_inicio') else None
                    data_fim_prova = datetime.strptime(prova.get('data_fim'), '%Y-%m-%d').date() if prova.get('data_fim') else None
                    
                    if prova.get('id') in provas_realizadas:
                        prova['status'] = 'Concluída'
                    elif data_inicio_prova and data_inicio_prova > hoje:
                        prova['status'] = 'Não iniciada'
                    elif data_fim_prova and data_fim_prova < hoje:
                        prova['status'] = 'Expirada'
                    
                    if curso_do_aluno not in provas_por_curso:
                        provas_por_curso[curso_do_aluno] = []
                    provas_por_curso[curso_do_aluno].append(prova)

    return render_template('provas.html', provas_por_curso=provas_por_curso)

@app.route('/prova/<prova_id>')
@login_required
def ver_prova(prova_id):
    todas_as_provas = carregar_provas()
    prova_selecionada = next((p for p in todas_as_provas if p.get('id') == prova_id), None)
    
    if not prova_selecionada:
        flash('Prova não encontrada.', 'danger')
        return redirect(url_for('lista_provas'))

    hoje = datetime.now().date()
    data_inicio_prova = datetime.strptime(prova_selecionada.get('data_inicio'), '%Y-%m-%d').date() if prova_selecionada.get('data_inicio') else None
    data_fim_prova = datetime.strptime(prova_selecionada.get('data_fim'), '%Y-%m-%d').date() if prova_selecionada.get('data_fim') else None
    
    resultados_anteriores = carregar_resultados_provas()
    prova_ja_feita = any(res['prova_id'] == prova_id and res['usuario'] == session.get('username') for res in resultados_anteriores)
    
    if session.get('role') not in ['admin', 'professor']:
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if not aluno_atual or prova_selecionada.get('curso') not in aluno_atual.get('curso', []):
            flash('Você não tem permissão para ver esta prova.', 'danger')
            return redirect(url_for('lista_aulas'))
        
        if prova_ja_feita:
            flash('Você já realizou esta prova.', 'warning')
            return redirect(url_for('lista_provas'))
        
        if data_inicio_prova and data_inicio_prova > hoje:
            flash('Esta prova ainda não está disponível.', 'warning')
            return redirect(url_for('lista_provas'))
            
        if data_fim_prova and data_fim_prova < hoje:
            flash('O prazo para realizar esta prova já expirou.', 'danger')
            return redirect(url_for('lista_provas'))

    return render_template('ver_prova.html', prova=prova_selecionada)


@app.route('/corrigir_prova/<prova_id>', methods=['POST'])
@login_required
def corrigir_prova(prova_id):
    todas_as_provas = carregar_provas()
    prova_selecionada = next((p for p in todas_as_provas if p.get('id') == prova_id), None)
    
    if not prova_selecionada:
        flash('Prova não encontrada.', 'danger')
        return redirect(url_for('lista_provas'))
    
    respostas_usuario = request.form
    pontuacao = 0
    total_questoes = len(prova_selecionada['questoes'])

    respostas_detalhadas = []
    for questao in prova_selecionada['questoes']:
        resposta_usuario = respostas_usuario.get(f"questao_{questao['id']}")
        correta = (resposta_usuario == questao['resposta_correta'])
        if correta:
            pontuacao += 1
        respostas_detalhadas.append({
            'pergunta': questao['pergunta'],
            'resposta_usuario': resposta_usuario,
            'resposta_correta': questao['resposta_correta'],
            'correta': correta
        })
    
    resultados = carregar_resultados_provas()
    novo_resultado = {
        'id': str(int(time.time())),
        'prova_id': prova_id,
        'titulo_prova': prova_selecionada['titulo'],
        'curso': prova_selecionada['curso'],
        'usuario': session['username'],
        'pontuacao': pontuacao,
        'total_questoes': total_questoes,
        'data': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'respostas_detalhadas': respostas_detalhadas
    }
    resultados.append(novo_resultado)
    salvar_resultados_provas(resultados)
    app.logger.info(f"Usuário '{session['username']}' concluiu a prova '{prova_selecionada['titulo']}' com pontuação {pontuacao}/{total_questoes}.")
    
    # --- NOVO CÓDIGO DE GAMIFICAÇÃO ---
    novas_conquistas = verificar_e_atribuir_conquistas(session['username'])
    for conquista in novas_conquistas:
        flash(f'🎉 Nova Conquista Desbloqueada: {conquista["titulo"]}!', 'success')
        socketio.emit('nova_conquista', {'usuario': session['username'], 'titulo': conquista['titulo']})

    # --- FIM DO NOVO CÓDIGO ---

    return render_template('resultado_prova.html', 
                           prova=prova_selecionada,
                           pontuacao=pontuacao,
                           total_questoes=total_questoes,
                           respostas_detalhadas=respostas_detalhadas)

# --- ROTAS DE GERENCIAMENTO (ADMIN) DE ALUNOS E AULAS ---
@app.route('/gerenciar_alunos', methods=['GET', 'POST'])
@login_required
@permission_required(['admin']) # Apenas admins podem gerenciar alunos
def gerenciar_alunos():
    if request.method == 'POST':
        nome = request.form['nome']
        
        # Carrega a lista completa de pessoas e usuários para a checagem de unicidade
        todas_pessoas = carregar_dados()
        todos_usuarios = carregar_usuarios()
        
        if any(p.get('nome') == nome for p in todas_pessoas) or any(u.get('username') == nome for u in todos_usuarios):
            flash(f"O nome '{nome}' já está em uso como aluno ou usuário. Tente outro.", 'danger')
            return redirect(url_for('gerenciar_alunos'))
        
        role = request.form['role']
        horas_estudo = None
        curso = []
        if role == 'aluno':
            horas_estudo = float(request.form['horas_estudo'])
            curso = request.form.getlist('curso')
        elif role == 'professor':
            curso = request.form.getlist('curso')
        
        novo_aluno = {
            "nome": nome,
            "nascimento": request.form['nascimento'],
            "curso": curso,
            "horas_estudo": horas_estudo,
            "celular": request.form.get('celular'),
            "cep": request.form.get('cep'),
            "rua": request.form.get('rua'),
            "bairro": request.form.get('bairro'),
            "cidade": request.form.get('cidade'),
            "numero": request.form.get('numero'),
            "complemento": request.form.get('complemento')
        }
        todas_pessoas.append(novo_aluno)
        salvar_dados(todas_pessoas)
        app.logger.info(f"Admin '{session['username']}' ADICIONOU o aluno '{nome}'.")
        flash(f"Aluno '{nome}' cadastrado com sucesso!", 'success')

        password = request.form['password']
        if not password:
            flash('A senha é obrigatória ao criar um login.', 'danger')
            return redirect(url_for('gerenciar_alunos'))
        password_hash = generate_password_hash(password)
        novo_usuario = { "username": nome, "password_hash": password_hash, "role": role }
        todos_usuarios.append(novo_usuario)
        salvar_usuarios(todos_usuarios)
        app.logger.info(f"Admin '{session['username']}' CRIOU a conta de login para '{nome}'.")
        flash(f"Conta de login para '{nome}' criada com sucesso!", 'success')
        
        return redirect(url_for('gerenciar_alunos'))

    alunos = carregar_dados()
    return render_template('gerenciar_alunos.html', alunos=alunos)

@app.route('/editar_aluno/<nome_do_aluno>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin'])
def editar_aluno(nome_do_aluno):
    todos_dados = carregar_dados()
    aluno_para_editar = next((aluno for aluno in todos_dados if aluno.get('nome') == nome_do_aluno), None)
    if not aluno_para_editar:
        return redirect(url_for('gerenciar_alunos'))

    if request.method == 'POST':
        aluno_para_editar['nascimento'] = request.form['nascimento']
        
        role = request.form.get('role')
        if role == 'aluno':
            aluno_para_editar['horas_estudo'] = float(request.form['horas_estudo'])
            aluno_para_editar['curso'] = request.form.getlist('curso')
        elif role == 'professor':
            aluno_para_editar['horas_estudo'] = None
            aluno_para_editar['curso'] = request.form.getlist('curso')
        else: # admin
            aluno_para_editar['horas_estudo'] = None
            aluno_para_editar['curso'] = []

        aluno_para_editar['celular'] = request.form.get('celular')
        aluno_para_editar['cep'] = request.form.get('cep')
        aluno_para_editar['rua'] = request.form.get('rua')
        aluno_para_editar['bairro'] = request.form.get('bairro')
        aluno_para_editar['cidade'] = request.form.get('cidade')
        aluno_para_editar['numero'] = request.form.get('numero')
        aluno_para_editar['complemento'] = request.form.get('complemento')
        salvar_dados(todos_dados)
        app.logger.info(f"Admin '{session['username']}' EDITOU o aluno '{nome_do_aluno}'.")
        flash(f"Aluno '{nome_do_aluno}' atualizado com sucesso!", 'success')
        
        if 'role' in request.form:
            usuarios = carregar_usuarios()
            usuario_correspondente = next((u for u in usuarios if u.get('username') == nome_do_aluno), None)
            if usuario_correspondente:
                usuario_correspondente['role'] = request.form['role']
                salvar_usuarios(usuarios)
                app.logger.info(f"Admin '{session['username']}' ALTEROU a permissão de '{nome_do_aluno}'.")
                flash(f"Permissão do usuário '{nome_do_aluno}' atualizada.", 'success')
        return redirect(url_for('gerenciar_alunos'))

    usuarios = carregar_usuarios()
    usuario_correspondente = next((u for u in usuarios if u.get('username') == nome_do_aluno), None)
    return render_template('editar_aluno.html', aluno=aluno_para_editar, usuario=usuario_correspondente)

@app.route('/deletar_aluno/<nome_do_aluno>')
@login_required
@permission_required(['admin'])
def deletar_aluno(nome_do_aluno):
    alunos = carregar_dados()
    alunos_filtrados = [aluno for aluno in alunos if aluno.get('nome') != nome_do_aluno]
    salvar_dados(alunos_filtrados)
    app.logger.info(f"Admin '{session['username']}' DELETOU o aluno '{nome_do_aluno}'.")

    usuarios = carregar_usuarios()
    usuarios_filtrados = [user for user in usuarios if user.get('username') != nome_do_aluno]
    salvar_usuarios(usuarios_filtrados)
    app.logger.info(f"Admin '{session['username']}' DELETOU o usuário associado a '{nome_do_aluno}'.")

    flash(f"Aluno '{nome_do_aluno}' e sua conta de login (se existente) foram deletados.", 'success')
    return redirect(url_for('gerenciar_alunos'))

@app.route('/gerenciar_aulas')
@login_required
@permission_required(['admin', 'professor'])
def gerenciar_aulas():
    aulas = carregar_aulas()
    return render_template('gerenciar_aulas.html', aulas=aulas)

@app.route('/criar_aula', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'professor'])
def criar_aula():
    if request.method == 'POST':
        aulas = carregar_aulas()
        
        nova_aula = {
            "id": str(int(time.time())),
            "titulo": request.form['titulo'],
            "curso": request.form['curso'],
            "conteudo": request.form['conteudo']
        }
        aulas.append(nova_aula)
        salvar_aulas(aulas)
        flash('Aula criada com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' CRIOU a aula '{nova_aula['titulo']}'.")
        socketio.emit('nova_aula_ou_prova', {'titulo': nova_aula['titulo'], 'tipo': 'aula'}, broadcast=True)
        return redirect(url_for('gerenciar_aulas'))
        
    return render_template('criar_editar_aula.html', aula=None)

@app.route('/editar_aula/<aula_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'professor'])
def editar_aula(aula_id):
    aulas = carregar_aulas()
    aula_para_editar = next((a for a in aulas if a.get('id') == aula_id), None)
    if not aula_para_editar:
        return redirect(url_for('gerenciar_aulas'))

    if request.method == 'POST':
        aula_para_editar['titulo'] = request.form['titulo']
        aula_para_editar['curso'] = request.form['curso']
        aula_para_editar['conteudo'] = request.form['conteudo']
        salvar_aulas(aulas)
        flash('Aula atualizada com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' EDITOU a aula '{aula_para_editar['titulo']}'.")
        return redirect(url_for('gerenciar_aulas'))

    return render_template('criar_editar_aula.html', aula=aula_para_editar)

@app.route('/deletar_aula/<aula_id>')
@login_required
@permission_required(['admin', 'professor'])
def deletar_aula(aula_id):
    aulas = carregar_aulas()
    aula_deletada = next((a for a in aulas if a.get('id') == aula_id), None)
    aulas_filtradas = [a for a in aulas if a.get('id') != aula_id]
    if len(aulas) > len(aulas_filtradas) and aula_deletada:
        salvar_aulas(aulas_filtradas)
        flash(f"Aula '{aula_deletada['titulo']}' deletada com sucesso!", 'success')
        app.logger.info(f"Admin '{session['username']}' DELETOU a aula '{aula_deletada['titulo']}'.")
    return redirect(url_for('gerenciar_aulas'))

# --- ROTAS DE GERENCIAMENTO (ADMIN) DE EXERCÍCIOS ---
@app.route('/gerenciar_exercicios')
@login_required
@permission_required(['admin', 'professor'])
def gerenciar_exercicios():
    exercicios = carregar_exercicios()
    return render_template('gerenciar_exercicios.html', exercicios=exercicios)

@app.route('/criar_exercicio', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'professor'])
def criar_exercicio():
    if request.method == 'POST':
        exercicios = carregar_exercicios()
        
        # Coleta os dados de múltiplos exercícios
        questoes = request.form.getlist('pergunta')
        imagem_urls = request.form.getlist('imagem_url')
        opcoes_a = request.form.getlist('opcao_a')
        opcoes_b = request.form.getlist('opcao_b')
        opcoes_c = request.form.getlist('opcao_c')
        opcoes_d = request.form.getlist('opcao_d')
        respostas_corretas = request.form.getlist('resposta_correta')
        curso = request.form.get('curso')
        imagem_widths = request.form.getlist('imagem_width')

        for i in range(len(questoes)):
            if questoes[i]: # Adiciona apenas se a pergunta não estiver vazia
                novo_exercicio = {
                    "id": str(int(time.time())) + str(random.randint(100, 999)),
                    "curso": curso,
                    "pergunta": questoes[i],
                    "imagem_url": imagem_urls[i] if imagem_urls and len(imagem_urls) > i else '',
                    "imagem_width": imagem_widths[i] if imagem_widths and len(imagem_widths) > i else '100%',
                    "opcoes": [opcoes_a[i], opcoes_b[i], opcoes_c[i], opcoes_d[i]],
                    "resposta_correta": respostas_corretas[i]
                }
                exercicios.append(novo_exercicio)

        salvar_exercicios(exercicios)
        flash('Exercícios criados com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' CRIOU novos exercícios para o curso '{curso}'.")
        return redirect(url_for('gerenciar_exercicios'))
    
    return render_template('criar_editar_exercicio.html', exercicio=None)

@app.route('/editar_exercicio/<exercicio_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'professor'])
def editar_exercicio(exercicio_id):
    exercicios = carregar_exercicios()
    exercicio_para_editar = next((ex for ex in exercicios if ex.get('id') == exercicio_id), None)
    if not exercicio_para_editar:
        return redirect(url_for('gerenciar_exercicios'))

    if request.method == 'POST':
        # Coleta apenas os dados do formulário de edição de um único exercício
        exercicio_para_editar['curso'] = request.form.get('curso')
        exercicio_para_editar['pergunta'] = request.form.get('pergunta')
        exercicio_para_editar['imagem_url'] = request.form.get('imagem_url', '')
        exercicio_para_editar['imagem_width'] = request.form.get('imagem_width', '100%')
        exercicio_para_editar['opcoes'] = [
            request.form.get('opcao_a'),
            request.form.get('opcao_b'),
            request.form.get('opcao_c'),
            request.form.get('opcao_d')
        ]
        exercicio_para_editar['resposta_correta'] = request.form.get('resposta_correta')
        salvar_exercicios(exercicios)
        flash('Exercício atualizado com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' EDITOU o exercício '{exercicio_para_editar['pergunta']}'.")
        return redirect(url_for('gerenciar_exercicios'))
    
    return render_template('criar_editar_exercicio.html', exercicio=exercicio_para_editar)

@app.route('/deletar_exercicio/<exercicio_id>')
@login_required
@permission_required(['admin', 'professor'])
def deletar_exercicio(exercicio_id):
    exercicios = carregar_exercicios()
    exercicio_deletado = next((ex for ex in exercicios if ex.get('id') == exercicio_id), None)
    exercicios_filtrados = [ex for ex in exercicios if ex.get('id') != exercicio_id]
    if len(exercicios) > len(exercicios_filtrados) and exercicio_deletado:
        salvar_exercicios(exercicios_filtrados)
        flash(f"Exercício deletado com sucesso!", 'success')
        app.logger.info(f"Admin '{session['username']}' DELETOU o exercício '{exercicio_deletado['pergunta']}'.")
    return redirect(url_for('gerenciar_exercicios'))


# --- ROTAS DE GERENCIAMENTO (ADMIN) DE PROVAS ---
@app.route('/gerenciar_provas')
@login_required
@permission_required(['admin', 'professor'])
def gerenciar_provas():
    provas = carregar_provas()
    return render_template('gerenciar_provas.html', provas=provas)

@app.route('/criar_prova', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'professor'])
def criar_prova():
    if request.method == 'POST':
        provas = carregar_provas()
        
        nova_prova = {
            "id": str(int(time.time())),
            "titulo": request.form['titulo'],
            "curso": request.form['curso'],
            "data_inicio": request.form['data_inicio'],
            "data_fim": request.form['data_fim'],
            "tempo_limite": request.form['tempo_limite'],
            "questoes": []
        }
        
        questoes_form = request.form.getlist('pergunta')
        imagem_urls = request.form.getlist('imagem_url')
        imagem_widths = request.form.getlist('imagem_width')
        opcoes_a_form = request.form.getlist('opcao_a')
        opcoes_b_form = request.form.getlist('opcao_b')
        opcoes_c_form = request.form.getlist('opcao_c')
        opcoes_d_form = request.form.getlist('opcao_d')
        respostas_corretas_form = request.form.getlist('resposta_correta')
        
        for i in range(len(questoes_form)):
            if questoes_form[i]:
                nova_prova['questoes'].append({
                    "id": str(i),
                    "pergunta": questoes_form[i],
                    "imagem_url": imagem_urls[i] if imagem_urls and len(imagem_urls) > i else '',
                    "imagem_width": imagem_widths[i] if imagem_widths and len(imagem_widths) > i else '100%',
                    "opcoes": [opcoes_a_form[i], opcoes_b_form[i], opcoes_c_form[i], opcoes_d_form[i]],
                    "resposta_correta": respostas_corretas_form[i]
                })

        provas.append(nova_prova)
        salvar_provas(provas)
        flash('Prova criada com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' CRIOU a prova '{nova_prova['titulo']}'.")
        socketio.emit('nova_aula_ou_prova', {'titulo': nova_prova['titulo'], 'tipo': 'prova'}, broadcast=True)
        return redirect(url_for('gerenciar_provas'))
    
    return render_template('criar_editar_prova.html', prova=None)


@app.route('/editar_prova/<prova_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'professor'])
def editar_prova(prova_id):
    provas = carregar_provas()
    prova_para_editar = next((p for p in provas if p.get('id') == prova_id), None)
    if not prova_para_editar:
        return redirect(url_for('gerenciar_provas'))

    if request.method == 'POST':
        prova_para_editar['titulo'] = request.form['titulo']
        prova_para_editar['curso'] = request.form['curso']
        prova_para_editar['data_inicio'] = request.form['data_inicio']
        prova_para_editar['data_fim'] = request.form['data_fim']
        prova_para_editar['tempo_limite'] = request.form['tempo_limite']
        
        questoes_form = request.form.getlist('pergunta')
        imagem_urls = request.form.getlist('imagem_url')
        imagem_widths = request.form.getlist('imagem_width')
        opcoes_a_form = request.form.getlist('opcao_a')
        opcoes_b_form = request.form.getlist('opcao_b')
        opcoes_c_form = request.form.getlist('opcao_c')
        opcoes_d_form = request.form.getlist('opcao_d')
        respostas_corretas_form = request.form.getlist('resposta_correta')
        
        prova_para_editar['questoes'] = []
        for i in range(len(questoes_form)):
            if questoes_form[i]:
                prova_para_editar['questoes'].append({
                    "id": str(i),
                    "pergunta": questoes_form[i],
                    "imagem_url": imagem_urls[i] if imagem_urls and len(imagem_urls) > i else '',
                    "imagem_width": imagem_widths[i] if imagem_widths and len(imagem_widths) > i else '100%',
                    "opcoes": [opcoes_a_form[i], opcoes_b_form[i], opcoes_c_form[i], opcoes_d_form[i]],
                    "resposta_correta": respostas_corretas_form[i]
                })
        
        salvar_provas(provas)
        flash('Prova atualizada com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' EDITOU a prova '{prova_para_editar['titulo']}'.")
        return redirect(url_for('gerenciar_provas'))
        
    return render_template('criar_editar_prova.html', prova=prova_para_editar)

@app.route('/deletar_prova/<prova_id>')
@login_required
@permission_required(['admin', 'professor'])
def deletar_prova(prova_id):
    provas = carregar_provas()
    prova_deletada = next((p for p in provas if p.get('id') == prova_id), None)
    provas_filtradas = [p for p in provas if p.get('id') != prova_id]
    if len(provas) > len(provas_filtradas) and prova_deletada:
        salvar_provas(provas_filtradas)
        flash(f"Prova '{prova_deletada['titulo']}' deletada com sucesso!", 'success')
        app.logger.info(f"Admin '{session['username']}' DELETOU a prova '{prova_deletada['titulo']}'.")
    return redirect(url_for('gerenciar_provas'))
    
# --- ROTAS DE RESULTADOS DE PROVAS ---
@app.route('/gerenciar_resultados_provas')
@login_required
@permission_required(['admin', 'professor'])
def gerenciar_resultados_provas():
    resultados = carregar_resultados_provas()
    return render_template('gerenciar_resultados_provas.html', resultados=resultados)

@app.route('/ver_resultado_prova/<resultado_id>')
@login_required
@permission_required(['admin', 'professor'])
def ver_resultado_prova(resultado_id):
    resultados = carregar_resultados_provas()
    resultado_selecionado = next((r for r in resultados if r.get('id') == resultado_id), None)
    if not resultado_selecionado:
        flash('Resultado não encontrado.', 'danger')
        return redirect(url_for('gerenciar_resultados_provas'))
    return render_template('ver_resultado_prova.html', resultado=resultado_selecionado)

@app.route('/meu_boletim')
@login_required
def meu_boletim():
    username = session.get('username')
    resultados = carregar_resultados_provas()
    meus_resultados = [r for r in resultados if r.get('usuario') == username]
    return render_template('boletim.html', resultados=meus_resultados)

# --- NOVAS ROTAS DE EXPORTAÇÃO ---
@app.route('/exportar_boletim/<formato>')
@login_required
def exportar_boletim(formato):
    username = session.get('username')
    resultados = [r for r in carregar_resultados_provas() if r.get('usuario') == username]
    if not resultados:
        flash("Nenhum resultado para exportar.", "warning")
        return redirect(url_for('meu_boletim'))
    
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    
    if formato == 'pdf':
        try:
            from weasyprint import HTML
            html_renderizado = render_template('boletim_pdf.html', resultados=resultados, username=username, data_hoje=data_hoje)
            pdf = HTML(string=html_renderizado).write_pdf()
            return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=boletim_{username}.pdf'})
        except ImportError:
            flash("Biblioteca WeasyPrint não encontrada para gerar PDF.", "danger")
            return redirect(url_for('meu_boletim'))
    
    if formato == 'excel':
        try:
            import pandas as pd
            import io
            from openpyxl import Workbook
            df = pd.DataFrame([
                {'Usuário': r['usuario'], 'Pontuação': f"{r['pontuacao']}/{r['total_questoes']}", 'Data': r['data']}
                for r in resultados
            ])
            output = io.BytesIO()
            writer = pd.ExcelWriter(output, engine='openpyxl')
            df.to_excel(writer, index=False, sheet_name='Boletim')
            writer.close()
            output.seek(0)
            return Response(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment;filename=boletim_{username}.xlsx'})
        except ImportError:
            flash("Bibliotecas Pandas/OpenPyXL não encontradas para gerar Excel.", "danger")
            return redirect(url_for('meu_boletim'))
    
    return redirect(url_for('meu_boletim'))

@app.route('/exportar_resultados_prova/<prova_id>/<formato>')
@login_required
@permission_required(['admin', 'professor'])
def exportar_resultados_prova(prova_id, formato):
    prova = buscar_prova_por_id(prova_id)
    if not prova:
        flash("Prova não encontrada.", "danger")
        return redirect(url_for('gerenciar_provas'))
        
    resultados = buscar_resultados_por_prova_id(prova_id)
    if not resultados:
        flash("Nenhum resultado para esta prova foi encontrado para exportar.", "warning")
        return redirect(url_for('gerenciar_provas'))
    
    data_hoje = datetime.now().strftime("%d/%m/%Y")

    if formato == 'pdf':
        try:
            from weasyprint import HTML
            html_renderizado = render_template('relatorio_provas_pdf.html', prova=prova, resultados=resultados, data_hoje=data_hoje)
            pdf = HTML(string=html_renderizado).write_pdf()
            return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=resultados_prova_{prova_id}.pdf'})
        except ImportError:
            flash("Biblioteca WeasyPrint não encontrada para gerar PDF.", "danger")
            return redirect(url_for('gerenciar_provas'))
            
    if formato == 'excel':
        try:
            import pandas as pd
            import io
            df = pd.DataFrame([
                {'Usuário': r['usuario'], 'Pontuação': f"{r['pontuacao']}/{r['total_questoes']}", 'Data': r['data']}
                for r in resultados
            ])
            output = io.BytesIO()
            writer = pd.ExcelWriter(output, engine='openpyxl')
            df.to_excel(writer, index=False, sheet_name=f'Resultados Prova {prova_id}')
            writer.close()
            output.seek(0)
            return Response(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment;filename=resultados_prova_{prova_id}.xlsx'})
        except ImportError:
            flash("Bibliotecas Pandas/OpenPyXL não encontradas para gerar Excel.", "danger")
            return redirect(url_for('gerenciar_provas'))
            
    return redirect(url_for('gerenciar_provas'))

# --- OUTRAS ROTAS GERAIS ---
@app.route('/relatorio')
@login_required
def relatorio():
    dados_relatorio = gerar_relatorio_dados()
    return render_template('relatorio.html', dados=dados_relatorio)

@app.route('/logs')
@login_required
@permission_required(['admin'])
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

@app.route('/exportar/<formato>')
@login_required
def exportar(formato):
    app.logger.info(f"Usuário '{session['username']}' EXPORTOU os dados para {formato.upper()}.")
    alunos = carregar_alunos()
    if formato == 'pdf':
        try:
            from weasyprint import HTML
            theme_color = request.args.get('color', '#4a90e2')
            dados_relatorio = gerar_relatorio_dados()
            data_atual = datetime.now().strftime("%d/%m/%Y")
            html_renderizado = render_template('relatorio_pdf.html', alunos=alunos, dados=dados_relatorio, data_hoje=data_atual, theme_color=theme_color)
            pdf = HTML(string=html_renderizado).write_pdf()
            return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=relatorio_alunos.pdf'})
        except ImportError:
            flash("Biblioteca WeasyPrint não encontrada para gerar PDF.", "danger")
            return redirect(url_for('lista_alunos'))
    if formato == 'excel':
        try:
            import pandas as pd
            import io
            df = pd.DataFrame(alunos)
            output = io.BytesIO()
            writer = pd.ExcelWriter(output, engine='openyxl')
            df.to_excel(writer, index=False, sheet_name='Alunos')
            writer.close()
            output.seek(0)
            return Response(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment;filename=relatorio_alunos.xlsx'})
        except ImportError:
            flash("Bibliotecas Pandas/OpenPyXL não encontradas para gerar Excel.", "danger")
            return redirect(url_for('lista_alunos'))
    return redirect(url_for('lista_alunos'))

@app.route('/assistente_ia')
@login_required
def assistente_ia():
    return render_template('assistente_ia.html')

@socketio.on('enviar_mensagem')
@login_required
def handle_message(data):
    user_message = data['message']
    username = session['username']
    
    # Adiciona a mensagem do usuário ao chat para o remetente
    emit('receber_mensagem', {'user': username, 'message': user_message}, room=request.sid)

    # Lógica para chamar a API da IA e obter a resposta
    response_text = ""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            response_text = 'Chave de API do Gemini não configurada.'
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            # NOVO PAYLOAD COM INSTRUÇÕES PARA A IA SER CONCISA
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": "Instruções: Responda de forma concisa e utilize listas ou parágrafos curtos para facilitar a leitura. Use emojis quando apropriado. O usuário perguntou:"},
                            {"text": user_message}
                        ]
                    }
                ]
            }

            response = requests.post(url, json=payload)
            response.raise_for_status()
            response_data = response.json()
            response_text = response_data['candidates'][0]['content']['parts'][0]['text']
    except requests.exceptions.RequestException as req_err:
        response_text = f"Desculpe, houve um erro na comunicação com a API de IA. Detalhes: {req_err}"
    except (KeyError, IndexError) as parse_err:
        response_text = f"Desculpe, a resposta da API de IA não pôde ser interpretada. Detalhes: {parse_err}. Resposta completa da API: {response.text}"
    except Exception as e:
        response_text = f"Ocorreu um erro inesperado ao usar a IA. Erro: {str(e)}"
    
    # Emite a resposta da IA de volta apenas para o remetente
    emit('receber_mensagem', {'user': 'IA', 'message': response_text}, room=request.sid)

# --- ROTAS DO FÓRUM ---
@app.route('/forum', methods=['GET'])
@login_required
def forum():
    posts = carregar_forum()
    
    posts_por_curso = defaultdict(list)
    for post in posts:
        posts_por_curso[post.get('curso', 'Sem Curso')].append(post)
        
    return render_template('forum.html', posts_por_curso=posts_por_curso)

@app.route('/novo_post', methods=['GET', 'POST'])
@login_required
def novo_post():
    if request.method == 'POST':
        posts = carregar_forum()
        novo_post = {
            "id": str(int(time.time())),
            "autor": session['username'],
            "titulo": request.form['titulo'],
            "curso": request.form['curso'],
            "conteudo": request.form['conteudo'],
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "visualizacoes": 0,
            "respostas": []
        }
        posts.insert(0, novo_post)
        salvar_forum(posts)
        flash('Tópico publicado com sucesso!', 'success')
        return redirect(url_for('forum'))
    
    return render_template('novo_post.html')

@app.route('/ver_post/<post_id>', methods=['GET', 'POST'])
@login_required
def ver_post(post_id):
    post = buscar_post_por_id(post_id)
    if not post:
        flash('Tópico não encontrado.', 'danger')
        return redirect(url_for('forum'))

    if request.method == 'POST':
        posts = carregar_forum()
        for p in posts:
            if p['id'] == post_id:
                p['respostas'].append({
                    "autor": session['username'],
                    "conteudo": request.form['comentario'],
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M")
                })
                break
        salvar_forum(posts)
        flash('Comentário adicionado com sucesso!', 'success')
        return redirect(url_for('ver_post', post_id=post_id))

    posts = carregar_forum()
    for p in posts:
        if p['id'] == post_id:
            p['visualizacoes'] += 1
            break
    salvar_forum(posts)

    return render_template('ver_post.html', post=post)

@app.route('/deletar_post/<post_id>', methods=['POST'])
@login_required
@permission_required(['admin', 'professor'])
def deletar_post(post_id):
    posts = carregar_forum()
    posts_filtrados = [p for p in posts if p.get('id') != post_id]
    salvar_forum(posts_filtrados)
    flash('Tópico deletado com sucesso.', 'success')
    return redirect(url_for('forum'))

# --- ROTAS DE GAMIFICAÇÃO ---
@app.route('/minhas_conquistas')
@login_required
@permission_required(['aluno'])
def minhas_conquistas():
    username = session.get('username')
    
    # Carrega os dados do aluno
    pessoas = carregar_dados()
    aluno = next((p for p in pessoas if p.get('nome') == username), None)
    
    # Carrega todas as conquistas definidas e as que o aluno já tem
    todas_conquistas = carregar_conquistas_definidas()
    conquistas_aluno = {c['id']: c for c in aluno.get('conquistas', [])} if aluno else {}
    
    return render_template('minhas_conquistas.html', 
                           todas_conquistas=todas_conquistas, 
                           conquistas_aluno=conquistas_aluno,
                           aluno=aluno)

@app.route('/ranking')
@login_required
@permission_required(['aluno'])
def ranking():
    rankings = calcular_ranking_por_curso()
    return render_template('ranking.html', rankings=rankings)

@app.route('/meu_progresso')
@login_required
@permission_required(['aluno'])
def meu_progresso():
    username = session.get('username')
    todos_resultados = carregar_resultados_provas()
    resultados_aluno = [r for r in todos_resultados if r.get('usuario') == username]
    alunos_todos = carregar_alunos()
    aluno_atual = next((aluno for aluno in alunos_todos if aluno.get('nome') == username), None)
    
    # Chama a nova função para pegar dados de progresso por curso/tópico
    progresso_por_curso = calcular_progresso_por_curso_e_topico(username)
    
    # Prepara os dados para o dashboard
    dados_dashboard = {
        'kpis': {
            'media_geral': 0,
            'provas_realizadas': len(resultados_aluno),
            'horas_estudo': aluno_atual.get('horas_estudo', 0) if aluno_atual else 0
        },
        'desempenho_cursos': [],
        'atividades_recentes': [],
        'progresso_por_curso': progresso_por_curso,
        'media_turma_horas': {}
    }

    if resultados_aluno:
        cursos = {}
        total_pontos_geral = 0
        total_questoes_geral = 0

        for res in resultados_aluno:
            curso = res.get('curso', 'Geral')
            pontos = res.get('pontuacao', 0)
            questoes = res.get('total_questoes', 0)

            total_pontos_geral += pontos
            total_questoes_geral += questoes

            if curso not in cursos:
                cursos[curso] = {'total_pontos': 0, 'total_questoes': 0}
            cursos[curso]['total_pontos'] += pontos
            cursos[curso]['total_questoes'] += questoes
        
        # Calcula a média de acertos por curso
        for curso, data in cursos.items():
            if data['total_questoes'] > 0:
                media = (data['total_pontos'] / data['total_questoes']) * 100
                dados_dashboard['desempenho_cursos'].append({
                    'curso': curso,
                    'media': round(media)
                })

                # Novo: Calcula a média de horas de estudo da turma
                media_turma = calcular_media_horas_estudo_por_curso(curso)
                dados_dashboard['media_turma_horas'][curso] = round(media_turma, 1)

        # Calcula a média geral
        if total_questoes_geral > 0:
            media_geral = (total_pontos_geral / total_questoes_geral) * 100
            dados_dashboard['kpis']['media_geral'] = round(media_geral, 2)

        # Prepara a lista de atividades recentes (as últimas 5)
        resultados_ordenados = sorted(resultados_aluno, key=lambda x: datetime.strptime(x['data'], "%d/%m/%Y %H:%M:%S"), reverse=True)
        for res in resultados_ordenados[:5]:
            score_percent = (res['pontuacao'] / res['total_questoes'] * 100) if res['total_questoes'] > 0 else 0
            dados_dashboard['atividades_recentes'].append({
                'titulo': res['titulo_prova'],
                'data': res['data'].split(' ')[0],
                'pontuacao': f"{res['pontuacao']}/{res['total_questoes']}",
                'score_percent': round(score_percent)
            })

    return render_template('meu_progresso.html', dados=dados_dashboard, aluno=aluno_atual)

# --- NOVA ROTA PARA O DASHBOARD DO PROFESSOR ---
@app.route('/dashboard_professor')
@login_required
@permission_required(['professor', 'admin'])
def dashboard_professor():
    provas = carregar_provas()
    resultados = carregar_resultados_provas()
    alunos = carregar_alunos()
    
    dados = {
        'media_geral_turma': 0,
        'total_provas': len(provas),
        'media_horas_estudo_turma': 0,
        'media_notas_provas': [],
        'provas_dificeis': [],
        'alunos_baixo_desempenho': [],
        'questoes_criticas': None
    }
    
    # 1. Média de horas de estudo da turma
    total_horas = sum(a['horas_estudo'] for a in alunos if a.get('horas_estudo') is not None)
    if alunos:
        dados['media_horas_estudo_turma'] = round(total_horas / len(alunos), 1)

    # 2. Média de notas por prova
    medias_por_prova = calcular_media_notas_por_prova()
    if medias_por_prova:
        dados['media_notas_provas'] = sorted(medias_por_prova, key=lambda x: x['titulo'])
        
        # 3. Média geral da turma
        total_medias = sum(p['media'] for p in medias_por_prova)
        dados['media_geral_turma'] = round(total_medias / len(medias_por_prova), 2)

    # 4. Provas mais difíceis (top 3 com as menores médias)
    provas_ordenadas = sorted(medias_por_prova, key=lambda x: x['media'])
    dados['provas_dificeis'] = provas_ordenadas[:3]

    # 5. Alunos com baixo desempenho (top 5 com as menores médias)
    dados['alunos_baixo_desempenho'] = identificar_alunos_com_baixo_desempenho()

    # 6. Questões críticas da prova mais difícil
    if provas_ordenadas:
        prova_mais_dificil_id = provas_ordenadas[0]['id']
        questoes = identificar_questoes_criticas(prova_mais_dificil_id)
        if questoes:
            dados['questoes_criticas'] = {
                'titulo_prova': provas_ordenadas[0]['titulo'],
                'questoes': questoes
            }
            
    return render_template('dashboard_professor.html', dados=dados)


if __name__ == '__main__':
    socketio.run(app, debug=True)