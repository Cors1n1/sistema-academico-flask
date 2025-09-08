import json
import os
import random
import string

# --- FUNÇÕES DE ALUNOS ---
def carregar_dados():
    if not os.path.exists("pessoas.json"): return []
    try:
        with open("pessoas.json", "r", encoding="utf-8") as f:
            return sorted(json.load(f), key=lambda x: x.get('nome', ''))
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def salvar_dados(pessoas):
    with open("pessoas.json", "w", encoding="utf-8") as f:
        json.dump(pessoas, f, ensure_ascii=False, indent=4)

def gerar_relatorio_dados():
    pessoas = carregar_dados()
    if not pessoas: return {"total_alunos": 0, "media_idades": "0.0", "media_horas": "0.0"}
    total_alunos = len(pessoas)
    soma_idades = sum(p.get('idade', 0) for p in pessoas)
    soma_horas = sum(p.get('horas_estudo', 0) for p in pessoas)
    media_idades = soma_idades / total_alunos if total_alunos > 0 else 0
    media_horas = soma_horas / total_alunos if total_alunos > 0 else 0
    return {
        "total_alunos": total_alunos,
        "media_idades": f"{media_idades:.1f}",
        "media_horas": f"{media_horas:.1f}"
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

# --- FUNÇÕES DE AULAS ---\n\n
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

# --- NOVAS FUNÇÕES DE PROVAS ---\n
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