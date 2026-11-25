"""Cérebro do Jarvis: modelo e esforço do orquestrador, nível dos agentes, conselho de IAs e escalada para o Fable.

Configurações compartilhadas entre o painel e o Telegram (CONFIG_DIR/cerebro.json):
- modelo:   modelo do Jarvis (orquestrador): opus (padrão), sonnet, haiku, fable ou um ID do gateway
- esforco:  auto (padrão: alto para planejar/começar uma demanda, médio para continuar e validar),
            low, medium, high, xhigh, max
- agentes:  economico · equilibrado (padrão) · caprichado: quanto modelo/esforço o Jarvis dá a cada agente
- conselho: desligado · decisoes (padrão: outras IAs opinam nas decisões e nos problemas difíceis) · sempre
- escalar:  sugerir (padrão: na 3ª tentativa sem resolver, sugere o Fable) · automatico · nunca
"""
import json
import os
import re
import threading

import jarvis_core as core

ARQ = os.path.join(core.CONFIG_DIR, "cerebro.json")
ARQ_FALHAS = os.path.join(core.CONFIG_DIR, "cerebro-falhas.json")
PADRAO = {"modelo": "opus", "esforco": "auto", "agentes": "equilibrado", "conselho": "decisoes", "escalar": "sugerir"}
OPCOES = {"esforco": ("auto", "low", "medium", "high", "xhigh", "max"),
          "agentes": ("economico", "equilibrado", "caprichado"),
          "conselho": ("desligado", "decisoes", "sempre"),
          "escalar": ("sugerir", "automatico", "nunca")}
NOMES_ESFORCO = {"auto": "automático", "low": "baixo", "medium": "médio", "high": "alto", "xhigh": "extra-alto",
                 "max": "máximo"}
APELIDOS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5",
            "fable": "claude-fable-5-2"}
TENTATIVAS_FABLE = 3
_trava = threading.Lock()

# o usuário dizendo que ainda não resolveu / que resolveu
FALHOU = re.compile(r"\b(n[aã]o (funcionou|deu certo|resolveu|abriu|carrega|mudou|aparece)|continua (com|o mesmo|dando|igual|sem)|"
                    r"ainda (n[aã]o|est[aá]|d[aá]|aparece|continua)|de novo|mesmo erro|mesmo problema|piorou|voltou a dar|"
                    r"deu erro|t[aá] dando erro|erro de novo|nada mudou)\b", re.I)
RESOLVEU = re.compile(r"\b(funcionou|deu certo|resolveu|resolvido|perfeito|ficou (bom|[oó]timo|excelente|perfeito)|agora foi|"
                      r"show|top|obrigad[oa])\b", re.I)


def ler():
    try:
        c = json.load(open(ARQ, encoding="utf-8"))
    except (OSError, ValueError):
        c = {}
    return {**PADRAO, **{k: v for k, v in c.items() if k in PADRAO or k == "fable_proxima"}}


def salvar(novo):
    with _trava:
        c = ler()
        if novo.get("modelo"):
            m = str(novo["modelo"]).strip()
            if m == "padrao":
                m = "opus"
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@-]{1,100}", m):
                raise ValueError("modelo inválido")
            c["modelo"] = m
        for k, ops in OPCOES.items():
            if novo.get(k) is not None:
                if novo[k] not in ops:
                    raise ValueError(f"{k} inválido")
                c[k] = novo[k]
        os.makedirs(os.path.dirname(ARQ), exist_ok=True)
        json.dump(c, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return c


def id_modelo(m):
    return APELIDOS.get(m, m)


# ------------------------------------------------------------------ escalada
def _falhas():
    try:
        return json.load(open(ARQ_FALHAS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def registrar(projeto, texto):
    """Conta as tentativas sem resolver do projeto a partir do que o usuário escreveu. Devolve o total atual."""
    if not projeto or not texto or texto.startswith("/"):
        return falhas(projeto)
    with _trava:
        f = _falhas()
        n = int(f.get(projeto, 0))
        if RESOLVEU.search(texto) and not FALHOU.search(texto):
            n = 0
        elif FALHOU.search(texto):
            n += 1
        f[projeto] = n
        json.dump(f, open(ARQ_FALHAS, "w", encoding="utf-8"))
        return n


def falhas(projeto):
    return int(_falhas().get(projeto or "", 0))


def zerar(projeto):
    with _trava:
        f = _falhas()
        f.pop(projeto, None)
        json.dump(f, open(ARQ_FALHAS, "w", encoding="utf-8"))


def marcar_fable(projeto):
    """Próxima mensagem deste projeto roda com o Fable (uma vez)."""
    with _trava:
        c = ler()
        c["fable_proxima"] = projeto
        json.dump(c, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _usar_fable(projeto):
    with _trava:
        c = ler()
        if c.get("fable_proxima") and c["fable_proxima"] == projeto:
            c.pop("fable_proxima")
            json.dump(c, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return True
    return False


# ------------------------------------------------------------------ decisão de cada execução
PLANEJAR = re.compile(r"^/(jarvis:)?(planejar|novo|entregar|pagina|adotar|evoluir|redesenhar|decidir)\b|"
                      r"\b(planej|arquitet|cri[ae] (o|um) (projeto|sistema|app|site)|do zero|nova demanda|"
                      r"refator|redesenh|migra[çc][aã]o|integra[çc][aã]o)", re.I)


def esforco_para(c, texto, tem_sessao, n_falhas):
    if c["esforco"] != "auto":
        return c["esforco"]
    if n_falhas >= 2:
        return "high"  # o mesmo problema voltou: pensa mais
    if PLANEJAR.search(texto or "") or len(texto or "") > 600 or (not tem_sessao and len(texto or "") >= 40):
        return "high"  # começo de demanda ou planejamento
    return "medium"  # continuar, ajustar e revalidar o que já foi planejado


def para_execucao(projeto, texto, tem_sessao, modelo_legado=None):
    """Decide modelo, esforço e regras extras desta execução. Devolve dict:
    modelo (ID), esforco, sistema (texto para o prompt), aviso (mensagem ao usuário ou "")."""
    c = ler()
    n = falhas(projeto)
    fable = _usar_fable(projeto)
    aviso = ""
    if not fable and n >= TENTATIVAS_FABLE and c["escalar"] == "automatico":
        fable, aviso = True, f"🧠 {n}ª tentativa no mesmo problema: desta vez o Jarvis usa o Fable."
    elif n >= TENTATIVAS_FABLE and c["escalar"] == "sugerir" and not fable:
        aviso = (f"💡 Já são {n} tentativas sem resolver. Quer que eu use o Fable (o modelo mais forte) nisto? "
                 "Mande /fable (vale só para a próxima mensagem).")
    modelo = id_modelo("fable") if fable else id_modelo(c["modelo"] if c.get("modelo") else (modelo_legado or "opus"))
    esforco = "high" if fable else esforco_para(c, texto, tem_sessao, n)
    return {"modelo": modelo, "esforco": esforco, "sistema": regras(c, n, fable), "aviso": aviso, "fable": fable}


NIVEIS = {
    "economico": """NÍVEL DOS AGENTES: econômico. Use o menor modelo que resolve:
- haiku + effort low: explorador, documentador, deploy, testador (rodar testes e ler resultados), designer em ajustes simples.
- sonnet + effort medium: desenvolvedor, designer (telas novas), android, dba, revisor.
- opus + effort high: só arquiteto e problemas que já falharam uma vez.""",
    "equilibrado": """NÍVEL DOS AGENTES: equilibrado. Escolha o modelo pelo tamanho e pelo risco da tarefa:
- haiku + effort low: explorador (achar arquivos, ler docs), documentador, deploy (checklist), testador (rodar testes).
- sonnet + effort low/medium: designer (layout, CSS, páginas), desenvolvedor em tarefas comuns, android em telas.
- sonnet + effort high: dba, revisor, desenvolvedor em lógica de negócio, integrações e APIs.
- opus + effort high: arquiteto, pagamentos, segurança, migração de dados, concorrência e bugs que já falharam.""",
    "caprichado": """NÍVEL DOS AGENTES: caprichado. Qualidade acima do custo:
- sonnet + effort medium: explorador, documentador, deploy, testador.
- sonnet + effort high: designer, desenvolvedor, android.
- opus + effort high: dba, revisor, arquiteto e tudo que envolve dados, dinheiro ou segurança.""",
}

CONSELHO = {
    "desligado": "",
    "decisoes": """CONSELHO DE IAS (decisões): antes de fechar uma decisão de arquitetura, fluxo, modelo de dados ou a causa
de um problema difícil, consulte as outras IAs ligadas: `jarvis-ajudante --conselho "pergunta objetiva + contexto
público"` (Gemini, Groq, Ollama, Grok e as demais respondem em paralelo; dados sensíveis são apagados). Compare as
respostas com a sua, faça o nivelamento (o que cada uma acertou, riscos, custo), escolha a melhor abordagem e
registre em docs/DECISOES.md quem propôs o quê. Não mande código privado inteiro: só o trecho e o contexto necessários.""",
    "sempre": """CONSELHO DE IAS (sempre): em CADA etapa (planejamento, fluxo, implementação de uma parte, revisão e
testes), peça segunda opinião às outras IAs ligadas: `jarvis-ajudante --conselho "pergunta + contexto público"` e,
para revisar um arquivo, `jarvis-ajudante --conselho --arquivo caminho "revise: bugs, segurança, legibilidade"`.
Compare as respostas, faça o nivelamento, aplique o que for melhor e registre em docs/DECISOES.md. Nunca envie
segredos, .env, chaves ou dados de clientes (a ferramenta recusa e apaga o que reconhecer).""",
}


def regras(c, n_falhas, fable):
    partes = [f"""MODELO E ESFORÇO POR DEMANDA: você é o orquestrador e decide quem trabalha e com quanto "cérebro".
No início de cada demanda, planeje e escreva no plano qual agente faz cada parte, com qual modelo e esforço, e
passe isso em cada chamada da ferramenta Agent/Task (campos `model`: haiku|sonnet|opus e `effort`: low|medium|high).
Tarefa simples não precisa de modelo grande: economize. Depois do plano, nas rodadas seguintes, apenas execute e
revalide. NUNCA use `model: fable` por conta própria: o Fable só entra quando o usuário pede (/fable).""",
             NIVEIS.get(c["agentes"], NIVEIS["equilibrado"])]
    if CONSELHO.get(c["conselho"]):
        partes.append(CONSELHO[c["conselho"]])
    if fable:
        partes.append("ESCALADA: o usuário pediu o Fable para este problema. Releia o histórico das tentativas que "
                      "falharam, levante as hipóteses ainda não testadas, consulte o conselho de IAs e resolva a causa.")
    elif n_falhas >= 2:
        partes.append(f"ATENÇÃO: o usuário já relatou {n_falhas} vezes que o problema continua. Não repita a mesma "
                      "abordagem: investigue a causa com o arquiteto (opus, effort high), teste a hipótese antes de "
                      "dizer que resolveu e mostre a prova (teste, print, log). Se ainda não resolver, diga com clareza "
                      "e sugira o Fable (/fable).")
    return "\n\n".join(partes)


def texto_status(projeto=None):
    c = ler()
    n = falhas(projeto)
    return (f"🧠 Cérebro do Jarvis\n• Modelo do Jarvis: {c['modelo']}\n• Esforço: {NOMES_ESFORCO[c['esforco']]}"
            + (" (alto para planejar/começar, médio para continuar e validar)" if c["esforco"] == "auto" else "")
            + f"\n• Agentes: {c['agentes']}\n• Conselho de IAs: {c['conselho']}\n• Escalar para o Fable: {c['escalar']}"
            + (f"\n• Tentativas sem resolver neste projeto: {n}" if n else "")
            + "\n\nMudar: /esforco alto · /equipe economico · /conselho sempre · /escalar automatico · /modelo sonnet"
            + "\nFable só na próxima mensagem: /fable (ou /fable <pedido>)")
