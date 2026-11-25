"""Treinador do atendimento: lê as conversas da semana (diário do atendimento), aponta onde o robô se perdeu e
propõe uma base de respostas revisada. Nada muda sozinho: você aprova (aplicar) ou descarta, no painel ou no Telegram.

Arquivos (por número de WhatsApp): <pasta do atendimento>/treinador/
  estado.json · relatorio.md · proposta.md · base-anterior-<data>.md (cópia antes de aplicar)
"""
import json
import os
import re
import threading
import time

_rodando = {}
TELEFONE = re.compile(r"\b\d{10,13}\b")

PEDIDO = """Você é um treinador de atendimento ao cliente por WhatsApp. Abaixo estão a BASE DE RESPOSTAS que o robô de
pré-atendimento segue e CONVERSAS reais da última semana (👤 cliente, 🤖 robô, 🙋 dono; [MÍDIA] = imagem/áudio).

Analise as conversas e encontre onde o robô:
- não entendeu o que o cliente disse, respondeu outra coisa ou ignorou uma pergunta;
- repetiu pergunta já respondida, ofereceu menu quando o cliente já tinha dito o que queria, soou robótico/repetitivo;
- desobedeceu a BASE (informou preço, prometeu algo, não chamou o dono quando devia, chamou sem precisar);
- não sabia responder porque falta informação na BASE (anote o que o dono precisa acrescentar).
Também veja o que o DONO respondeu depois do robô: é o jeito certo, e pode virar regra.

Responda EXATAMENTE neste formato, em português do Brasil:
<relatorio>
Resumo em 2 linhas (quantas conversas, como o robô foi).
Depois, até 12 itens, do mais importante ao menos:
N. Problema — exemplo curto da conversa (sem números de telefone) — ajuste proposto
No fim: "Perguntas para o dono:" com o que falta na base (se houver).
</relatorio>
<base>
A BASE COMPLETA revisada, pronta para colar: mantenha tudo o que o dono definiu (regras, informações, tom),
mude só o necessário para corrigir os problemas, e marque cada trecho novo ou alterado com (novo) no fim da linha.
Nunca coloque preços ou informações que não estão na base atual nem nas respostas do dono.
</base>"""


def _pasta(at):
    p = os.path.join(at.DIR, "treinador")
    os.makedirs(p, exist_ok=True)
    return p


def estado(at):
    try:
        e = json.load(open(os.path.join(_pasta(at), "estado.json"), encoding="utf-8"))
    except (OSError, ValueError):
        e = {}
    p = _pasta(at)
    for nome in ("relatorio", "proposta"):
        try:
            e[nome] = open(os.path.join(p, nome + ".md"), encoding="utf-8").read()
        except OSError:
            e[nome] = ""
    e["rodando"] = bool(_rodando.get(at.DIR))
    return e


def _salvar_estado(at, e):
    e = {k: v for k, v in e.items() if k not in ("relatorio", "proposta", "rodando")}
    json.dump(e, open(os.path.join(_pasta(at), "estado.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def conversas(at, dias=7, limite_chars=45000):
    """Junta o diário por cliente. Prioriza conversas em que o dono precisou entrar, com erro ou mais longas."""
    pasta = os.path.join(at.DIR, "diario")
    corte = time.time() - dias * 86400
    por = {}
    try:
        arquivos = sorted(n for n in os.listdir(pasta) if n.endswith(".jsonl"))
    except OSError:
        arquivos = []
    for n in arquivos:
        for linha in open(os.path.join(pasta, n), encoding="utf-8"):
            try:
                m = json.loads(linha)
            except ValueError:
                continue
            if m.get("t", 0) >= corte:
                por.setdefault(m["c"], []).append(m)
    def peso(msgs):
        return (sum(1 for m in msgs if m["p"] == "dono") * 5 + sum(1 for m in msgs if m.get("humano")) * 2
                + sum(1 for m in msgs if m.get("erro")) * 3 + len(msgs))
    ordem = sorted(por.values(), key=peso, reverse=True)
    blocos, total = [], 0
    for i, msgs in enumerate(ordem, 1):
        icone = {"cliente": "👤", "robo": "🤖", "dono": "🙋"}
        corpo = "\n".join(icone.get(m["p"], "?") + " " + TELEFONE.sub("[telefone]", m["x"])[:400] for m in msgs[-30:])
        bloco = f"--- Conversa {i} ({time.strftime('%d/%m', time.localtime(msgs[0]['t']))}) ---\n{corpo}"
        if total + len(bloco) > limite_chars:
            break
        blocos.append(bloco)
        total += len(bloco)
    return blocos, len(por)


def analisar(at, avisar=True):
    """Roda a análise (demora 1 a 3 minutos). Devolve o estado."""
    if _rodando.get(at.DIR):
        return {"erro": "o treinador já está analisando"}
    _rodando[at.DIR] = True
    try:
        blocos, total = conversas(at)
        rotulo = f"【{at.NOME}】 " if getattr(at, "NOME", "") else ""
        if len(blocos) < 2:
            e = estado(at)
            e.update(quando=time.strftime("%d/%m/%Y %H:%M"), conversas=total, pendente=False,
                     aviso="poucas conversas na semana para analisar")
            _salvar_estado(at, e)
            if avisar:
                at._avisar_dono(f"🎓 Treinador do atendimento: só {total} conversa(s) nesta semana, nada para analisar ainda.")
            return estado(at)
        base = re.sub(r"<!--.*?-->", "", at.ler_faq(), flags=re.S).strip()
        conteudo = f"BASE DE RESPOSTAS ATUAL:\n{base}\n\nCONVERSAS ({len(blocos)} de {total}):\n\n" + "\n\n".join(blocos)
        bruto = at._chamar_modelo(PEDIDO, [{"role": "user", "content": conteudo}], max_tokens=7000, temperatura=0.3,
                                  forte=True, tempo=300)
        rel = re.search(r"<relatorio>\s*(.*?)\s*(?:</relatorio>|$)", bruto, re.S)
        prop = re.search(r"<base>\s*(.*?)\s*(?:</base>|$)", bruto, re.S)
        relatorio = (rel.group(1) if rel else bruto).strip()
        proposta = at.sem_marca_ia(prop.group(1)).strip() if prop else ""
        if len(proposta) < max(200, len(base) * 0.5):  # base cortada ou ausente: não oferece aplicar
            proposta = ""
        p = _pasta(at)
        open(os.path.join(p, "relatorio.md"), "w", encoding="utf-8").write(relatorio)
        open(os.path.join(p, "proposta.md"), "w", encoding="utf-8").write(proposta)
        e = estado(at)
        e.update(quando=time.strftime("%d/%m/%Y %H:%M"), conversas=total, analisadas=len(blocos),
                 pendente=bool(proposta), aviso="" if proposta else "a base sugerida veio incompleta: veja só o relatório")
        _salvar_estado(at, e)
        if avisar:
            import rotinas
            cmd = f"/treinar {getattr(at, 'CMD_LINHA', '')}".rstrip()
            at._avisar_dono(f"🎓 Treinador do atendimento · {len(blocos)} conversa(s) analisadas\n\n{relatorio[:3300]}\n\n"
                            + (f"Base sugerida no arquivo abaixo. Aplicar: {cmd} aplicar · descartar: {cmd} descartar "
                               "(ou no painel 📱 → Treinador)." if proposta else "Sem base sugerida desta vez."))
            if proposta:
                rotinas.avisar_telegram_documento(os.path.join(p, "proposta.md"), f"{rotulo}📄 Base sugerida (marcas “(novo)”)")
        return estado(at)
    except Exception as x:  # noqa: BLE001
        if avisar:
            at._avisar_dono(f"🎓 O treinador não conseguiu analisar: {type(x).__name__}: {str(x)[:200]}")
        return {"erro": f"{type(x).__name__}: {str(x)[:200]}"}
    finally:
        _rodando.pop(at.DIR, None)


def analisar_fundo(at):
    threading.Thread(target=analisar, args=(at,), daemon=True).start()


def aplicar(at):
    e = estado(at)
    if not e.get("pendente") or not e.get("proposta"):
        return False, "não há base sugerida esperando aprovação"
    p = _pasta(at)
    copia = os.path.join(p, f"base-anterior-{time.strftime('%Y%m%d-%H%M')}.md")
    open(copia, "w", encoding="utf-8").write(at.ler_faq())
    nova = re.sub(r"\s*\(novo\)\s*$", "", e["proposta"], flags=re.M)  # tira as marcas
    at.salvar_faq(nova)
    e.update(pendente=False, aplicada=time.strftime("%d/%m/%Y %H:%M"), copia=copia)
    _salvar_estado(at, e)
    return True, f"✅ Base nova aplicada. A anterior ficou guardada em {os.path.basename(copia)}."


def descartar(at):
    e = estado(at)
    e["pendente"] = False
    _salvar_estado(at, e)
    return True, "🗑 Sugestão descartada. A base continua como estava."


def comando(at, arg):
    a = (arg or "").strip().lower()
    if a == "aplicar":
        return aplicar(at)[1]
    if a == "descartar":
        return descartar(at)[1]
    if a in ("ver", "status"):
        e = estado(at)
        if not e.get("quando"):
            return "🎓 O treinador ainda não rodou. Use /treinar para analisar agora."
        return (f"🎓 Última análise: {e['quando']} ({e.get('analisadas', 0)} conversas)"
                + (" · base sugerida esperando você" if e.get("pendente") else "") + f"\n\n{e.get('relatorio', '')[:3000]}")
    if _rodando.get(at.DIR):
        return "🎓 O treinador já está analisando; o resultado chega aqui."
    analisar_fundo(at)
    return "🎓 Analisando as conversas da semana (1 a 3 minutos). O relatório e a base sugerida chegam aqui."
