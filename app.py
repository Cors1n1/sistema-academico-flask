from flask import Flask, render_template, request, redirect, url_for, Response, session, flash
from functools import wraps
from funcoes.funcoes import (
    carregar_dados, salvar_dados, gerar_relatorio_dados, 
    carregar_usuarios, salvar_usuarios, carregar_aulas, salvar_aulas,
    carregar_exercicios, salvar_exercicios, carregar_provas, salvar_provas
)
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
import time
import random

app = Flask(__name__)
app.secret_key = 'chave-secreta-para-o-projeto-unip-12345'

# CONFIGURAÇÃO DO LOG
handler = RotatingFileHandler('app.log', maxBytes=100000, backupCount=3, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# DECORATORS DE PERMISSÃO
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

# --- ROTAS DA APLICAÇÃO GERAL ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/meu_perfil')
@login_required
def meu_perfil():
    username = session.get('username')
    alunos = carregar_dados()
    aluno_correspondente = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
    return render_template('meu_perfil.html', aluno=aluno_correspondente)

@app.route('/lista_alunos')
@login_required
def lista_alunos():
    todos_alunos = carregar_dados()
    if session.get('role') == 'admin':
        return render_template('lista_alunos.html', alunos=todos_alunos)
    else:
        username = session.get('username')
        aluno_atual = next((aluno for aluno in todos_alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            curso_do_aluno = aluno_atual.get('curso')
            colegas_de_turma = [aluno for aluno in todos_alunos if aluno.get('curso') == curso_do_aluno]
            return render_template('lista_alunos.html', alunos=colegas_de_turma)
        else:
            return render_template('lista_alunos.html', alunos=[])

# --- ROTAS DE AULAS ---
@app.route('/aulas')
@login_required
def lista_aulas():
    todas_as_aulas = carregar_aulas()
    aulas_por_curso = {}
    if session.get('role') == 'admin':
        for aula in todas_as_aulas:
            curso = aula.get('curso')
            if curso not in aulas_por_curso:
                aulas_por_curso[curso] = []
            aulas_por_curso[curso].append(aula)
    else:
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            curso_do_aluno = aluno_atual.get('curso')
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
    
    if session.get('role') != 'admin':
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if not aluno_atual or aula_selecionada.get('curso') != aluno_atual.get('curso'):
            flash('Você não tem permissão para ver esta aula.', 'danger')
            return redirect(url_for('lista_aulas'))
    return render_template('ver_aula.html', aula=aula_selecionada)


# --- ROTAS DE EXERCÍCIOS (ALUNO) ---
@app.route('/lista_exercicios')
@login_required
def lista_exercicios():
    todos_exercicios = carregar_exercicios()
    exercicios_por_curso = {}

    if session.get('role') == 'admin':
        for exercicio in todos_exercicios:
            curso = exercicio.get('curso', 'Sem Curso')
            if curso not in exercicios_por_curso:
                exercicios_por_curso[curso] = []
            exercicios_por_curso[curso].append(exercicio)
    else:
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            curso_do_aluno = aluno_atual.get('curso')
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

    if session.get('role') != 'admin':
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if not aluno_atual or exercicio_selecionado.get('curso') != aluno_atual.get('curso'):
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

    if session.get('role') == 'admin':
        for prova in todas_as_provas:
            curso = prova.get('curso', 'Sem Curso')
            if curso not in provas_por_curso:
                provas_por_curso[curso] = []
            provas_por_curso[curso].append(prova)
    else:
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if aluno_atual:
            curso_do_aluno = aluno_atual.get('curso')
            provas_do_curso = [p for p in todas_as_provas if p.get('curso') == curso_do_aluno]
            if provas_do_curso:
                provas_por_curso[curso_do_aluno] = provas_do_curso

    return render_template('provas.html', provas_por_curso=provas_por_curso)

@app.route('/prova/<prova_id>')
@login_required
def ver_prova(prova_id):
    todas_as_provas = carregar_provas()
    prova_selecionada = next((p for p in todas_as_provas if p.get('id') == prova_id), None)
    
    if not prova_selecionada:
        flash('Prova não encontrada.', 'danger')
        return redirect(url_for('lista_provas'))

    if session.get('role') != 'admin':
        username = session.get('username')
        alunos = carregar_dados()
        aluno_atual = next((aluno for aluno in alunos if aluno.get('nome') == username), None)
        if not aluno_atual or prova_selecionada.get('curso') != aluno_atual.get('curso'):
            flash('Você não tem permissão para ver esta prova.', 'danger')
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
    
    return render_template('resultado_prova.html', 
                           prova=prova_selecionada,
                           pontuacao=pontuacao,
                           total_questoes=total_questoes,
                           respostas_detalhadas=respostas_detalhadas)

# --- ROTAS DE GERENCIAMENTO (ADMIN) DE ALUNOS E AULAS ---
@app.route('/gerenciar_alunos', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def gerenciar_alunos():
    if request.method == 'POST':
        nome = request.form['nome']
        alunos = carregar_dados()
        usuarios = carregar_usuarios()
        if any(aluno.get('nome') == nome for aluno in alunos) or any(u.get('username') == nome for u in usuarios):
            flash(f"O nome '{nome}' já está em uso como aluno ou usuário. Tente outro.", 'danger')
            return redirect(url_for('gerenciar_alunos'))
        
        novo_aluno = {
            "nome": nome, "idade": int(request.form['idade']),
            "curso": request.form['curso'], "horas_estudo": float(request.form['horas_estudo'])
        }
        alunos.append(novo_aluno)
        salvar_dados(alunos)
        app.logger.info(f"Admin '{session['username']}' ADICIONOU o aluno '{nome}'.")
        flash(f"Aluno '{nome}' cadastrado com sucesso!", 'success')

        if 'criar_login' in request.form:
            password = request.form['password']
            role = request.form['role']
            if not password:
                flash('A senha é obrigatória ao criar um login.', 'danger')
                return redirect(url_for('gerenciar_alunos'))
            password_hash = generate_password_hash(password)
            novo_usuario = { "username": nome, "password_hash": password_hash, "role": role }
            usuarios.append(novo_usuario)
            salvar_usuarios(usuarios)
            app.logger.info(f"Admin '{session['username']}' CRIOU a conta de login para '{nome}'.")
            flash(f"Conta de login para '{nome}' criada com sucesso!", 'success')
        
        return redirect(url_for('gerenciar_alunos'))

    alunos = carregar_dados()
    return render_template('gerenciar_alunos.html', alunos=alunos)

@app.route('/editar_aluno/<nome_do_aluno>', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def editar_aluno(nome_do_aluno):
    alunos = carregar_dados()
    aluno_para_editar = next((aluno for aluno in alunos if aluno.get('nome') == nome_do_aluno), None)
    if not aluno_para_editar: return redirect(url_for('gerenciar_alunos'))
    
    if request.method == 'POST':
        aluno_para_editar['idade'] = int(request.form['idade'])
        aluno_para_editar['curso'] = request.form['curso']
        aluno_para_editar['horas_estudo'] = float(request.form['horas_estudo'])
        salvar_dados(alunos)
        app.logger.info(f"Admin '{session['username']}' EDITOU o aluno '{nome_do_aluno}'.")
        flash(f"Aluno '{nome_do_aluno}' atualizado com sucesso!", 'success')
        
        if 'role' in request.form:
            usuarios = carregar_usuarios()
            for user in usuarios:
                if user.get('username') == nome_do_aluno:
                    user['role'] = request.form['role']
                    salvar_usuarios(usuarios)
                    app.logger.info(f"Admin '{session['username']}' ALTEROU a permissão de '{nome_do_aluno}'.")
                    flash(f"Permissão do usuário '{nome_do_aluno}' atualizada.", 'success')
                    break
        return redirect(url_for('gerenciar_alunos'))

    usuarios = carregar_usuarios()
    usuario_correspondente = next((u for u in usuarios if u.get('username') == nome_do_aluno), None)
    return render_template('editar_aluno.html', aluno=aluno_para_editar, usuario=usuario_correspondente)

@app.route('/deletar_aluno/<nome_do_aluno>')
@login_required
@permission_required('admin')
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
@permission_required('admin')
def gerenciar_aulas():
    aulas = carregar_aulas()
    return render_template('gerenciar_aulas.html', aulas=aulas)

@app.route('/criar_aula', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
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
        return redirect(url_for('gerenciar_aulas'))
        
    return render_template('criar_editar_aula.html', aula=None)

@app.route('/editar_aula/<aula_id>', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
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
@permission_required('admin')
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
@permission_required('admin')
def gerenciar_exercicios():
    exercicios = carregar_exercicios()
    return render_template('gerenciar_exercicios.html', exercicios=exercicios)

@app.route('/criar_exercicio', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def criar_exercicio():
    if request.method == 'POST':
        exercicios = carregar_exercicios()
        
        # Coleta os dados de múltiplos exercícios
        questoes = request.form.getlist('pergunta')
        opcoes_a = request.form.getlist('opcao_a')
        opcoes_b = request.form.getlist('opcao_b')
        opcoes_c = request.form.getlist('opcao_c')
        opcoes_d = request.form.getlist('opcao_d')
        respostas_corretas = request.form.getlist('resposta_correta')
        curso = request.form.get('curso')

        for i in range(len(questoes)):
            if questoes[i]: # Adiciona apenas se a pergunta não estiver vazia
                novo_exercicio = {
                    "id": str(int(time.time())) + str(random.randint(100, 999)),
                    "curso": curso,
                    "pergunta": questoes[i],
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
@permission_required('admin')
def editar_exercicio(exercicio_id):
    exercicios = carregar_exercicios()
    exercicio_para_editar = next((ex for ex in exercicios if ex.get('id') == exercicio_id), None)
    if not exercicio_para_editar:
        return redirect(url_for('gerenciar_exercicios'))
    
    if request.method == 'POST':
        # Coleta apenas os dados do formulário de edição de um único exercício
        exercicio_para_editar['curso'] = request.form.get('curso')
        exercicio_para_editar['pergunta'] = request.form.get('pergunta')
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
@permission_required('admin')
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
@permission_required('admin')
def gerenciar_provas():
    provas = carregar_provas()
    return render_template('gerenciar_provas.html', provas=provas)

@app.route('/criar_prova', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def criar_prova():
    if request.method == 'POST':
        provas = carregar_provas()
        
        nova_prova = {
            "id": str(int(time.time())),
            "titulo": request.form['titulo'],
            "curso": request.form['curso'],
            "questoes": []
        }
        
        questoes_form = request.form.getlist('pergunta')
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
                    "opcoes": [opcoes_a_form[i], opcoes_b_form[i], opcoes_c_form[i], opcoes_d_form[i]],
                    "resposta_correta": respostas_corretas_form[i]
                })

        provas.append(nova_prova)
        salvar_provas(provas)
        flash('Prova criada com sucesso!', 'success')
        app.logger.info(f"Admin '{session['username']}' CRIOU a prova '{nova_prova['titulo']}'.")
        return redirect(url_for('gerenciar_provas'))
    
    return render_template('criar_editar_prova.html', prova=None)


@app.route('/editar_prova/<prova_id>', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def editar_prova(prova_id):
    provas = carregar_provas()
    prova_para_editar = next((p for p in provas if p.get('id') == prova_id), None)
    if not prova_para_editar:
        return redirect(url_for('gerenciar_provas'))

    if request.method == 'POST':
        prova_para_editar['titulo'] = request.form['titulo']
        prova_para_editar['curso'] = request.form['curso']
        
        questoes_form = request.form.getlist('pergunta')
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
@permission_required('admin')
def deletar_prova(prova_id):
    provas = carregar_provas()
    prova_deletada = next((p for p in provas if p.get('id') == prova_id), None)
    provas_filtradas = [p for p in provas if p.get('id') != prova_id]
    if len(provas) > len(provas_filtradas) and prova_deletada:
        salvar_provas(provas_filtradas)
        flash(f"Prova '{prova_deletada['titulo']}' deletada com sucesso!", 'success')
        app.logger.info(f"Admin '{session['username']}' DELETOU a prova '{prova_deletada['titulo']}'.")
    return redirect(url_for('gerenciar_provas'))

# --- OUTRAS ROTAS GERAIS ---
@app.route('/relatorio')
@login_required
def relatorio():
    dados_relatorio = gerar_relatorio_dados()
    return render_template('relatorio.html', dados=dados_relatorio)

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

@app.route('/exportar/<formato>')
@login_required
def exportar(formato):
    app.logger.info(f"Usuário '{session['username']}' EXPORTOU os dados para {formato.upper()}.")
    alunos = carregar_dados()
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
            writer = pd.ExcelWriter(output, engine='openpyxl')
            df.to_excel(writer, index=False, sheet_name='Alunos')
            writer.close()
            output.seek(0)
            return Response(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment;filename=relatorio_alunos.xlsx'})
        except ImportError:
            flash("Bibliotecas Pandas/OpenPyXL não encontradas para gerar Excel.", "danger")
            return redirect(url_for('lista_alunos'))
    return redirect(url_for('lista_alunos'))

if __name__ == '__main__':
    app.run(debug=True)