"""
Persistência local da IA do Afetto (SQLite).

Guarda o histórico de telemetria da coleira, as análises do Guard e as
conversas do Assistente. O arquivo fica em runtime/afetto.db (ou no caminho
definido em AFETTO_DB) e é criado automaticamente na primeira execução.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

ESQUEMA = """
CREATE TABLE IF NOT EXISTS telemetria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id      TEXT,
    pet_nome    TEXT NOT NULL,
    device_id   TEXT,
    temperatura REAL NOT NULL,
    atividade   REAL NOT NULL,
    status      TEXT,
    alerta      TEXT,
    recebido_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analises (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id     TEXT,
    pet_nome   TEXT NOT NULL,
    score      INTEGER NOT NULL,
    nivel      TEXT NOT NULL,
    fonte      TEXT NOT NULL,
    resultado  TEXT NOT NULL,
    criado_em  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensagens (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sessao_id TEXT NOT NULL,
    pet_id    TEXT,
    papel     TEXT NOT NULL CHECK (papel IN ('tutor', 'afetto')),
    conteudo  TEXT NOT NULL,
    fonte     TEXT,
    criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetria_pet ON telemetria (pet_id, id);
CREATE INDEX IF NOT EXISTS idx_analises_pet   ON analises (pet_id, id);
CREATE INDEX IF NOT EXISTS idx_mensagens_sess ON mensagens (sessao_id, id);
"""


def caminho_db() -> Path:
    return Path(os.getenv("AFETTO_DB", str(BASE_DIR / "runtime" / "afetto.db")))


def agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def idade_segundos(iso: str) -> float:
    """Há quantos segundos o registro foi gravado (infinito se a data for inválida)."""
    try:
        return (datetime.now().astimezone() - datetime.fromisoformat(iso)).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


@contextmanager
def conexao():
    caminho = caminho_db()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(ESQUEMA)
        yield con
        con.commit()
    finally:
        con.close()


# ── Telemetria ──────────────────────────────────────────────────────────────
def salvar_telemetria(pet_id, pet_nome, temperatura, atividade, status=None,
                      device_id=None, alerta=None, recebido_em=None) -> int:
    with conexao() as con:
        cur = con.execute(
            "INSERT INTO telemetria (pet_id, pet_nome, device_id, temperatura, atividade,"
            " status, alerta, recebido_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pet_id, pet_nome, device_id, float(temperatura), float(atividade),
             status, alerta, recebido_em or agora()),
        )
        return cur.lastrowid


def listar_telemetria(pet_id, limite=20) -> list[dict]:
    with conexao() as con:
        linhas = con.execute(
            "SELECT * FROM telemetria WHERE pet_id = ? ORDER BY id DESC LIMIT ?",
            (pet_id, int(limite)),
        ).fetchall()
    return [dict(l) for l in linhas]


# ── Análises do Guard ───────────────────────────────────────────────────────
def salvar_analise(pet_id, pet_nome, resultado: dict) -> int:
    analise = resultado.get("analise", {})
    with conexao() as con:
        cur = con.execute(
            "INSERT INTO analises (pet_id, pet_nome, score, nivel, fonte, resultado, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pet_id, pet_nome, int(analise.get("score_risco", 0)), analise.get("nivel", "?"),
             resultado.get("fonte", "?"), json.dumps(resultado, ensure_ascii=False), agora()),
        )
        return cur.lastrowid


def listar_analises(pet_id, limite=10) -> list[dict]:
    with conexao() as con:
        linhas = con.execute(
            "SELECT * FROM analises WHERE pet_id = ? ORDER BY id DESC LIMIT ?",
            (pet_id, int(limite)),
        ).fetchall()
    resultado = []
    for l in linhas:
        item = dict(l)
        item["resultado"] = json.loads(item["resultado"])
        resultado.append(item)
    return resultado


# ── Conversas do Assistente ─────────────────────────────────────────────────
def salvar_mensagem(sessao_id, pet_id, papel, conteudo, fonte=None) -> int:
    with conexao() as con:
        cur = con.execute(
            "INSERT INTO mensagens (sessao_id, pet_id, papel, conteudo, fonte, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (sessao_id, pet_id, papel, conteudo, fonte, agora()),
        )
        return cur.lastrowid


def historico_sessao(sessao_id, limite=8) -> list[dict]:
    with conexao() as con:
        linhas = con.execute(
            "SELECT * FROM (SELECT * FROM mensagens WHERE sessao_id = ? ORDER BY id DESC LIMIT ?)"
            " ORDER BY id",
            (sessao_id, int(limite)),
        ).fetchall()
    return [dict(l) for l in linhas]


def resumo() -> dict:
    """Contagem de registros por tabela (usado no /health e nas evidências)."""
    with conexao() as con:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("telemetria", "analises", "mensagens")}
