"""Reconhece a voz do dono no modo mãos livres: só a sua voz aciona o Jarvis.

Modelo aberto WeSpeaker ResNet34 (ONNX, ~26 MB, licença CC-BY-4.0), baixado do Hugging Face na primeira vez
e rodado localmente com o onnxruntime (que já vem com o faster-whisper). Nenhum áudio sai do servidor.
Cadastro: 3 frases suas viram uma "assinatura" (vetor de 256 números), salva em <config do Claude>/jarvis-voz-dono.json.
Cada fala captada é comparada com essa assinatura (semelhança de 0 a 1); abaixo do limite, é ignorada.
"""
import json
import os
import threading
import time
import urllib.request

import numpy as np

CONFIG_DIR = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))
ARQ = os.path.join(CONFIG_DIR, "jarvis-voz-dono.json")
DIR_AMOSTRAS = os.path.join(CONFIG_DIR, "voz-dono-amostras")
MODELO = os.path.join(CONFIG_DIR, "modelos", "voxceleb_resnet34_LM.onnx")
URL = os.environ.get("JARVIS_VOZ_MODELO_URL",
                     "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/main/voxceleb_resnet34_LM.onnx")
FRASES = [
    "Jarvis, abre o projeto da loja e me mostra o que falta para publicar.",
    "Ok Jarvis, cria uma tela de cadastro com nome, telefone e e-mail.",
    "Jarvis, pode dormir. Depois a gente continua a conversa.",
]
PADRAO = {"ligado": False, "limiar": 0.5, "janela": 3, "interromper": True}
_trava = threading.Lock()
_sessao = {"s": None}


def config():
    try:
        with open(ARQ, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    c = dict(PADRAO)
    c.update({k: d[k] for k in ("ligado", "limiar", "janela", "interromper", "assinatura", "cadastro", "sugerido") if k in d})
    return c


def publico():
    c = config()
    return {"ligado": bool(c["ligado"]), "limiar": c["limiar"], "janela": c["janela"], "interromper": c["interromper"],
            "cadastrada": bool(c.get("assinatura")), "cadastro": c.get("cadastro"), "sugerido": c.get("sugerido"),
            "frases": FRASES, "modelo_baixado": os.path.exists(MODELO)}


def _gravar(c):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = ARQ + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, ARQ)


def salvar(dados):
    with _trava:
        c = config()
        if "ligado" in dados:
            c["ligado"] = bool(dados["ligado"]) and bool(c.get("assinatura"))
        if "interromper" in dados:
            c["interromper"] = bool(dados["interromper"])
        if "limiar" in dados:
            c["limiar"] = round(min(0.9, max(0.15, float(dados["limiar"]))), 2)
        if "janela" in dados:
            c["janela"] = int(min(60, max(2, int(dados["janela"]))))
        _gravar(c)
    return publico()


# ------------------------------------------------------------------ características (fbank estilo Kaldi)
def _mel(f):
    return 1127.0 * np.log(1.0 + f / 700.0)


_BANCO = {}


def _banco(n_fft, sr=16000, n_mel=80, lo=20.0):
    if n_fft in _BANCO:
        return _BANCO[n_fft]
    hi = sr / 2
    mlo, mhi = _mel(lo), _mel(hi)
    centros = mlo + (mhi - mlo) * np.arange(n_mel + 2) / (n_mel + 1)
    freqs = _mel(np.arange(n_fft // 2) * sr / n_fft)  # o Kaldi ignora o bin de Nyquist
    b = np.zeros((n_mel, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mel):
        esq, cen, dir_ = centros[i], centros[i + 1], centros[i + 2]
        subida = (freqs - esq) / (cen - esq)
        descida = (dir_ - freqs) / (dir_ - cen)
        b[i, :n_fft // 2] = np.maximum(0, np.minimum(subida, descida))
    _BANCO[n_fft] = b
    return b


def fbank(audio, sr=16000):
    """80 bandas mel, janela 25 ms, passo 10 ms, janela 'povey', pré-ênfase 0,97 (como torchaudio.compliance.kaldi.fbank),
    com a média removida (CMN), que é o que o WeSpeaker espera."""
    x = np.asarray(audio, dtype=np.float32) * 32768.0
    tam, passo, n_fft = int(0.025 * sr), int(0.010 * sr), 512
    if len(x) < tam:
        return np.zeros((0, 80), dtype=np.float32)
    n = 1 + (len(x) - tam) // passo
    idx = np.arange(tam)[None, :] + passo * np.arange(n)[:, None]
    q = x[idx]
    q = q - q.mean(axis=1, keepdims=True)
    q = np.concatenate([q[:, :1] - 0.97 * q[:, :1], q[:, 1:] - 0.97 * q[:, :-1]], axis=1)
    q = q * (np.power(0.5 - 0.5 * np.cos(2 * np.pi * np.arange(tam) / (tam - 1)), 0.85))[None, :]
    esp = np.abs(np.fft.rfft(q, n=n_fft, axis=1)) ** 2
    f = np.log(np.maximum(esp @ _banco(n_fft, sr).T, np.finfo(np.float32).eps))
    return (f - f.mean(axis=0, keepdims=True)).astype(np.float32)


# ------------------------------------------------------------------ modelo
def _baixar():
    if os.path.exists(MODELO):
        return
    os.makedirs(os.path.dirname(MODELO), exist_ok=True)
    tmp = MODELO + ".parcial"
    with urllib.request.urlopen(URL, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            bloco = r.read(1 << 16)
            if not bloco:
                break
            f.write(bloco)
    if os.path.getsize(tmp) < 5_000_000:
        os.unlink(tmp)
        raise RuntimeError("o download do modelo de voz veio incompleto")
    os.replace(tmp, MODELO)


def _modelo():
    with _trava:
        if _sessao["s"] is None:
            _baixar()
            import onnxruntime as ort
            op = ort.SessionOptions()
            op.intra_op_num_threads = 1  # leve: não disputa CPU com o resto
            op.inter_op_num_threads = 1
            _sessao["s"] = ort.InferenceSession(MODELO, sess_options=op, providers=["CPUExecutionProvider"])
        return _sessao["s"]


def assinatura_de(audio):
    """Vetor normalizado da voz neste áudio (16 kHz mono float)."""
    feats = fbank(audio)
    if len(feats) < 50:  # menos de ~0,5 s de fala
        raise ValueError("áudio curto demais para reconhecer a voz")
    s = _modelo()
    e = s.run(None, {s.get_inputs()[0].name: feats[None, :, :]})[0].reshape(-1).astype(np.float32)
    return e / (np.linalg.norm(e) + 1e-9)


def _so_fala(audio, sr=16000):
    """Corta os silêncios (a comparação fica mais justa)."""
    q = int(0.03 * sr)
    if len(audio) < q * 4:
        return audio
    blocos = audio[: len(audio) // q * q].reshape(-1, q)
    energia = np.sqrt((blocos ** 2).mean(axis=1))
    lim = max(0.008, np.percentile(energia, 30) * 1.8)
    bons = blocos[energia > lim]
    return bons.reshape(-1) if len(bons) >= 10 else audio


def carregar(caminho):
    import jarvis_core as core
    return _so_fala(core._carregar_audio(caminho))


# ------------------------------------------------------------------ cadastro e verificação
def salvar_amostra(n, caminho):
    """Guarda a frase n (1..3) do cadastro e devolve a duração útil."""
    n = int(n)
    if n not in (1, 2, 3):
        raise ValueError("amostra inválida")
    audio = carregar(caminho)
    if len(audio) < 16000 * 1.5:
        raise ValueError("ficou curto: leia a frase inteira, em voz normal")
    os.makedirs(DIR_AMOSTRAS, exist_ok=True)
    np.save(os.path.join(DIR_AMOSTRAS, f"{n}.npy"), audio.astype(np.float32))
    return round(len(audio) / 16000, 1)


def concluir_cadastro():
    """Junta as 3 frases numa assinatura e sugere o limite a partir de quanto elas se parecem entre si."""
    amostras = []
    for n in (1, 2, 3):
        p = os.path.join(DIR_AMOSTRAS, f"{n}.npy")
        if not os.path.exists(p):
            raise ValueError(f"falta gravar a frase {n}")
        amostras.append(np.load(p))
    embs = [assinatura_de(a) for a in amostras]
    media = np.mean(embs, axis=0)
    media /= np.linalg.norm(media) + 1e-9
    entre = [float(embs[i] @ embs[j]) for i in range(3) for j in range(i + 1, 3)]
    # limite sugerido: um pouco abaixo da menor semelhança entre as suas próprias frases (entre 0,35 e 0,65)
    sugerido = round(min(0.65, max(0.35, min(entre) - 0.12)), 2)
    with _trava:
        c = config()
        c.update(assinatura=[round(float(v), 6) for v in media], sugerido=sugerido, limiar=sugerido, ligado=True,
                 cadastro={"quando": time.strftime("%d/%m/%Y %H:%M"), "semelhanca_entre_frases": [round(v, 2) for v in entre]})
        _gravar(c)
    for n in (1, 2, 3):
        try:
            os.unlink(os.path.join(DIR_AMOSTRAS, f"{n}.npy"))
        except OSError:
            pass
    return publico()


def apagar():
    with _trava:
        c = config()
        for k in ("assinatura", "cadastro", "sugerido"):
            c.pop(k, None)
        c["ligado"] = False
        _gravar(c)
    return publico()


def semelhanca(caminho):
    """Para o botão Testar: quanto esta fala se parece com a sua voz cadastrada (mesmo com o filtro desligado)."""
    c = config()
    if not c.get("assinatura"):
        raise ValueError("cadastre sua voz primeiro")
    sem = float(assinatura_de(carregar(caminho)) @ np.asarray(c["assinatura"], dtype=np.float32))
    return round(sem, 2), sem >= float(c["limiar"])


def verificar(caminho):
    """(é_o_dono, semelhança). Se o reconhecimento está desligado ou sem cadastro: (True, None)."""
    c = config()
    if not c["ligado"] or not c.get("assinatura"):
        return True, None
    audio = carregar(caminho)
    e = assinatura_de(audio)
    sem = float(e @ np.asarray(c["assinatura"], dtype=np.float32))
    return sem >= float(c["limiar"]), round(sem, 2)
