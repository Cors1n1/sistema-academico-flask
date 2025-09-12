import json
import os
import random
import string
from datetime import datetime, timedelta
import jwt
from collections import defaultdict

# --- FUNÇÕES DE ALUNOS ---
def carregar_dados():
    if not os.path.exists("pessoas.json"): return []
    try:
        with open("pessoas.json", "r", encoding="utf-8") as f:
            pessoas = json.load(f)
            # Converte o campo 'curso' para uma lista se for uma string
            for p in pessoas:
                if 'curso' in p and isinstance(p['curso'], str):
                    p['curso'] = [p['curso']]
                if 'nascimento' in p and p['nascimento']:
                    try:
                        data_nascimento = datetime.strptime(p['nascimento'], '%Y-%m-%d').date()
                        hoje = datetime.now().date()
                        idade = hoje.year - data_nascimento.year - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
                        p['idade'] = idade
                    except (ValueError, TypeError):
                        p['idade'] = None
                else:
                    p['idade'] = None
            return sorted(pessoas, key=lambda x: x.get('nome', ''))
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def carregar_alunos():
    """Carrega apenas os dados de 'pessoas' que correspondem a usuários com a role 'aluno'."""
    todos_usuarios = carregar_usuarios()
    usuarios_alunos = {u['username'] for u in todos_usuarios if u.get('role') == 'aluno'}
    
    todas_pessoas = carregar_dados()
    # Filtra as pessoas para incluir apenas aquelas que são alunos
    alunos_filtrados = [p for p in todas_pessoas if p.get('nome') in usuarios_alunos]
    
    return sorted(alunos_filtrados, key=lambda x: x.get('nome', ''))

def salvar_dados(pessoas):
    with open("pessoas.json", "w", encoding="utf-8") as f:
        json.dump(pessoas, f, ensure_ascii=False, indent=4)

def gerar_relatorio_dados():
    alunos = carregar_alunos()
    if not alunos: return {"total_alunos": 0, "media_idades": "0.0", "media_horas": "0.0", "total_cursos": 0, "alunos_por_curso": {}, "faixas_idade": {}}

    total_alunos = len(alunos)
    idades_validas = [p.get('idade') for p in alunos if p.get('idade') is not None]
    soma_idades = sum(idades_validas)
    soma_horas = sum(p.get('horas_estudo', 0) for p in alunos)

    media_idades = soma_idades / len(idades_validas) if idades_validas else 0
    media_horas = soma_horas / total_alunos if total_alunos > 0 else 0

    todos_cursos = []
    for p in alunos:
        todos_cursos.extend(p.get('curso', []))
    cursos_unicos = sorted(list(set(todos_cursos)))

    alunos_por_curso = {curso: todos_cursos.count(curso) for curso in cursos_unicos}

    faixas_idade = {
        '0-17': len([i for i in idades_validas if i < 18]),
        '18-24': len([i for i in idades_validas if 18 <= i <= 24]),
        '25-34': len([i for i in idades_validas if 25 <= i <= 34]),
        '35+': len([i for i in idades_validas if i >= 35]),
    }

    return {
        "total_alunos": total_alunos,
        "media_idades": f"{media_idades:.1f}",
        "media_horas": f"{media_horas:.1f}",
        "total_cursos": len(cursos_unicos),
        "alunos_por_curso": alunos_por_curso,
        "faixas_idade": faixas_idade,
    }

def calcular_media_horas_estudo_por_curso(curso_alvo):
    """Calcula a média de horas de estudo de todos os alunos de um curso específico."""
    alunos = carregar_alunos()
    alunos_no_curso = [a for a in alunos if curso_alvo in a.get('curso', []) and a.get('horas_estudo') is not None]
    
    if not alunos_no_curso:
        return 0.0

    total_horas = sum(a['horas_estudo'] for a in alunos_no_curso)
    return total_horas / len(alunos_no_curso)

def calcular_media_notas_por_prova():
    """Calcula a média de notas por prova para todos os alunos."""
    resultados = carregar_resultados_provas()
    provas = carregar_provas()
    provas_info = {p['id']: p['titulo'] for p in provas}
    
    medias = defaultdict(lambda: {'total_pontos': 0, 'total_questoes': 0, 'total_alunos': 0})
    
    for r in resultados:
        prova_id = r['prova_id']
        medias[prova_id]['total_pontos'] += r['pontuacao']
        medias[prova_id]['total_questoes'] += r['total_questoes']
        medias[prova_id]['total_alunos'] += 1
        
    resultado_final = []
    for prova_id, dados in medias.items():
        if dados['total_questoes'] > 0:
            media_percentual = round((dados['total_pontos'] / dados['total_questoes']) * 100, 2)
            resultado_final.append({
                'id': prova_id,
                'titulo': provas_info.get(prova_id, 'Prova Desconhecida'),
                'media': media_percentual
            })
            
    return sorted(resultado_final, key=lambda x: x['media'])

def identificar_questoes_criticas(prova_id):
    """Identifica as questões com maior taxa de erro para uma prova específica."""
    resultados = carregar_resultados_provas()
    resultados_prova = [r for r in resultados if r['prova_id'] == prova_id]
    
    if not resultados_prova:
        return None
        
    questoes = {}
    
    for r in resultados_prova:
        for resposta in r['respostas_detalhadas']:
            pergunta = resposta['pergunta']
            if pergunta not in questoes:
                questoes[pergunta] = {'erros': 0, 'total': 0}
            
            questoes[pergunta]['total'] += 1
            if not resposta['correta']:
                questoes[pergunta]['erros'] += 1
                
    questoes_criticas = []
    for pergunta, dados in questoes.items():
        if dados['total'] > 0:
            taxa_erro = round((dados['erros'] / dados['total']) * 100, 2)
            questoes_criticas.append({
                'pergunta': pergunta,
                'taxa_erro': taxa_erro
            })
            
    return sorted(questoes_criticas, key=lambda x: x['taxa_erro'], reverse=True)

def identificar_alunos_com_baixo_desempenho(limite=5):
    """Identifica os alunos com as menores médias de notas."""
    alunos = carregar_alunos()
    resultados = carregar_resultados_provas()
    
    pontuacoes = defaultdict(lambda: {'total_pontos': 0, 'total_questoes': 0})
    
    for r in resultados:
        pontuacoes[r['usuario']]['total_pontos'] += r['pontuacao']
        pontuacoes[r['usuario']]['total_questoes'] += r['total_questoes']
        
    medias_alunos = []
    for aluno in alunos:
        nome_aluno = aluno['nome']
        dados_pontuacao = pontuacoes[nome_aluno]
        if dados_pontuacao['total_questoes'] > 0:
            media = round((dados_pontuacao['total_pontos'] / dados_pontuacao['total_questoes']) * 100, 2)
            medias_alunos.append({'nome': nome_aluno, 'media': media})
            
    return sorted(medias_alunos, key=lambda x: x['media'])[:limite]


# --- FUNÇÕES DE USUÁRIOS ---
def carregar_usuarios():
    if not os.path.exists('usuarios.json'): return []
    try:
        with open('usuarios.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_usuarios(usuarios):
    with open('usuarios.json', 'w', encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=4)

def gerar_senha_aleatoria(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def gerar_token_recuperacao(username, secret_key, expiration=3600):
    payload = {
        'user_id': username,
        'exp': datetime.utcnow() + timedelta(seconds=expiration)
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')

def verificar_token_recuperacao(token, secret_key):
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return 'expired'
    except jwt.InvalidTokenError:
        return None

# --- FUNÇÕES DE AULAS ---
def carregar_aulas():
    if not os.path.exists("aulas.json"): return []
    try:
        with open("aulas.json", "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return []
            return sorted(json.loads(content), key=lambda x: x.get('titulo', ''))
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_aulas(aulas):
    with open("aulas.json", "w", encoding="utf-8") as f:
        json.dump(aulas, f, ensure_ascii=False, indent=4)

# --- FUNÇÕES DE EXERCÍCIOS ---
def carregar_exercicios():
    if not os.path.exists("exercicios.json"):
        return []
    try:
        with open("exercicios.json", "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_exercicios(exercicios):
    with open("exercicios.json", "w", encoding="utf-8") as f:
        json.dump(exercicios, f, ensure_ascii=False, indent=4)

# --- FUNÇÕES DE PROVAS ---
def carregar_provas():
    if not os.path.exists("provas.json"):
        return []
    try:
        with open("provas.json", "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_provas(provas):
    with open("provas.json", "w", encoding="utf-8") as f:
        json.dump(provas, f, ensure_ascii=False, indent=4)
        
def gerar_id_prova(provas):
    while True:
        novo_id = 'P-' + ''.join(random.choices(string.digits, k=5))
        if not any(p.get('id') == novo_id for p in provas):
            return novo_id

# --- FUNÇÕES DE RESULTADOS DE PROVAS ---
def carregar_resultados_provas():
    if not os.path.exists("resultados_provas.json"):
        return []
    try:
        with open("resultados_provas.json", "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_resultados_provas(resultados):
    with open("resultados_provas.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=4)

def buscar_resultados_por_prova_id(prova_id):
    resultados = carregar_resultados_provas()
    return [r for r in resultados if r.get('prova_id') == prova_id]

def buscar_prova_por_id(prova_id):
    provas = carregar_provas()
    return next((p for p in provas if p.get('id') == prova_id), None)

# --- FUNÇÕES DE GAMIFICAÇÃO ---
def carregar_conquistas_definidas():
    if not os.path.exists("conquistas.json"): return []
    try:
        with open("conquistas.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def verificar_e_atribuir_conquistas(username):
    pessoas = carregar_dados()
    aluno = next((p for p in pessoas if p.get('nome') == username), None)
    if not aluno: return []

    resultados = [r for r in carregar_resultados_provas() if r.get('usuario') == username]
    todas_as_provas = carregar_provas()
    conquistas_definidas = carregar_conquistas_definidas()

    if 'conquistas' not in aluno:
        aluno['conquistas'] = []

    conquistas_desbloqueadas_nesta_verificacao = []
    ids_conquistas_aluno = {c['id'] for c in aluno['conquistas']}

    for conquista in conquistas_definidas:
        if conquista['id'] in ids_conquistas_aluno:
            continue

        conquista_ganha = False
        
        if conquista['id'] == 'PRIMEIRA_PROVA' and len(resultados) >= 1:
            conquista_ganha = True

        if conquista['id'] == 'DESTAQUE':
            for r in resultados:
                if r['total_questoes'] > 0 and (r['pontuacao'] / r['total_questoes']) * 100 > 90:
                    conquista_ganha = True
                    break
        
        if conquista['id'] == 'PERFECCIONISTA':
            for r in resultados:
                if r['total_questoes'] > 0 and r['pontuacao'] == r['total_questoes']:
                    conquista_ganha = True
                    break
        
        if conquista['id'] == 'MARATONISTA' and len(resultados) >= 3:
            conquista_ganha = True

        cursos_para_verificar = {
            'ESPECIALISTA_LOGICA': 'Lógica de Programação',
            'ESPECIALISTA_LINGUAGENS': 'Linguagens de Programação',
            'ESPECIALISTA_ESTRUTURAS': 'Algorítimos e Estruturas de dados'
        }
        if conquista['id'] in cursos_para_verificar:
            nome_curso = cursos_para_verificar[conquista['id']]
            ids_provas_curso = {p['id'] for p in todas_as_provas if p['curso'] == nome_curso}
            ids_provas_realizadas_pelo_aluno = {r['prova_id'] for r in resultados}
            
            if ids_provas_curso and ids_provas_curso.issubset(ids_provas_realizadas_pelo_aluno):
                conquista_ganha = True

        if conquista_ganha:
            nova_conquista = {
                "id": conquista['id'],
                "titulo": conquista['titulo'],
                "data": datetime.now().strftime("%d/%m/%Y")
            }
            aluno['conquistas'].append(nova_conquista)
            conquistas_desbloqueadas_nesta_verificacao.append(conquista)

    salvar_dados(pessoas)
    return conquistas_desbloqueadas_nesta_verificacao

def calcular_progresso_por_curso_e_topico(username):
    resultados = carregar_resultados_provas()
    resultados_aluno = [r for r in resultados if r.get('usuario') == username]
    
    progresso_por_curso = defaultdict(lambda: {'labels': [], 'data': []})

    for res in resultados_aluno:
        curso = res.get('curso', 'Sem Curso')
        titulo_prova = res.get('titulo_prova', 'Prova Sem Título')
        pontuacao = res.get('pontuacao', 0)
        total_questoes = res.get('total_questoes', 0)
        
        if total_questoes > 0:
            porcentagem = round((pontuacao / total_questoes) * 100, 2)
            progresso_por_curso[curso]['labels'].append(titulo_prova)
            progresso_por_curso[curso]['data'].append(porcentagem)

    return progresso_por_curso

def calcular_ranking_por_curso():
    alunos = carregar_alunos()
    resultados = carregar_resultados_provas()
    
    pontuacoes = defaultdict(lambda: {'total_pontos': 0, 'total_questoes': 0, 'cursos': []})
    
    for aluno in alunos:
        pontuacoes[aluno['nome']]['cursos'] = aluno.get('curso', [])

    for res in resultados:
        username = res.get('usuario')
        if username in pontuacoes:
            pontuacoes[username]['total_pontos'] += res.get('pontuacao', 0)
            pontuacoes[username]['total_questoes'] += res.get('total_questoes', 0)

    ranking_por_curso = {}

    for username, data in pontuacoes.items():
        if data['total_questoes'] > 0:
            media = round((data['total_pontos'] / data['total_questoes']) * 100, 2)
            aluno_info = {
                'nome': username,
                'media': media
            }
            for curso in data['cursos']:
                if curso not in ranking_por_curso:
                    ranking_por_curso[curso] = []
                ranking_por_curso[curso].append(aluno_info)

    for curso in ranking_por_curso:
        ranking_por_curso[curso] = sorted(ranking_por_curso[curso], key=lambda x: x['media'], reverse=True)

    return ranking_por_curso

# --- FUNÇÕES DO FÓRUM ---
def carregar_forum():
    if not os.path.exists("forum.json"): return []
    try:
        with open("forum.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_forum(posts):
    with open("forum.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

def buscar_post_por_id(post_id):
    posts = carregar_forum()
    return next((p for p in posts if p.get('id') == post_id), None)