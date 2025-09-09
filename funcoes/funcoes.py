import json
import os
import random
import string
from datetime import datetime, timedelta
import jwt

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

def salvar_dados(pessoas):
    with open("pessoas.json", "w", encoding="utf-8") as f:
        json.dump(pessoas, f, ensure_ascii=False, indent=4)

def gerar_relatorio_dados():
    pessoas = carregar_dados()
    if not pessoas: return {"total_alunos": 0, "media_idades": "0.0", "media_horas": "0.0", "total_cursos": 0, "alunos_por_curso": {}, "faixas_idade": {}}

    total_alunos = len(pessoas)
    idades_validas = [p.get('idade') for p in pessoas if p.get('idade') is not None]
    soma_idades = sum(idades_validas)
    soma_horas = sum(p.get('horas_estudo', 0) for p in pessoas)

    media_idades = soma_idades / len(idades_validas) if idades_validas else 0
    media_horas = soma_horas / total_alunos if total_alunos > 0 else 0

    todos_cursos = []
    for p in pessoas:
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

# --- FUNÇÕES DE USUÁRIOS ---
def carregar_usuarios():
    if not os.path.exists('usuarios.json'): return []
    try:
        with open('usuarios.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_usuarios(usuarios):
    with open('usuarios.json', 'w', encoding='utf-8') as f:
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
        return 'expired'  # Token expirou
    except jwt.InvalidTokenError:
        return None      # Token inválido

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
    """Carrega os dados dos exercícios do arquivo exercicios.json."""
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
    """Salva os dados dos exercícios no arquivo exercicios.json."""
    with open("exercicios.json", "w", encoding="utf-8") as f:
        json.dump(exercicios, f, ensure_ascii=False, indent=4)

# --- FUNÇÕES DE PROVAS ---

def carregar_provas():
    """Carrega os dados das provas do arquivo provas.json."""
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
    """Salva os dados das provas no arquivo provas.json."""
    with open("provas.json", "w", encoding="utf-8") as f:
        json.dump(provas, f, ensure_ascii=False, indent=4)
        
def gerar_id_prova(provas):
    """Gera um ID único para uma nova prova (formato: P-XXXXX)."""
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