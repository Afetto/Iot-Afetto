"""
Camada de dados da IA do Afetto.

Carrega a base local de pets (data/pets.json), valida cada registro e
calcula os indicadores que a IA usa (idade, vacinas em dia, meses desde a
última consulta). Nenhum dado clínico é inventado: o que não existe na base
fica como desconhecido.
"""
import json
import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PETS_FILE = Path(os.getenv("AFETTO_PETS_FILE", str(BASE_DIR / "data" / "pets.json")))

ESPECIES_VALIDAS = {"cão", "gato", "outro"}
CAMPOS_OBRIGATORIOS = ("id", "nome", "especie", "data_nascimento")


class DadosInvalidos(ValueError):
    """Erro de validação da base de pets, com a lista de problemas encontrados."""

    def __init__(self, erros):
        super().__init__("; ".join(erros))
        self.erros = erros


def _data(valor, campo, erros):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        erros.append(f"{campo}: data inválida ({valor!r}), use AAAA-MM-DD")
        return None


def validar_pet(pet: dict, hoje: date | None = None) -> list[str]:
    """Retorna a lista de erros do registro (vazia quando está válido)."""
    hoje = hoje or date.today()
    erros = []
    pid = pet.get("id", "?") if isinstance(pet, dict) else "?"
    if not isinstance(pet, dict):
        return [f"pet {pid}: registro deve ser um objeto"]

    for campo in CAMPOS_OBRIGATORIOS:
        if not str(pet.get(campo, "")).strip():
            erros.append(f"pet {pid}: campo obrigatório ausente: {campo}")

    if pet.get("especie") and pet["especie"] not in ESPECIES_VALIDAS:
        erros.append(f"pet {pid}: espécie inválida ({pet['especie']})")

    nasc = _data(pet.get("data_nascimento"), f"pet {pid}.data_nascimento", erros) \
        if pet.get("data_nascimento") else None
    if nasc and nasc > hoje:
        erros.append(f"pet {pid}: data de nascimento no futuro")

    peso = pet.get("peso_kg")
    if peso is not None and (isinstance(peso, bool) or not isinstance(peso, (int, float)) or not 0 < peso <= 120):
        erros.append(f"pet {pid}: peso_kg deve ser um número entre 0 e 120")

    for i, vacina in enumerate(pet.get("vacinas", [])):
        if not vacina.get("nome"):
            erros.append(f"pet {pid}: vacina {i + 1} sem nome")
        aplicada = _data(vacina.get("aplicada_em"), f"pet {pid}.vacina {i + 1}.aplicada_em", erros)
        proxima = _data(vacina.get("proxima_dose"), f"pet {pid}.vacina {i + 1}.proxima_dose", erros)
        if aplicada and proxima and proxima < aplicada:
            erros.append(f"pet {pid}: vacina {vacina.get('nome')} com próxima dose antes da aplicação")

    for i, consulta in enumerate(pet.get("consultas", [])):
        dia = _data(consulta.get("data"), f"pet {pid}.consulta {i + 1}.data", erros)
        if dia and dia > hoje:
            erros.append(f"pet {pid}: consulta {i + 1} com data no futuro")

    for campo in ("doencas_cronicas", "medicamentos_ativos"):
        if not isinstance(pet.get(campo, []), list):
            erros.append(f"pet {pid}: {campo} deve ser uma lista")
    return erros


def carregar_pets(caminho: Path | None = None, hoje: date | None = None) -> list[dict]:
    """Lê e valida a base. Levanta DadosInvalidos se algum registro estiver errado."""
    caminho = Path(caminho or PETS_FILE)
    try:
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise DadosInvalidos([f"não foi possível ler {caminho.name}: {erro}"]) from erro

    pets = conteudo.get("pets") if isinstance(conteudo, dict) else None
    if not isinstance(pets, list) or not pets:
        raise DadosInvalidos(["o arquivo deve ter uma lista 'pets' não vazia"])

    erros, ids = [], set()
    for pet in pets:
        erros += validar_pet(pet, hoje)
        pid = pet.get("id") if isinstance(pet, dict) else None
        if pid in ids:
            erros.append(f"id duplicado: {pid}")
        ids.add(pid)
    if erros:
        raise DadosInvalidos(erros)
    return pets


def _meses_entre(inicio: date, fim: date) -> int:
    meses = (fim.year - inicio.year) * 12 + fim.month - inicio.month
    return meses - (1 if fim.day < inicio.day else 0)


def indicadores(pet: dict, hoje: date | None = None) -> dict:
    """Converte o histórico em indicadores usados pelo Guard e pelo Assistente."""
    hoje = hoje or date.today()
    nasc = date.fromisoformat(pet["data_nascimento"])
    vacinas = pet.get("vacinas", [])
    vencidas = [v["nome"] for v in vacinas if date.fromisoformat(v["proxima_dose"]) < hoje]
    proximas = sorted(
        (v for v in vacinas if date.fromisoformat(v["proxima_dose"]) >= hoje),
        key=lambda v: v["proxima_dose"],
    )
    consultas = sorted(pet.get("consultas", []), key=lambda c: c["data"])
    ultima = consultas[-1] if consultas else None

    return {
        "idade_anos": _meses_entre(nasc, hoje) // 12,
        "vacinas_em_dia": (not vencidas) if vacinas else None,
        "vacinas_vencidas": vencidas,
        "proxima_vacina": proximas[0] if proximas else None,
        "ultima_consulta": ultima,
        "ultima_consulta_meses": _meses_entre(date.fromisoformat(ultima["data"]), hoje) if ultima else None,
    }


def perfil_para_ia(pet: dict, hoje: date | None = None) -> dict:
    """Perfil completo (cadastro + indicadores) no formato que a IA consome."""
    return {
        "pet_id": pet["id"],
        "nome": pet["nome"],
        "especie": pet["especie"],
        "raca": pet.get("raca", "SRD"),
        "sexo": pet.get("sexo"),
        "peso_kg": pet.get("peso_kg"),
        "tutor": pet.get("tutor"),
        "device_id": pet.get("device_id"),
        "doencas_cronicas": pet.get("doencas_cronicas", []),
        "medicamentos_ativos": pet.get("medicamentos_ativos", []),
        "vacinas": pet.get("vacinas", []),
        "consultas": pet.get("consultas", []),
        **indicadores(pet, hoje),
    }


def buscar_pet(chave: str, pets: list[dict] | None = None) -> dict | None:
    """Procura por id, nome (sem diferenciar maiúsculas) ou device_id."""
    if not chave:
        return None
    alvo = str(chave).strip().lower()
    for pet in pets if pets is not None else carregar_pets():
        if alvo in {str(pet.get("id", "")).lower(), str(pet.get("nome", "")).lower(),
                    str(pet.get("device_id", "")).lower()}:
            return pet
    return None
