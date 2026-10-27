"""Validação e preparação dos dados que alimentam a IA (data/pets.json)."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import apoio  # noqa: F401  (ajusta o sys.path)
import dados

HOJE = date(2026, 10, 27)


def pet_valido(**mudancas):
    pet = {
        "id": "teste", "nome": "Teste", "especie": "cão", "data_nascimento": "2020-01-15",
        "peso_kg": 10.0,
        "vacinas": [{"nome": "V10", "aplicada_em": "2026-01-01", "proxima_dose": "2027-01-01"}],
        "consultas": [{"data": "2026-04-10", "motivo": "Check-up"}],
    }
    pet.update(mudancas)
    return pet


class ValidacaoTest(unittest.TestCase):
    def test_base_do_projeto_e_valida(self):
        pets = dados.carregar_pets()
        self.assertEqual({p["id"] for p in pets}, {"bolinha", "felix", "mel"})

    def test_registro_valido_sem_erros(self):
        self.assertEqual(dados.validar_pet(pet_valido(), HOJE), [])

    def test_detecta_campos_e_valores_invalidos(self):
        erros = dados.validar_pet(pet_valido(nome="", especie="dragão", peso_kg=-3,
                                             data_nascimento="2030-01-01"), HOJE)
        texto = " | ".join(erros)
        self.assertIn("nome", texto)
        self.assertIn("espécie inválida", texto)
        self.assertIn("peso_kg", texto)
        self.assertIn("no futuro", texto)

    def test_detecta_datas_de_vacina_incoerentes(self):
        vacina = {"nome": "V10", "aplicada_em": "2026-05-01", "proxima_dose": "2026-01-01"}
        erros = dados.validar_pet(pet_valido(vacinas=[vacina]), HOJE)
        self.assertTrue(any("próxima dose antes" in e for e in erros))

    def test_detecta_data_mal_formatada(self):
        erros = dados.validar_pet(pet_valido(consultas=[{"data": "10/04/2026", "motivo": "x"}]), HOJE)
        self.assertTrue(any("AAAA-MM-DD" in e for e in erros))

    def test_arquivo_com_id_duplicado_e_rejeitado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "pets.json"
            caminho.write_text(json.dumps({"pets": [pet_valido(), pet_valido()]}), encoding="utf-8")
            with self.assertRaises(dados.DadosInvalidos) as ctx:
                dados.carregar_pets(caminho, HOJE)
        self.assertIn("id duplicado: teste", ctx.exception.erros)


class IndicadoresTest(unittest.TestCase):
    def test_calcula_idade_e_meses_desde_consulta(self):
        ind = dados.indicadores(pet_valido(), HOJE)
        self.assertEqual(ind["idade_anos"], 6)
        self.assertEqual(ind["ultima_consulta_meses"], 6)
        self.assertTrue(ind["vacinas_em_dia"])
        self.assertEqual(ind["proxima_vacina"]["nome"], "V10")

    def test_identifica_vacina_vencida(self):
        vacina = {"nome": "Antirrábica", "aplicada_em": "2025-01-01", "proxima_dose": "2026-01-01"}
        ind = dados.indicadores(pet_valido(vacinas=[vacina]), HOJE)
        self.assertFalse(ind["vacinas_em_dia"])
        self.assertEqual(ind["vacinas_vencidas"], ["Antirrábica"])

    def test_sem_vacinas_fica_desconhecido(self):
        self.assertIsNone(dados.indicadores(pet_valido(vacinas=[]), HOJE)["vacinas_em_dia"])

    def test_busca_por_nome_e_coleira(self):
        pets = dados.carregar_pets()
        self.assertEqual(dados.buscar_pet("MEL", pets)["id"], "mel")
        self.assertEqual(dados.buscar_pet("coleira-002", pets)["id"], "felix")
        self.assertIsNone(dados.buscar_pet("rex", pets))


if __name__ == "__main__":
    unittest.main()
