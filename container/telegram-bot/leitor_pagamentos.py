#!/usr/bin/env python3
"""Leitor de pagamentos: lê, na SUA conta do Telegram, só a conversa com o bot de pagamentos
(padrão: @DastDePixPartnerBot) e repassa cada "PAGAMENTO FASTFLOW RECEBIDO" ao Jarvis.

Por que uma conta e não o bot do Jarvis? O Telegram não deixa um bot ler a conversa privada entre você e
outro bot, nem mensagens de outros bots em grupos. Este leitor:
  - só ESCUTA a conversa com PAGAMENTOS_BOT (não lê outras conversas, não envia nada, não marca como lido);
  - ao ligar, recupera os pagamentos das últimas 24 h (o Jarvis ignora os já processados);
  - roda num contêiner separado; a sessão fica no volume "pagamentos-sessao".
Para desconectar a qualquer momento: Telegram → Configurações → Dispositivos → encerrar "Jarvis leitor".

Uso:
  primeira vez (login com código):  python3 leitor_pagamentos.py --login
  serviço:                          python3 leitor_pagamentos.py
"""
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request

from telethon import TelegramClient, events

API_ID = int(os.environ.get("TG_API_ID") or 0)
API_HASH = os.environ.get("TG_API_HASH", "")
BOT = os.environ.get("PAGAMENTOS_BOT", "DastDePixPartnerBot").lstrip("@")
SESSAO = os.environ.get("TG_SESSAO", "/sessao/leitor")
GATILHO = os.environ.get("JARVIS_GATILHO_URL", "http://jarvisweb:8090/api/gatilho")
TOKEN = os.environ.get("JARVIS_GATILHO_TOKEN", "")


def eh_pagamento(texto):
    t = (texto or "").upper()
    return "FASTFLOW" in t and "RECEBIDO" in t


def enviar_ao_jarvis(texto):
    req = urllib.request.Request(GATILHO, data=json.dumps({"acao": "pagamento", "texto": texto,
                                                           "fonte": "leitor-telegram"}).encode(),
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    for tentativa in range(5):  # o painel pode estar reiniciando
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return {"ok": False, "erro": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"}
        except Exception as e:  # noqa: BLE001
            print(f"jarvis indisponível ({type(e).__name__}); nova tentativa em {10 * (tentativa + 1)} s", flush=True)
            time.sleep(10 * (tentativa + 1))
    return {"ok": False, "erro": "Jarvis não respondeu"}


async def repassar(texto, origem):
    if not eh_pagamento(texto):
        return
    r = await asyncio.to_thread(enviar_ao_jarvis, texto)
    estado = "já processado" if r.get("repetido") else (r.get("resumo") or r.get("erro") or "?")
    print(f"[{origem}] pagamento #{r.get('id', '?')}: {estado}", flush=True)


async def principal(login):
    if not API_ID or not API_HASH:
        sys.exit("Falta TG_API_ID e TG_API_HASH (veja ./pagamentos-configurar.sh)")
    if not TOKEN and not login:
        sys.exit("Falta JARVIS_GATILHO_TOKEN (rode ./automacoes-configurar.sh e depois ./pagamentos-configurar.sh)")
    cli = TelegramClient(SESSAO, API_ID, API_HASH, device_model="Jarvis leitor", app_version="1.14",
                         system_version="pagamentos")
    if login:
        await cli.start()  # pede telefone, código e senha de 2 etapas (se tiver)
        eu = await cli.get_me()
        bot = await cli.get_entity(BOT)
        print(f"✅ Conectado como {eu.first_name} · vou ler só a conversa com @{getattr(bot, 'username', BOT)}")
        await cli.disconnect()
        return
    await cli.connect()
    if not await cli.is_user_authorized():
        sys.exit("Sessão não autorizada. Rode: ./pagamentos-configurar.sh")
    bot = await cli.get_entity(BOT)

    @cli.on(events.NewMessage(chats=bot))
    async def nova(ev):
        await repassar(ev.raw_text, "nova")

    @cli.on(events.MessageEdited(chats=bot))
    async def editada(ev):
        await repassar(ev.raw_text, "editada")

    limite = time.time() - 24 * 3600  # recupera o que chegou enquanto estava desligado
    antigas = [m async for m in cli.iter_messages(bot, limit=40) if m.date.timestamp() > limite]
    for m in reversed(antigas):
        await repassar(m.raw_text, "recuperada")
    print(f"👂 Lendo pagamentos de @{getattr(bot, 'username', BOT)} (só leitura)", flush=True)
    await cli.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(principal("--login" in sys.argv))
