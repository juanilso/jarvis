"""Anexos enviados ao Jarvis (painel e Telegram): imagens, vídeos e arquivos.

O Claude enxerga imagens, mas não "assiste" vídeo. Para vídeo, o Jarvis extrai quadros espalhados pelo vídeo (com o
instante de cada um) e transcreve a fala; o Claude recebe os quadros como imagens + a transcrição, e o caminho do
vídeo original (para cortar mais quadros num trecho específico, se precisar).
Tudo fica em /workspace/.jarvis-anexos (fora dos projetos: não vai para o Git) e é apagado depois de 30 dias.
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid

import jarvis_core as core

DIR = os.path.join(core.WORKSPACE, ".jarvis-anexos")
IMAGENS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}
VIDEOS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp", ".mpeg", ".mpg"}
MAX_BYTES = 500 * 1024 * 1024
MAX_QUADROS = 12
MAX_FALA_SEG = 15 * 60
DIAS = 30


def tipo(caminho):
    ext = os.path.splitext(caminho)[1].lower()
    return "imagem" if ext in IMAGENS else "video" if ext in VIDEOS else "arquivo"


def novo_caminho(nome_original):
    os.makedirs(DIR, exist_ok=True)
    ext = os.path.splitext(nome_original or "")[1].lower()
    ext = ext if re.fullmatch(r"\.[a-z0-9]{1,6}", ext) else ".bin"
    base = re.sub(r"[^\w.-]+", "-", os.path.splitext(os.path.basename(nome_original or "anexo"))[0])[:40].strip("-") or "anexo"
    return os.path.join(DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}-{base}{ext}")


def receber(nome_original, leitor, tamanho):
    """Grava o upload em partes (sem carregar tudo na memória). leitor(n) -> bytes."""
    if tamanho <= 0:
        raise ValueError("arquivo vazio")
    if tamanho > MAX_BYTES:
        raise ValueError(f"arquivo grande demais (máx. {MAX_BYTES // 1024 // 1024} MB)")
    destino = novo_caminho(nome_original)
    falta = tamanho
    with open(destino, "wb") as f:
        while falta > 0:
            bloco = leitor(min(1 << 20, falta))
            if not bloco:
                break
            f.write(bloco)
            falta -= len(bloco)
    if falta:
        os.unlink(destino)
        raise ValueError("envio interrompido")
    limpar_antigos()
    return destino


def valido(caminho):
    """Só aceita caminhos dentro da pasta de anexos (o painel manda o caminho de volta)."""
    real = os.path.realpath(caminho or "")
    return real.startswith(os.path.realpath(DIR) + os.sep) and os.path.isfile(real)


def limpar_antigos():
    limite = time.time() - DIAS * 86400
    try:
        for n in os.listdir(DIR):
            c = os.path.join(DIR, n)
            if os.path.getmtime(c) < limite:
                shutil.rmtree(c, ignore_errors=True) if os.path.isdir(c) else os.unlink(c)
    except OSError:
        pass


def _duracao(caminho):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", caminho],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _tem_audio(caminho):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                        caminho], capture_output=True, text=True, timeout=60)
    return bool(r.stdout.strip())


def _hms(seg):
    seg = int(seg)
    return f"{seg // 60:02d}:{seg % 60:02d}" if seg < 3600 else f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


def preparar_video(caminho, transcrever=True):
    """Extrai quadros (com o instante) e a fala. Devolve {duracao, quadros: [(seg, caminho)], fala, aviso}."""
    dur = _duracao(caminho)
    pasta = os.path.splitext(caminho)[0] + "-quadros"
    os.makedirs(pasta, exist_ok=True)
    n = MAX_QUADROS if dur > 60 else max(4, min(MAX_QUADROS, int(dur / 4) + 2)) if dur else 1
    instantes = [dur * (i + 0.5) / n for i in range(n)] if dur else [0]
    quadros = []
    for t in instantes:
        saida = os.path.join(pasta, f"q-{int(t * 10):06d}.jpg")
        r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", caminho,
                            "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", saida],
                           capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(saida):
            quadros.append((t, saida))
    fala, aviso = "", ""
    if transcrever and _tem_audio(caminho):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                wav = os.path.join(tmp, "a.wav")
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", caminho, "-t", str(MAX_FALA_SEG),
                                "-vn", "-ac", "1", "-ar", "16000", wav], check=True, capture_output=True, timeout=600)
                fala = core.transcrever(wav)
            if dur > MAX_FALA_SEG:
                aviso = f"(fala transcrita só dos primeiros {MAX_FALA_SEG // 60} minutos)"
        except Exception as e:  # noqa: BLE001
            aviso = f"(não consegui transcrever a fala: {type(e).__name__})"
    return {"duracao": dur, "quadros": quadros, "fala": fala, "aviso": aviso}


def montar_pedido(pedido, caminhos, origem="painel", avisar=None):
    """Texto para o Claude com cada anexo preparado. avisar(texto) recebe o andamento (vídeo demora)."""
    blocos = []
    for c in caminhos:
        t = tipo(c)
        if t == "imagem":
            blocos.append(f"- IMAGEM: {c}")
        elif t == "video":
            if avisar:
                avisar(f"🎞️ Preparando o vídeo {os.path.basename(c)} (quadros e fala)…")
            v = preparar_video(c)
            linhas = [f"- VÍDEO ({_hms(v['duracao'])}): {c}",
                      "  Quadros (abra cada um com Read; o instante está ao lado):"]
            linhas += [f"    [{_hms(s)}] {q}" for s, q in v["quadros"]]
            if v["fala"]:
                linhas.append(f"  Fala transcrita {v['aviso']}: “{v['fala'][:6000]}”")
            elif v["aviso"]:
                linhas.append("  " + v["aviso"])
            else:
                linhas.append("  (sem fala)")
            linhas.append("  Precisa ver um trecho com mais detalhe? Extraia mais quadros: "
                          f"ffmpeg -ss <mm:ss> -i {c} -frames:v 4 -vf fps=2 <pasta>/q%d.jpg")
            blocos.append("\n".join(linhas))
        else:
            blocos.append(f"- ARQUIVO: {c}")
    pedido = pedido or "Analise o(s) anexo(s) e me diga o que você vê e o que sugere fazer neste projeto."
    return (f"{pedido}\n\n[Anexos enviados pelo usuário pelo {origem}. Abra cada imagem e cada quadro com a ferramenta Read "
            "antes de responder: é assim que você vê o que ele mostrou (tela com erro, layout de referência, fluxo "
            "gravado…). Não faça commit destes arquivos; se algum precisar ir para o projeto (ex.: logo), copie.]\n"
            + "\n".join(blocos))
