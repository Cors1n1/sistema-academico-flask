# gerar_hash.py

from werkzeug.security import generate_password_hash

# --- Para o usuário admin ---
senha_admin = input("Digite a senha que você quer para o usuário 'admin': ")
hash_admin = generate_password_hash(senha_admin)

print("\n================ HASH DO ADMIN ================")
print(hash_admin)
print("=============================================\n")


# --- Para o usuário visitante ---
senha_visitante = input("Digite a senha que você quer para o usuário 'visitante': ")
hash_visitante = generate_password_hash(senha_visitante)

print("\n============== HASH DO VISITANTE ==============")
print(hash_visitante)
print("=============================================\n")