"""Configuração comum dos testes: banco SQLite temporário e Ollama desligado."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TesteComBanco(unittest.TestCase):
    """Cada teste usa um banco novo e nunca chama o Ollama de verdade."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {"AFETTO_DB": str(Path(self._tmp.name) / "teste.db")})
        self._env.start()
        import guard
        self._llm = patch.object(guard, "chamar_llama", return_value=None)
        self._llm.start()
        self.guard = guard
        self.client = guard.app.test_client()

    def tearDown(self):
        self._llm.stop()
        self._env.stop()
        self._tmp.cleanup()
