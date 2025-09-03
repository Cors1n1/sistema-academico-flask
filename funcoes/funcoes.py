import json
import os

def carregar_dados():
    if not os.path.exists("pessoas.json"):
        return []
    with open("pessoas.json", "r", encoding="utf-8") as f:
        try:
            return sorted(json.load(f), key=lambda x: x['nome'])
        except json.JSONDecodeError:
            return []
    return []

def salvar_dados(pessoas):
    with open("pessoas.json", "w", encoding="utf-8") as f:
        json.dump(pessoas, f, ensure_ascii=False, indent=4)

def gerar_relatorio_dados():
    pessoas = carregar_dados()
    if not pessoas:
        return None
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