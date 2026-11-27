"""Uma tarefa pesada por vez (vídeo de jogos, vídeo de filme): duas renderizações juntas travavam a VPS.
Trava por arquivo, então vale entre processos do mesmo container. A segunda espera a primeira terminar."""
import contextlib
import fcntl
import os

ARQ = os.environ.get("JARVIS_TRAVA_PESADO", "/tmp/jarvis-pesado.lock")


@contextlib.contextmanager
def um_por_vez(ao_esperar=None):
    f = open(ARQ, "a+")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if ao_esperar:
                ao_esperar()
            fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()
