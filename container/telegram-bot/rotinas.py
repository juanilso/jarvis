"""Gatilho seguro para rotinas automáticas (n8n ou qualquer agendador) e registro das execuções.

POST /api/gatilho  (cabeçalho: Authorization: Bearer <JARVIS_GATILHO_TOKEN>)
{
  "rotina":  "Pesquisa semanal",          nome que aparece no escritório e nos avisos
  "acao":    "hermes" | "jarvis" | "pesquisar" | "tendencias" | "ideia" | "avisar" | "status",
  "texto":   "o pedido",
  "projeto": "pasta do projeto" (opcional; padrão: o projeto atual do painel),
  "avisar":  true                          manda o resultado no Telegram
  "esperar": false                         true = devolve o resultado na resposta HTTP (até 15 min)
}

Regras: o Jarvis em rotina só analisa/testa/relata (edição e comandos perigosos bloqueados);
o Hermes continua só-leitura; nada de deploy, push ou banco de produção.
"""
import hmac
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

import jarvis_core as core

TOKEN = os.environ.get("JARVIS_GATILHO_TOKEN", "").strip()
ARQ = os.path.join(core.CONFIG_DIR, "rotinas.jsonl")
ACOES = {"hermes", "jarvis", "pesquisar", "tendencias", "ideia", "avisar", "status"}
_lock = threading.Lock()


def autorizado(cabecalho):
    if not TOKEN:
        return False
    enviado = (cabecalho or "").removeprefix("Bearer ").strip()
    return hmac.compare_digest(enviado, TOKEN)


def registrar(item):
    item = dict(item, quando=item.get("quando") or time.strftime("%Y-%m-%d %H:%M:%S"))
    with _lock:
        try:
            os.makedirs(os.path.dirname(ARQ), exist_ok=True)
            with open(ARQ, "a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except OSError as e:
            print("erro ao registrar rotina:", e, flush=True)


def listar(limite=30):
    try:
        linhas = open(ARQ, encoding="utf-8").read().splitlines()[-limite * 3:]
    except OSError:
        return []
    saida, vistos = [], set()
    for l in reversed(linhas):  # cada execução tem início e fim: mostra só o registro mais recente
        try:
            item = json.loads(l)
        except json.JSONDecodeError:
            continue
        if item.get("id") in vistos:
            continue
        vistos.add(item.get("id"))
        saida.append(item)
    return saida[:limite]


def avisar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token or not chats:
        return False
    ok = False
    for chat in chats:
        for i in range(0, len(texto), 3900):
            dados = urllib.parse.urlencode({"chat_id": chat, "text": texto[i:i + 3900]}).encode()
            try:
                urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=dados, timeout=20)
                ok = True
            except Exception as e:  # noqa: BLE001
                print("erro ao avisar no Telegram:", e, flush=True)
    return ok


def _limpar_nome(nome):
    return re.sub(r"[^\w .:-]", "", str(nome or "rotina"))[:60] or "rotina"


def executar(dados, publicar, pool, estado):
    """Valida e executa um pedido do gatilho. Retorna (código_http, dict)."""
    if not isinstance(dados, dict):
        return 400, {"erro": "corpo deve ser JSON"}
    acao = str(dados.get("acao", "")).lower()
    if acao not in ACOES:
        return 400, {"erro": f"ação inválida; use uma de: {', '.join(sorted(ACOES))}"}
    rotina = _limpar_nome(dados.get("rotina"))
    texto = str(dados.get("texto", ""))[:4000].strip()
    projeto = str(dados.get("projeto") or estado.ler()["projeto"] or "")
    if projeto and projeto not in core.listar_projetos():
        return 400, {"erro": f"projeto “{projeto}” não existe"}
    quer_aviso, esperar = bool(dados.get("avisar")), bool(dados.get("esperar"))
    if acao not in ("status",) and not texto:
        return 400, {"erro": "falta o texto do pedido"}
    base = {"id": f"{time.time():.3f}", "rotina": rotina, "acao": acao, "projeto": projeto, "pedido": texto[:200],
            "quando": time.strftime("%Y-%m-%d %H:%M:%S")}

    def concluir(ok, resultado):
        registrar(dict(base, ok=ok, resultado=resultado[:1500], fim=time.strftime("%Y-%m-%d %H:%M:%S")))
        publicar({"tipo": "info" if ok else "erro", "texto": f"🔁 Rotina “{rotina}” ({acao}):\n\n{resultado}"}, projeto or None)
        if quer_aviso:
            avisar_telegram(f"🔁 {rotina}\n\n{resultado}")

    if acao == "status":
        ativos = pool.resumo()
        return 200, {"ok": True, "rodando": ativos, "rotinas": listar(5)}
    if acao == "avisar":
        ok = avisar_telegram(f"🔁 {rotina}\n\n{texto}")
        registrar(dict(base, ok=ok, resultado="aviso enviado" if ok else "Telegram não configurado"))
        return (200 if ok else 503), {"ok": ok}
    if acao == "ideia":
        import kb
        caminho = kb.salvar("ideias", texto.split("\n")[0][:70], texto, tags=["rotina", rotina], projeto=projeto)
        concluir(True, f"Nota salva: {caminho}")
        return 200, {"ok": True, "caminho": caminho}

    publicar({"tipo": "sistema", "texto": f"🔁 Rotina “{rotina}” começou ({acao})"}, projeto or None)
    registrar(dict(base, ok=None, resultado="iniciada"))
    pronto, saida = threading.Event(), {}

    def tarefa():
        try:
            if acao == "hermes":
                import hermes_cliente as hermes
                try:
                    r = hermes.perguntar(texto, projeto or None)
                    saida.update(ok=True, resultado=r)
                except hermes.ErroHermes as e:
                    saida.update(ok=False, resultado=f"Hermes: {e}")
            elif acao in ("pesquisar", "tendencias"):
                import kb
                destino, prompt = (kb.prompt_tendencias if acao == "tendencias" else kb.prompt_pesquisa)(texto)
                final = {}
                pool.de("_pesquisa").rodar(estado, prompt, False, lambda ev: final.update(ev) if ev["tipo"] == "resposta" else None,
                                           cwd=kb.KB_DIR, usar_sessao=False, projeto=projeto or None)
                kb.sincronizar()
                saida.update(ok=not final.get("erro"), resultado=(final.get("texto") or "pesquisa concluída")
                             + (f"\n\nSalva em: {os.path.relpath(destino, kb.KB_DIR)}" if os.path.exists(destino) else ""))
            elif acao == "jarvis":
                final = {}

                def ao_evento(ev):
                    if ev["tipo"] == "resposta":
                        final.update(ev)
                    elif ev["tipo"] not in ("inicio",):
                        publicar(ev, projeto)
                pool.de(projeto).rodar(estado, texto, False, ao_evento, usar_sessao=False, projeto=projeto,
                                       sistema=core.REGRAS_ROTINA, extra=core.BLOQUEIOS_ROTINA)
                saida.update(ok=bool(final) and not final.get("erro"), resultado=final.get("texto") or "sem resposta")
        except Exception as e:  # noqa: BLE001
            saida.update(ok=False, resultado=f"falhou: {type(e).__name__}: {e}")
        finally:
            concluir(saida.get("ok", False), saida.get("resultado", ""))
            pronto.set()

    if acao == "jarvis":
        if not projeto:
            return 400, {"erro": "informe o projeto"}
        ok, motivo = pool.pode_iniciar(projeto)
        if not ok:
            registrar(dict(base, ok=False, resultado=motivo))
            return 409, {"erro": motivo}
    if acao in ("pesquisar", "tendencias"):
        ok, motivo = pool.pode_iniciar("_pesquisa")
        if not ok:
            return 409, {"erro": motivo}
    threading.Thread(target=tarefa, daemon=True).start()
    if esperar:
        pronto.wait(timeout=900)
        return 200, {"ok": saida.get("ok", False), "resultado": saida.get("resultado", "ainda rodando")}
    return 202, {"ok": True, "status": "iniciada", "rotina": rotina}
