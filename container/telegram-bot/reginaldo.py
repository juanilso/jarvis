"""Reginaldo: o assistente pessoal do dono (agente próprio, com sessão e memória dele).

Fala com você pelo WhatsApp 2 (quando o número 2 está no modo "assistente pessoal"), com voz masculina, e recebe as
demandas pessoais que você passa ao Jarvis (o Jarvis fica um nível acima: organiza a estrutura e repassa).
Usa o `jarvis-pessoal` (lista, agenda, e-mail, roteiros), que passa pelo cofre: ele nunca vê senha.
"""
import json
import os
import threading
import time

import pessoal

NOME = "Reginaldo"
DIR = os.path.join(pessoal.DIR, "reginaldo")
VOZ_GRATUITA = os.environ.get("REGINALDO_VOZ_GRATUITA", "pt-BR-AntonioNeural")  # masculina (reserva sem ElevenLabs)
_trava = threading.Lock()
_ocupado = {"ate": 0}

PROMPT = """Você é o Reginaldo, assistente pessoal do dono (Juanilson). Homem, educado, direto e eficiente, como um
secretário de confiança. Fale em português do Brasil, em primeira pessoa no masculino ("anotei", "estou de olho").
O Jarvis é o gerente: ele cuida dos projetos de código e da estrutura; você cuida da vida pessoal e da rotina de
trabalho do dono (e-mail, agenda, lista de compras, roteiros do trabalho).

Quem fala com você:
- Mensagem sem [De: …] = o dono, no privado.
- [De: Nome (pessoa autorizada pelo dono)] ou [De: Nome (no grupo da família)] = outra pessoa da família (ex.: a esposa)
  ou o grupo da família. Chame a pessoa pelo nome. Para elas: lista de compras, agenda (ver e marcar compromissos),
  lembretes e perguntas do dia a dia. E-mail do dono, roteiros do trabalho e o cofre são só para o dono: se outra
  pessoa pedir, diga com educação que isso precisa ser pedido por ele.
- No grupo, responda curto: várias pessoas leem.

Como responder:
- Mensagem começando com [POR VOZ]: o dono falou por áudio e sua resposta vira áudio. Escreva como fala: frases curtas,
  sem listas longas, sem links, sem markdown. Se houver detalhes (lista grande, dados), coloque-os depois de uma linha
  só com --- (essa parte vai por escrito, não é falada).
- Mensagem começando com [PEDIDO DO JARVIS]: o Jarvis repassou um pedido do dono. Faça e responda ao dono direto.
- Seja curto. Uma confirmação simples é uma linha ("Anotei leite e pão. Faltam 5 itens.").
- Datas: hoje é {hoje}. Converta "terça às 15h" para data/hora ISO no fuso de São Paulo e confira o dia da semana.
  Se ficar ambíguo (qual terça? manhã ou tarde?), pergunte antes de marcar.
- Se faltar algo para fazer o pedido (um acesso no cofre, a agenda não conectada, um roteiro que não existe), diga
  exatamente o que falta e onde o dono configura. Não invente.
- O que você precisar guardar sobre o dono (preferências, pessoas, rotinas), anote em notas.md nesta pasta e consulte.

{regra}
"""


def ocupado():
    return _ocupado["ate"] > time.time()


def _anotar(papel, texto, origem):
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, "conversa.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "p": papel, "x": texto[:4000], "o": origem}, ensure_ascii=False) + "\n")


def conversar(texto, origem="whatsapp", voz=False):
    """Manda a mensagem ao Reginaldo e devolve a resposta (bloqueante)."""
    import jarvis_core as core
    with _trava:
        if ocupado():
            raise RuntimeError("o Reginaldo ainda está terminando a mensagem anterior")
        _ocupado["ate"] = time.time() + 900
    os.makedirs(DIR, exist_ok=True)
    _anotar("dono", texto, origem)
    pessoal._marcar("Reginaldo: " + texto[:60])
    resposta, erros = [], []

    def ev(e):
        if e.get("tipo") == "resposta" and e.get("texto"):
            resposta.append(e["texto"])
        elif e.get("tipo") == "erro":
            erros.append(e.get("texto", "erro"))
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    hoje = time.strftime("%Y-%m-%d") + f" ({dias[time.localtime().tm_wday]}), {time.strftime('%H:%M')}"
    try:
        core.Execucao().rodar(core.Estado("reginaldo"), ("[POR VOZ] " if voz else "") + texto, False, ev, cwd=DIR,
                              projeto="reginaldo", sistema=PROMPT.format(hoje=hoje, regra=pessoal.REGRA_AGENTE),
                              orquestrador=False)
    finally:
        _ocupado["ate"] = 0
        pessoal._marcar("")
    final = "\n\n".join(resposta).strip() or ("⚠ " + "; ".join(erros) if erros else "(sem resposta)")
    _anotar("reginaldo", final, origem)
    return final


def gerar_ogg(texto):
    """Voz do Reginaldo: a voz masculina escolhida na ElevenLabs (painel) ou a gratuita masculina."""
    import elevenlabs
    c = elevenlabs.config()
    return elevenlabs.gerar_ogg(texto, voz=c.get("voz_reginaldo") or "-", gratuita=VOZ_GRATUITA)


def linha_pessoal():
    """Qual número do WhatsApp está no modo assistente pessoal (ou None)."""
    import linhas
    for n in (2, 1):
        try:
            c = linhas.modulos(n)[2].carregar() if (n == 1 or linhas.ativa(2)) else {}
            if c and (c.get("modo") == "pessoal" or c["dono"].get("agente") == "reginaldo") and c["dono"].get("numero"):
                return n
        except Exception:  # noqa: BLE001
            continue
    return None


def pedido_do_jarvis(texto):
    """O Jarvis repassa uma demanda pessoal: o Reginaldo faz e responde ao dono pelo WhatsApp (e no painel)."""
    def rodar():
        try:
            final = conversar("[PEDIDO DO JARVIS] " + texto, origem="jarvis")
        except Exception as e:  # noqa: BLE001
            final = f"⚠ {type(e).__name__}: {str(e)[:200]}"
        mostrado = final.replace("\n---", "\n\n📋", 1)
        try:
            import sys
            pub = getattr(sys.modules.get("__main__"), "publicar", None)  # só existe no processo do painel
            if pub:
                pub({"tipo": "info", "texto": f"👤 {NOME}: {mostrado}"})
        except Exception:  # noqa: BLE001
            pass
        n = linha_pessoal()
        if n:
            import linhas
            linhas.modulos(n)[0].mandar_ao_dono(mostrado, de=f"🧑‍💼 *{NOME}*")
    if ocupado():
        return f"⏳ O {NOME} está terminando outra coisa; repito o pedido em seguida se você mandar de novo."
    threading.Thread(target=rodar, daemon=True).start()
    n = linha_pessoal()
    return f"👤 Passei para o {NOME}." + (f" Ele te responde no WhatsApp {n} e aqui no painel." if n else " Ele responde aqui no painel.")
