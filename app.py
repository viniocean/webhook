from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import random
import string
import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# Config Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Config Flask
app = Flask(__name__)

# Config SMTP
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_NAME = os.getenv("FROM_NAME", "Marcaton")


@app.route("/teste-log")
def teste_log():
    print("Rota de teste acessada!")
    return "OK", 200

# Gera chave no estilo MENSAL-XXXX-XXXX-XXXX-XXXX
def gerar_chave_licenca(prefixo="", tamanho=16):
    caracteres = string.ascii_uppercase + string.digits
    chave_base = ''.join(random.choices(caracteres, k=tamanho))
    chave_formatada = '-'.join(chave_base[i:i+4] for i in range(0, tamanho, 4))
    return f"{prefixo.upper()}-{chave_formatada}"

# Envia e-mail estilizado com HTML + botões
def enviar_email(para, chave, plano, validade, nome):
    msg = EmailMessage()
    msg["Subject"] = "Sua chave de ativação do Marcaton"
    msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"] = para

    msg.set_content(f"""
Olá {nome},

Sua chave: {chave}
Plano: {plano}
Validade: {validade}
Use essa chave no aplicativo para ativar.

Equipe Marcaton.
""")

    html_template = """
    <!DOCTYPE html>
    <html lang="pt-BR">
      <body style="margin:0; padding:0; background-color:#121212; font-family:Arial, sans-serif; color:#ffffff;">
        <div style="max-width:600px; margin:auto; background-color:#1e1e1e; border-radius:12px; overflow:hidden;">
          <div style="padding:30px; background-color:#1e1e1e;">
            <h2 style="color:#00BFFF;">🔐 Sua chave de ativação</h2>
            <p>Olá, <strong>{{NOME}}</strong>! Obrigado por adquirir o <strong>Marcaton</strong>.</p>

            <p style="margin: 20px 0; font-size: 18px;">
              Aqui estão as informações da sua licença:
            </p>

            <div style="background-color:#000000; padding:20px; border-radius:10px; margin:20px 0;">
              <p style="font-size:16px; margin:0;"><strong>🔑 Chave:</strong></p>
              <p style="font-size:24px; font-weight:bold; color:#00BFFF; margin:8px 0;">{{CHAVE}}</p>

              <p style="font-size:16px; margin:0;"><strong>📦 Plano:</strong></p>
              <p style="font-size:18px; margin:8px 0;">{{PLANO}}</p>

              <p style="font-size:16px; margin:0;"><strong>📅 Validade:</strong></p>
              <p style="font-size:18px; margin:8px 0;">até {{VALIDADE}}</p>
            </div>

            <p style="margin: 20px 0;">Use essa chave no aplicativo para liberar o acesso.</p>

            <p style="margin: 20px 0;">Faça o download do aplicativo clicando no link abaixo:</p>
            <p style="margin: 10px 0;">
              <a href="https://github.com/viniocean/Marcaton/releases/download/Marcaton/Marcaton.exe" target="_blank"
                 style="color:#00BFFF; text-decoration:none; font-size:16px;">
                👉 Faça o download clicando aqui
              </a>
            </p>

            <p style="margin: 20px 0;">Qualquer dúvida entre em contato conosco:</p>

            <!-- Botões -->
            <div style="text-align:center; margin-top:30px;">
              <a href="https://t.me/supmarcaton" target="_blank"
                 style="background-color:#0088cc; color:white; text-decoration:none; padding:12px 24px; border-radius:8px; margin:5px; display:inline-block; font-size:16px;">
                💬 Falar no Telegram
              </a>
              <a href="https://wa.me/5521959028176" target="_blank"
                 style="background-color:#25D366; color:white; text-decoration:none; padding:12px 24px; border-radius:8px; margin:5px; display:inline-block; font-size:16px;">
                📲 Falar no WhatsApp
              </a>
            </div>

            <p style="margin-top:40px; font-size:14px; color:#888;">Equipe Marcaton</p>
          </div>
          <div style="background-color:#000000; padding:15px; text-align:center; font-size:12px; color:#555;">
            © 2025 Marcaton. Todos os direitos reservados.
          </div>
        </div>
      </body>
    </html>
    """

    html_final = html_template.replace("{{CHAVE}}", chave)\
                              .replace("{{PLANO}}", plano.upper())\
                              .replace("{{VALIDADE}}", validade)\
                              .replace("{{NOME}}", nome)

    msg.add_alternative(html_final, subtype='html')

    try:
        with smtplib.SMTP_SSL("smtp.hostinger.com", 465) as smtp:  # Altere para smtp.hostinger.com se for Hostinger
            smtp.set_debuglevel(1)
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print(f"Email enviado para {para}")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# Webhook principal
@app.route("/webhook-yampi", methods=["POST"])
def webhook_yampi():
    data = request.json
    try:
        email = data["resource"]["customer"]["data"]["email"]
        nome = data["resource"]["customer"]["data"]["name"]
        nome_plano = data["resource"]["items"]["data"][0]["sku"]["data"]["title"].lower()

        if "mensal" in nome_plano:
            dias = 30
            prefixo = "MENSAL"
        elif "semestral" in nome_plano:
            dias = 180
            prefixo = "SEMESTRAL"
        elif "anual" in nome_plano:
            dias = 365
            prefixo = "ANUAL"
        else:
            return jsonify({"erro": "Plano desconhecido"}), 400

        validade = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d")
        chave = gerar_chave_licenca(prefixo=prefixo)

        db.collection("licenses").document(chave).set({
            "email": email,
            "validade": validade,
            "plano": nome_plano,
            "used": False,
            "used_at": None
        })

        enviar_email(email, chave, nome_plano, validade, nome)

        return jsonify({"status": "sucesso", "key": chave}), 200

    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route("/webhook-kiwify", methods=["POST"])
def webhook_kiwify():
    data = request.json
    try:
        if data.get("event") != "order.approved":
            return jsonify({"status": "evento ignorado"}), 200

        order = data["payload"]["order"]
        email = order["customer"]["email"]
        nome = order["customer"]["name"]
        nome_plano = order["product"]["name"].lower()

        if "mensal" in nome_plano:
            dias = 30
            prefixo = "MENSAL"
        elif "semestral" in nome_plano:
            dias = 180
            prefixo = "SEMESTRAL"
        elif "anual" in nome_plano:
            dias = 365
            prefixo = "ANUAL"
        else:
            return jsonify({"erro": "Plano desconhecido"}), 400

        validade = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d")
        chave = gerar_chave_licenca(prefixo=prefixo)

        db.collection("licenses").document(chave).set({
            "email": email,
            "validade": validade,
            "plano": nome_plano,
            "used": False,
            "used_at": None
        })

        enviar_email(email, chave, nome_plano, validade, nome)

        return jsonify({"status": "sucesso", "key": chave}), 200

    except Exception as e:
        print(f"Erro no webhook Kiwify: {e}")
        return jsonify({"erro": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return "Webhook do Marcaton está online!"

if __name__ == "__main__":
    app.run(debug=True)
