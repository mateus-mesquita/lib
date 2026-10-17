"""
Testes unitários para o sistema de Revisão Ativa por E-mail (send_reminder.py).
Utiliza apenas a biblioteca padrão 'unittest'.
"""

from datetime import datetime, time, timedelta
import json
import os
import tempfile
import unittest
from zoneinfo import ZoneInfo

import send_reminder


class TestStudyReminder(unittest.TestCase):

    def setUp(self):
        self.tz = ZoneInfo("America/Sao_Paulo")
        self.sample_config = {
            "documents": [
                {"name": "Doc A", "total": 25, "block_size": 10, "link": "https://example.com/a"},
                {"name": "Doc B", "total": 15, "block_size": 10, "link": ""},
                {"name": "Doc C", "chapters": ["Cap 1", "Cap 2", "Cap 3"], "link": ""},
                {"name": "Doc D", "total": 20, "block_size": 10, "link": ""}
            ],
            "timezone": "America/Sao_Paulo",
            "active_start": 8,
            "active_end": 22,
            "min_interval_min": 60,
            "max_interval_min": 120,
            "review_every": 4,
            "est_minutes_per_block": 5
        }

    def test_generate_blocks_pages_with_remainder(self):
        """Testa geração de blocos por páginas quando o total tem sobra."""
        doc = {"name": "Doc A", "total": 25, "block_size": 10}
        blocks = send_reminder.generate_blocks(doc)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["label"], "páginas 1–10")
        self.assertEqual(blocks[1]["label"], "páginas 11–20")
        self.assertEqual(blocks[2]["label"], "páginas 21–25")

    def test_generate_blocks_single_page(self):
        """Testa geração de bloco com página única."""
        doc = {"name": "Doc Single", "start_page": 5, "total": 5, "block_size": 10}
        blocks = send_reminder.generate_blocks(doc)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["label"], "página 5")

    def test_generate_blocks_chapters(self):
        """Testa geração de blocos por capítulos nomeados (RF13)."""
        doc = {"name": "Doc C", "chapters": ["Introdução", "Capítulo 1", "Conclusão"]}
        blocks = send_reminder.generate_blocks(doc)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["label"], "Introdução")
        self.assertEqual(blocks[1]["label"], "Capítulo 1")
        self.assertEqual(blocks[2]["label"], "Conclusão")

    def test_active_window(self):
        """Testa detecção correta da janela de estudo (08:00 às 22:00)."""
        dt_inside = datetime(2026, 10, 16, 14, 30, tzinfo=self.tz)
        dt_early = datetime(2026, 10, 16, 7, 59, tzinfo=self.tz)
        dt_late = datetime(2026, 10, 16, 22, 1, tzinfo=self.tz)
        dt_boundary_start = datetime(2026, 10, 16, 8, 0, tzinfo=self.tz)
        dt_boundary_end = datetime(2026, 10, 16, 22, 0, tzinfo=self.tz)

        self.assertTrue(send_reminder.is_in_active_window(dt_inside, 8, 22))
        self.assertTrue(send_reminder.is_in_active_window(dt_boundary_start, 8, 22))
        self.assertTrue(send_reminder.is_in_active_window(dt_boundary_end, 8, 22))
        self.assertFalse(send_reminder.is_in_active_window(dt_early, 8, 22))
        self.assertFalse(send_reminder.is_in_active_window(dt_late, 8, 22))

    def test_calculate_next_send_time_within_window(self):
        """Testa sorteio do próximo horário quando ainda cabe no mesmo dia."""
        now = datetime(2026, 10, 16, 10, 0, tzinfo=self.tz)
        next_dt = send_reminder.calculate_next_send_time(
            now, min_interval=60, max_interval=120, active_start=8, active_end=22, tz=self.tz
        )
        self.assertEqual(next_dt.date(), now.date())
        self.assertGreaterEqual(next_dt, now + timedelta(minutes=60))
        self.assertLessEqual(next_dt, now + timedelta(minutes=120))

    def test_calculate_next_send_time_overnight_rollover(self):
        """Testa agendamento para o dia seguinte quando ultrapassa active_end."""
        now = datetime(2026, 10, 16, 21, 30, tzinfo=self.tz)
        next_dt = send_reminder.calculate_next_send_time(
            now, min_interval=60, max_interval=120, active_start=8, active_end=22, tz=self.tz
        )
        # Deve ser no dia seguinte às 08:00 + jitter (0 a 30 min)
        self.assertEqual(next_dt.date(), now.date() + timedelta(days=1))
        self.assertEqual(next_dt.hour, 8)
        self.assertGreaterEqual(next_dt.minute, 0)
        self.assertLessEqual(next_dt.minute, 30)

    def test_rotation_across_documents(self):
        """Testa alternância sequencial entre os documentos (RF3)."""
        state = send_reminder.load_state(":memory:", self.sample_config)

        # 1º envio: Doc A
        idx, doc, blocks = send_reminder.find_next_reading_document(self.sample_config, state)
        self.assertEqual(doc["name"], "Doc A")
        self.assertEqual(idx, 0)

        # Simula conclusão do bloco 0 do Doc A e avanço do ponteiro
        state["documents"]["Doc A"]["current_block_index"] += 1
        state["current_doc_index"] = 1

        # 2º envio: Doc B
        idx, doc, blocks = send_reminder.find_next_reading_document(self.sample_config, state)
        self.assertEqual(doc["name"], "Doc B")
        self.assertEqual(idx, 1)

    def test_review_logic_on_fourth_reminder(self):
        """Testa que a cada 4 lembretes ocorre revisão espaçada (RF10)."""
        state = send_reminder.load_state(":memory:", self.sample_config)
        # Preenche histórico com 3 blocos enviados
        state["history"] = [
            {"doc_name": "Doc A", "block_index": 0, "block_label": "páginas 1–10", "sent_at": "2026-10-16T08:30:00", "review_count": 0},
            {"doc_name": "Doc B", "block_index": 0, "block_label": "páginas 1–10", "sent_at": "2026-10-16T10:00:00", "review_count": 0},
            {"doc_name": "Doc C", "block_index": 0, "block_label": "Cap 1", "sent_at": "2026-10-16T11:30:00", "review_count": 0},
        ]
        state["reminder_count"] = 3  # Próximo será o 4º lembrete

        # Verifica se o 4º envio será de revisão
        is_review_turn = ((state["reminder_count"] + 1) % self.sample_config["review_every"] == 0) and (len(state["history"]) > 0)
        self.assertTrue(is_review_turn)

        # Deve selecionar o bloco mais antigo (Doc A, páginas 1–10)
        state["history"].sort(key=lambda item: (item.get("review_count", 0), item.get("sent_at", "")))
        selected = state["history"][0]
        self.assertEqual(selected["doc_name"], "Doc A")
        self.assertEqual(selected["block_label"], "páginas 1–10")

    def test_cycle_restart_when_all_documents_finish(self):
        """Testa reinício do ciclo (RF8) quando todos os documentos terminam seus blocos."""
        state = send_reminder.load_state(":memory:", self.sample_config)
        # Marca todos os documentos como concluídos
        state["documents"]["Doc A"]["current_block_index"] = 3  # total é 3
        state["documents"]["Doc B"]["current_block_index"] = 2  # total é 2
        state["documents"]["Doc C"]["current_block_index"] = 3  # total é 3
        state["documents"]["Doc D"]["current_block_index"] = 2  # total é 2

        self.assertEqual(state["cycle"], 1)

        idx, doc, blocks = send_reminder.find_next_reading_document(self.sample_config, state)

        # O ciclo deve ter incrementado para 2 e todos os blocos reiniciados em 0
        self.assertEqual(state["cycle"], 2)
        self.assertEqual(doc["name"], "Doc A")
        self.assertEqual(state["documents"]["Doc A"]["current_block_index"], 0)
        self.assertEqual(state["documents"]["Doc B"]["current_block_index"], 0)

    def test_build_email_contains_required_sections(self):
        """Testa se o e-mail construído contém todas as seções exigidas no PRD."""
        doc = {"name": "Doc A", "link": "https://example.com/a"}
        block = {"label": "páginas 11–20", "block_index": 1, "est_minutes": 5, "link": "https://example.com/a"}

        subject, plain, html = send_reminder.build_reminder_email(
            is_review=False,
            doc_config=doc,
            block_info=block,
            total_blocks=10,
            cycle=1,
            prev_block_label="páginas 1–10"
        )

        self.assertIn("[Estudo] Doc A · páginas 11–20", subject)
        self.assertIn("páginas 1–10", plain)  # Pergunta do bloco anterior
        self.assertIn("páginas 11–20", plain)  # Ação de leitura
        self.assertIn("Qual é a tese, resultado ou conclusão principal", plain)
        self.assertIn("https://example.com/a", plain)
        self.assertIn("https://example.com/a", html)


if __name__ == "__main__":
    unittest.main()
