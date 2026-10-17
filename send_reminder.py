#!/usr/bin/env python3
"""
Revisão Ativa por E-mail (send_reminder.py)

Envia lembretes periódicos de estudo com técnicas de recuperação ativa,
intercalação entre documentos e repetição espaçada via GitHub Actions.
Utiliza apenas a biblioteca padrão do Python (smtplib, json, zoneinfo, etc.).
"""

import argparse
from datetime import datetime, time, timedelta
from email.message import EmailMessage
import json
import os
import random
import smtplib
import sys
from zoneinfo import ZoneInfo


CONFIG_FILE = "config.json"
STATE_FILE = "state.json"

# Assegura que o terminal no Windows suporte UTF-8 sem erro de codificação
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_config(config_path: str = CONFIG_FILE) -> dict:
    """Carrega as configurações do projeto a partir do arquivo JSON."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Defaults
    config.setdefault("timezone", "America/Sao_Paulo")
    config.setdefault("active_start", 8)
    config.setdefault("active_end", 22)
    config.setdefault("min_interval_min", 60)
    config.setdefault("max_interval_min", 120)
    config.setdefault("review_every", 4)
    config.setdefault("est_minutes_per_block", 5)
    config.setdefault("documents", [])
    return config


def generate_blocks(doc_config: dict, default_est_minutes: int = 5) -> list[dict]:
    """
    Gera a lista de blocos de um documento.
    Suporta divisão por páginas (total e block_size) ou capítulos nomeados (chapters).
    """
    blocks = []
    name = doc_config.get("name", "Documento")
    link = doc_config.get("link", "").strip()
    est_minutes = doc_config.get("est_minutes", default_est_minutes)

    # Suporte a capítulos nomeados (RF13)
    if "chapters" in doc_config and doc_config["chapters"]:
        for idx, chapter in enumerate(doc_config["chapters"]):
            blocks.append({
                "doc_name": name,
                "block_index": idx,
                "label": str(chapter).strip(),
                "link": link,
                "est_minutes": est_minutes
            })
        return blocks

    # Divisão por páginas sequenciais (RF2)
    start_page = int(doc_config.get("start_page", 1))
    total_pages = int(doc_config.get("total", 0))
    block_size = int(doc_config.get("block_size", 10))

    if total_pages < start_page or block_size <= 0:
        print(f"[Aviso] Documento '{name}' possui configuração de páginas inválida (total: {total_pages}, start: {start_page}, block_size: {block_size}).")
        return []

    curr = start_page
    idx = 0
    while curr <= total_pages:
        end = min(curr + block_size - 1, total_pages)
        label = f"páginas {curr}–{end}" if curr != end else f"página {curr}"
        blocks.append({
            "doc_name": name,
            "block_index": idx,
            "label": label,
            "link": link,
            "est_minutes": est_minutes,
            "start_page": curr,
            "end_page": end
        })
        curr = end + 1
        idx += 1

    return blocks


def load_state(state_path: str = STATE_FILE, config: dict | None = None) -> dict:
    """Carrega o estado persistido ou cria a estrutura inicial se não existir."""
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            print(f"[Aviso] Erro ao ler {state_path} ({e}). Inicializando novo estado.")
            state = {}
    else:
        state = {}

    state.setdefault("cycle", 1)
    state.setdefault("current_doc_index", 0)
    state.setdefault("reminder_count", 0)
    state.setdefault("last_sent_at", None)
    state.setdefault("next_send_at", None)
    state.setdefault("documents", {})
    state.setdefault("history", [])

    if config and "documents" in config:
        for doc in config["documents"]:
            doc_name = doc.get("name")
            if not doc_name:
                continue
            doc_blocks = generate_blocks(doc, config.get("est_minutes_per_block", 5))
            total_blocks = len(doc_blocks)
            if doc_name not in state["documents"]:
                state["documents"][doc_name] = {
                    "current_block_index": 0,
                    "total_blocks": total_blocks,
                    "completed_blocks": 0
                }
            else:
                # Atualiza total de blocos caso config tenha mudado
                state["documents"][doc_name]["total_blocks"] = total_blocks

    return state


def save_state(state: dict, state_path: str = STATE_FILE) -> None:
    """Salva o estado no arquivo JSON com formatação legível."""
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_now(timezone_str: str) -> datetime:
    """Retorna o horário atual com fuso horário configurado."""
    tz = ZoneInfo(timezone_str)
    return datetime.now(tz)


def is_in_active_window(now: datetime, active_start: int, active_end: int) -> bool:
    """Verifica se o horário está dentro da janela de estudo (ex.: 08:00 às 22:00)."""
    start_time = time(active_start, 0)
    end_time = time(active_end, 0)
    return start_time <= now.time() <= end_time


def calculate_next_send_time(
    now: datetime,
    min_interval: int,
    max_interval: int,
    active_start: int,
    active_end: int,
    tz: ZoneInfo
) -> datetime:
    """
    Sorteia o próximo horário de envio dentro da janela permitida.
    Se o intervalo ultrapassar active_end, agenda para a manhã seguinte (active_start + jitter).
    """
    interval_minutes = random.randint(min_interval, max_interval)
    candidate = now + timedelta(minutes=interval_minutes)

    start_time = time(active_start, 0)
    end_time = time(active_end, 0)

    # Se o horário candidato passar do fim da janela hoje:
    if candidate.time() > end_time or candidate.time() < start_time:
        # Agendar para amanhã na abertura da janela com um pequeno jitter aleatório (0 a 30 min)
        jitter = random.randint(0, 30)
        tomorrow = now.date() + timedelta(days=1)
        next_dt = datetime.combine(tomorrow, start_time, tzinfo=tz) + timedelta(minutes=jitter)
        return next_dt

    return candidate


def find_next_reading_document(config: dict, state: dict) -> tuple[int, dict, list[dict]]:
    """
    Localiza o próximo documento da rodada que ainda possui blocos para leitura.
    Reinicia o ciclo se todos tiverem terminado seus blocos.
    Retorna: (doc_index, doc_config, blocks)
    """
    docs = config.get("documents", [])
    if not docs:
        raise ValueError("Nenhum documento configurado em config.json.")

    num_docs = len(docs)
    start_index = state.get("current_doc_index", 0) % num_docs

    # Verifica se algum documento ainda tem blocos no ciclo atual
    for offset in range(num_docs):
        idx = (start_index + offset) % num_docs
        doc = docs[idx]
        doc_name = doc["name"]
        blocks = generate_blocks(doc, config.get("est_minutes_per_block", 5))
        doc_state = state["documents"].get(doc_name, {})
        curr_block = doc_state.get("current_block_index", 0)

        if curr_block < len(blocks):
            return idx, doc, blocks

    # Se chegou aqui, todos os documentos terminaram seus blocos neste ciclo!
    # Reinicia o ciclo (RF8)
    state["cycle"] += 1
    print(f"🎉 Todos os documentos foram concluídos no ciclo {state['cycle'] - 1}! Iniciando Ciclo {state['cycle']}.")
    for doc in docs:
        d_name = doc["name"]
        if d_name in state["documents"]:
            state["documents"][d_name]["current_block_index"] = 0

    first_doc = docs[0]
    first_blocks = generate_blocks(first_doc, config.get("est_minutes_per_block", 5))
    return 0, first_doc, first_blocks


def build_reminder_email(
    is_review: bool,
    doc_config: dict,
    block_info: dict,
    total_blocks: int,
    cycle: int,
    prev_block_label: str | None = None
) -> tuple[str, str, str]:
    """
    Constrói o assunto, corpo em texto puro e corpo alternativo em HTML
    para lembretes regulares ou de revisão espaçada.
    """
    doc_name = doc_config.get("name", "Documento")
    block_label = block_info.get("label", "")
    block_idx = block_info.get("block_index", 0)
    block_num = block_idx + 1
    est_minutes = block_info.get("est_minutes", 5)
    link = block_info.get("link", "").strip()

    progress_pct = (block_num / total_blocks * 100) if total_blocks > 0 else 100

    if is_review:
        # Lembrete de Revisão Espaçada (RF10)
        subject = f"[Estudo] {doc_name} · Revisão ({block_label})"

        link_text_plain = f"\nLink do documento: {link}\n" if link else ""
        link_html = f'<p style="margin: 16px 0;"><a href="{link}" style="background-color: #2563eb; color: #ffffff; padding: 10px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Abrir Documento</a></p>' if link else ""

        plain_text = f"""======================================================
REVISÃO ATIVA DE ESTUDO · ESPAÇAMENTO
======================================================

Documento: {doc_name}
Bloco de Revisão: {block_label} (bloco {block_num} de {total_blocks})
Ciclo Atual: Rodada {cycle}
{link_text_plain}
------------------------------------------------------
🚨 AÇÃO DE REVISÃO (SEM ABRIR O DOCUMENTO PRIMEIRO):
------------------------------------------------------
Não abra o documento agora. Pegue papel e caneta ou abra
uma folha em branco e escreva de memória tudo o que lembrar
deste trecho.

GUIA DE RECUPERAÇÃO ATIVA:
1. Quais foram as principais conclusões, regras ou conceitos apresentados?
2. Explique com suas próprias palavras a ideia mais importante desse bloco.
3. Quais pontos você sente dúvida ou não recorda com clareza?

------------------------------------------------------
APÓS TENTAR LEMBRAR:
------------------------------------------------------
Abra o documento e confira:
- O que você lembrou com exatidão?
- Qual ponto crucial você havia esquecido? (Anote para fixar!)

Bons estudos!
"""

        html_text = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .card {{ background: #ffffff; max-width: 600px; margin: 0 auto; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); padding: 28px; }}
    .badge {{ background-color: #fef3c7; color: #92400e; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 9999px; display: inline-block; }}
    h1 {{ font-size: 20px; color: #0f172a; margin: 16px 0 8px 0; }}
    .subtitle {{ color: #64748b; font-size: 14px; margin-bottom: 20px; }}
    .action-box {{ background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 14px 18px; border-radius: 6px; margin: 20px 0; }}
    .action-box strong {{ color: #b45309; }}
    ol {{ padding-left: 20px; line-height: 1.6; color: #334155; }}
    li {{ margin-bottom: 8px; }}
    .footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #f1f5f9; font-size: 12px; color: #94a3b8; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Revisão Espaçada</span>
    <h1>{doc_name}</h1>
    <div class="subtitle">{block_label} · Bloco {block_num} de {total_blocks} · Rodada {cycle}</div>

    <div class="action-box">
      <strong>🚨 Ação (Sem abrir o material antes):</strong>
      <p style="margin: 6px 0 0 0;">Escreva de memória tudo o que lembrar de <strong>{doc_name} ({block_label})</strong> antes de consultar o texto.</p>
    </div>

    {link_html}

    <h3 style="font-size: 15px; color: #0f172a; margin-top: 20px;">Perguntas de Recuperação Ativa:</h3>
    <ol>
      <li>Quais foram os conceitos, definições ou conclusões principais apresentados?</li>
      <li>Como você explicaria esse trecho com suas próprias palavras para outra pessoa?</li>
      <li>Quais aspectos você teve dificuldade de resgatar da memória?</li>
    </ol>

    <div style="background-color: #f8fafc; border-radius: 6px; padding: 12px 16px; margin-top: 20px; font-size: 14px; color: #475569;">
      <strong>Em seguida:</strong> Abra o documento e compare o que lembrou com o original. Anote os pontos esquecidos!
    </div>

    <div class="footer">
      Revisão Ativa por E-mail · Rodada {cycle}
    </div>
  </div>
</body>
</html>"""

    else:
        # Lembrete Regular de Leitura (RF9)
        subject = f"[Estudo] {doc_name} · {block_label}"

        link_text_plain = f"\nLink do documento: {link}\n" if link else ""
        link_html = f'<p style="margin: 16px 0;"><a href="{link}" style="background-color: #2563eb; color: #ffffff; padding: 10px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Abrir Documento</a></p>' if link else ""

        if prev_block_label:
            opening_recall_plain = f"Antes de abrir o documento:\nO que você lembra do trecho anterior ({prev_block_label})?\nForce a memória por 30 segundos antes de ler o próximo trecho."
            opening_recall_html = f"""<div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; color: #1e3a8a;">
              <strong>🧠 Recuperação Ativa Pré-Leitura:</strong><br>
              Antes de abrir o documento: o que você lembra do trecho anterior (<strong>{prev_block_label}</strong>)? Tente evocar os conceitos de memória por 30 segundos.
            </div>"""
        else:
            opening_recall_plain = f"Antes de abrir o documento:\nO que você já sabe ou associa ao tema de '{doc_name}'?\nTente formular 1 ou 2 conceitos básicos de memória."
            opening_recall_html = f"""<div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; color: #1e3a8a;">
              <strong>🧠 Preparação Mental:</strong><br>
              Antes de iniciar o bloco 1: o que você já sabe ou associa ao tema de <strong>{doc_name}</strong>?
            </div>"""

        plain_text = f"""======================================================
LEMBRETE DE LEITURA · REVISÃO ATIVA
======================================================

Documento: {doc_name}
Leitura Agora: {block_label} (bloco {block_num} de {total_blocks}, aprox. {est_minutes} min)
Progresso: {progress_pct:.0f}% concluído · Rodada {cycle}
{link_text_plain}
------------------------------------------------------
1. RECUPERAÇÃO ATIVA (ANTES DE LER):
------------------------------------------------------
{opening_recall_plain}

------------------------------------------------------
2. AÇÃO DE LEITURA:
------------------------------------------------------
Leia atentamente: {doc_name}, {block_label}.
Tempo estimado: ~{est_minutes} minutos.

------------------------------------------------------
3. PERGUNTAS DE FIXAÇÃO (RESPONDA DE MEMÓRIA APÓS LER):
------------------------------------------------------
1. Qual é a tese, resultado ou conclusão principal desse trecho?
2. Como você explicaria o conceito central em termos simples com suas próprias palavras?
3. Se você fosse elaborar uma pergunta de prova sobre essa parte, qual seria?

------------------------------------------------------
Progresso: Bloco {block_num} de {total_blocks} ({progress_pct:.0f}%)
Bons estudos!
"""

        html_text = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .card {{ background: #ffffff; max-width: 600px; margin: 0 auto; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); padding: 28px; }}
    .badge {{ background-color: #dbeafe; color: #1d4ed8; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 9999px; display: inline-block; }}
    h1 {{ font-size: 20px; color: #0f172a; margin: 16px 0 8px 0; }}
    .subtitle {{ color: #64748b; font-size: 14px; margin-bottom: 20px; }}
    .progress-bar {{ background: #e2e8f0; border-radius: 9999px; height: 8px; width: 100%; margin: 8px 0 16px 0; overflow: hidden; }}
    .progress-fill {{ background: #3b82f6; height: 100%; border-radius: 9999px; width: {progress_pct:.0f}%; }}
    .read-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 14px 18px; border-radius: 8px; margin: 18px 0; }}
    ol {{ padding-left: 20px; line-height: 1.6; color: #334155; }}
    li {{ margin-bottom: 8px; }}
    .footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #f1f5f9; font-size: 12px; color: #94a3b8; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Leitura Recomendada</span>
    <h1>{doc_name}</h1>
    <div class="subtitle">{block_label} · Bloco {block_num} de {total_blocks} (~{est_minutes} min)</div>

    <div class="progress-bar">
      <div class="progress-fill"></div>
    </div>

    {opening_recall_html}

    <div class="read-box">
      <strong style="color: #0f172a;">📖 Ação de Estudo:</strong>
      <p style="margin: 6px 0 0 0; color: #475569;">Leia <strong>{doc_name}</strong>, <strong>{block_label}</strong>. Leitura focada de cerca de {est_minutes} minutos.</p>
    </div>

    {link_html}

    <h3 style="font-size: 15px; color: #0f172a; margin-top: 22px;">Fixação Pós-Leitura (Responda de memória sem olhar):</h3>
    <ol>
      <li>Qual é a conclusão, ideia central ou resultado principal deste trecho?</li>
      <li>Como você explicaria esse conceito com suas próprias palavras para um colega?</li>
      <li>Que pergunta de prova teórica ou prática você formularia sobre este bloco?</li>
    </ol>

    <div class="footer">
      Progresso no documento: {progress_pct:.0f}% · Rodada {cycle} · Revisão Ativa
    </div>
  </div>
</body>
</html>"""

    return subject, plain_text, html_text


def send_email_smtp(subject: str, plain_content: str, html_content: str) -> None:
    """Envia o e-mail via servidor SMTP com suporte a STARTTLS / SSL."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port_raw = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    email_to = os.environ.get("EMAIL_TO", smtp_user)
    email_from = os.environ.get("EMAIL_FROM", smtp_user)

    missing = []
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_user:
        missing.append("SMTP_USER")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")
    if not email_to:
        missing.append("EMAIL_TO")

    if missing:
        raise ValueError(
            f"Configurações SMTP ausentes nas variáveis de ambiente: {', '.join(missing)}. "
            "Defina-as como Secrets no GitHub ou variáveis locais para testar o envio."
        )

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(plain_content)
    msg.add_alternative(html_content, subtype="html")

    print(f"Conectando ao servidor SMTP {smtp_host}:{smtp_port}...")
    if smtp_port == 465:
        # SSL direto
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    else:
        # STARTTLS (porta 587 ou 25)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

    print(f"✅ E-mail enviado com sucesso para {email_to}!")


def print_status(config: dict, state: dict) -> None:
    """Exibe o status atual do estudo no terminal."""
    tz_str = config.get("timezone", "America/Sao_Paulo")
    tz = ZoneInfo(tz_str)
    now = datetime.now(tz)
    active_start = config.get("active_start", 8)
    active_end = config.get("active_end", 22)
    in_window = is_in_active_window(now, active_start, active_end)

    print("\n" + "=" * 60)
    print("📊 STATUS DA REVISÃO ATIVA POR E-MAIL")
    print("=" * 60)
    print(f"Horário Atual ({tz_str}): {now.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Janela de Estudo: {active_start:02d}:00 às {active_end:02d}:00 ({'ATIVO AGORA' if in_window else 'FORA DA JANELA'})")
    print(f"Lembretes Enviados no Total: {state.get('reminder_count', 0)}")
    print(f"Último Envio: {state.get('last_sent_at', 'Nenhum')}")
    print(f"Próximo Envio Agendado: {state.get('next_send_at', 'Não agendado')}")
    print(f"Ciclo Atual: Rodada {state.get('cycle', 1)}")

    docs = config.get("documents", [])
    print("\n📚 Progresso dos Documentos:")
    for idx, doc in enumerate(docs):
        d_name = doc["name"]
        blocks = generate_blocks(doc, config.get("est_minutes_per_block", 5))
        total_b = len(blocks)
        doc_st = state.get("documents", {}).get(d_name, {})
        curr_b = doc_st.get("current_block_index", 0)
        pct = (curr_b / total_b * 100) if total_b > 0 else 100
        current_pointer = " ⬅️ (PRÓXIMO)" if idx == state.get("current_doc_index", 0) else ""
        print(f"  [{idx + 1}] {d_name}: bloco {curr_b} de {total_b} ({pct:.0f}%){current_pointer}")

    history = state.get("history", [])
    print(f"\nHistórico de blocos disponíveis para revisão: {len(history)}")
    print("=" * 60 + "\n")


def execute_cycle(
    config: dict,
    state: dict,
    force: bool = False,
    dry_run: bool = False
) -> bool:
    """
    Executa a verificação e lógica de envio de um lembrete.
    Retorna True se um lembrete foi enviado (ou simulado em dry-run), False caso contrário.
    """
    tz_str = config.get("timezone", "America/Sao_Paulo")
    tz = ZoneInfo(tz_str)
    now = datetime.now(tz)

    active_start = config.get("active_start", 8)
    active_end = config.get("active_end", 22)
    min_interval = config.get("min_interval_min", 60)
    max_interval = config.get("max_interval_min", 120)
    review_every = config.get("review_every", 4)

    # 1. Checagem da Janela de Estudo
    in_window = is_in_active_window(now, active_start, active_end)
    if not in_window and not force:
        print(f"[Info] Fora da janela de estudo ({active_start:02d}:00 às {active_end:02d}:00). Hora atual: {now.strftime('%H:%M')}.")
        # Se next_send_at for nulo ou já tiver passado, agenda para amanhã de manhã
        next_send_raw = state.get("next_send_at")
        needs_reschedule = True
        if next_send_raw:
            try:
                next_send_dt = datetime.fromisoformat(next_send_raw)
                if next_send_dt > now:
                    needs_reschedule = False
            except Exception:
                pass

        if needs_reschedule and not dry_run:
            new_next = calculate_next_send_time(now, min_interval, max_interval, active_start, active_end, tz)
            state["next_send_at"] = new_next.isoformat()
            save_state(state)
            print(f"[Info] Próximo envio reagendado para o início da próxima janela: {new_next.strftime('%d/%m/%Y %H:%M')}.")
        return False

    # 2. Checagem de Horário Agendado (next_send_at)
    next_send_raw = state.get("next_send_at")
    if next_send_raw and not force:
        try:
            next_send_dt = datetime.fromisoformat(next_send_raw)
            if now < next_send_dt:
                print(f"[Info] Ainda não é hora de enviar. Próximo agendado para {next_send_dt.strftime('%d/%m/%Y %H:%M:%S')} (agora: {now.strftime('%H:%M:%S')}).")
                return False
        except Exception as e:
            print(f"[Aviso] Formato de data inválido em next_send_at ({e}). Continuando envio.")

    # 3. Decidir se é Lembrete de Revisão Espaçada (RF10) ou Leitura Regular (RF9)
    reminder_count = state.get("reminder_count", 0)
    history = state.get("history", [])

    is_review_turn = ((reminder_count + 1) % review_every == 0) and (len(history) > 0)

    if is_review_turn:
        # Seleciona o bloco mais antigo com menor número de revisões
        history.sort(key=lambda item: (item.get("review_count", 0), item.get("sent_at", "")))
        review_entry = history[0]

        target_doc_name = review_entry["doc_name"]
        # Encontra config do doc
        doc_cfg = next((d for d in config["documents"] if d["name"] == target_doc_name), {"name": target_doc_name})
        block_info = {
            "label": review_entry.get("block_label", ""),
            "block_index": review_entry.get("block_index", 0),
            "est_minutes": config.get("est_minutes_per_block", 5),
            "link": doc_cfg.get("link", "")
        }
        total_blocks = state["documents"].get(target_doc_name, {}).get("total_blocks", 1)
        cycle = state.get("cycle", 1)

        subject, plain_text, html_text = build_reminder_email(
            is_review=True,
            doc_config=doc_cfg,
            block_info=block_info,
            total_blocks=total_blocks,
            cycle=cycle
        )

        print(f"\n[Ação] Preparando Lembrete de REVISÃO ESPAÇADA (#{reminder_count + 1})")
        print(f"Assunto: {subject}")

    else:
        # Leitura Regular: pega próximo documento e bloco
        doc_idx, doc_cfg, blocks = find_next_reading_document(config, state)
        doc_name = doc_cfg["name"]
        curr_block_idx = state["documents"][doc_name]["current_block_index"]
        block_info = blocks[curr_block_idx]
        total_blocks = len(blocks)
        cycle = state.get("cycle", 1)

        # Label do bloco anterior para a pergunta de abertura de recuperação ativa
        prev_block_label = None
        if curr_block_idx > 0:
            prev_block_label = blocks[curr_block_idx - 1]["label"]
        elif cycle > 1 and len(blocks) > 0:
            prev_block_label = blocks[-1]["label"]

        subject, plain_text, html_text = build_reminder_email(
            is_review=False,
            doc_config=doc_cfg,
            block_info=block_info,
            total_blocks=total_blocks,
            cycle=cycle,
            prev_block_label=prev_block_label
        )

        print(f"\n[Ação] Preparando Lembrete de LEITURA REGULAR (#{reminder_count + 1})")
        print(f"Assunto: {subject}")

    # 4. Envio do E-mail
    if dry_run:
        print("\n--- MODO DRY-RUN: Conteúdo que seria enviado ---")
        print(f"Assunto: {subject}")
        print("Corpo Texto Puro:")
        print(plain_text)
        print("-------------------------------------------------")
        print("[Dry-run] O e-mail NÃO foi enviado e state.json NÃO foi modificado.")
        return True
    else:
        # Envia e-mail real via SMTP
        send_email_smtp(subject, plain_text, html_text)

    # 5. Atualização segura do Estado após envio bem-sucedido
    state["last_sent_at"] = now.isoformat()
    state["reminder_count"] += 1

    if is_review_turn:
        # Incrementa review_count do bloco revisado
        review_entry["review_count"] = review_entry.get("review_count", 0) + 1
        review_entry["last_reviewed_at"] = now.isoformat()
    else:
        # Avança o índice do bloco do documento atual
        doc_name = doc_cfg["name"]
        state["documents"][doc_name]["current_block_index"] += 1
        state["documents"][doc_name]["completed_blocks"] += 1

        # Registra no histórico para futuras revisões espaçadas
        state["history"].append({
            "doc_name": doc_name,
            "block_index": block_info["block_index"],
            "block_label": block_info["label"],
            "sent_at": now.isoformat(),
            "cycle": cycle,
            "review_count": 0
        })

        # Avança o ponteiro de rotação para o próximo documento
        num_docs = len(config["documents"])
        state["current_doc_index"] = (doc_idx + 1) % num_docs

    # 6. Sorteia o próximo horário de envio (60 a 120 minutos)
    next_time = calculate_next_send_time(now, min_interval, max_interval, active_start, active_end, tz)
    state["next_send_at"] = next_time.isoformat()
    save_state(state)
    print(f"📅 Próximo envio sorteado para: {next_time.strftime('%d/%m/%Y %H:%M:%S')}")
    return True


def reset_state(config: dict) -> None:
    """Reinicia o arquivo state.json para as condições iniciais."""
    state = {
        "cycle": 1,
        "current_doc_index": 0,
        "reminder_count": 0,
        "last_sent_at": None,
        "next_send_at": None,
        "documents": {},
        "history": []
    }
    for doc in config.get("documents", []):
        d_name = doc["name"]
        blocks = generate_blocks(doc, config.get("est_minutes_per_block", 5))
        state["documents"][d_name] = {
            "current_block_index": 0,
            "total_blocks": len(blocks),
            "completed_blocks": 0
        }
    save_state(state)
    print("🔄 Estado reiniciado com sucesso!")


def main():
    parser = argparse.ArgumentParser(
        description="Sistema de Revisão Ativa por E-mail (GitHub Actions / Local)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula o envio do e-mail exibindo o conteúdo no console sem disparar SMTP nem salvar o estado."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força o envio imediato, ignorando restrições de horário agendado e janela de estudo."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Exibe o status atual do estudo, documentos e próximo envio agendado."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reinicia o arquivo state.json do zero."
    )
    parser.add_argument(
        "--config",
        default=CONFIG_FILE,
        help="Caminho para o arquivo config.json (padrão: config.json)"
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Erro ao carregar configuração: {e}")
        sys.exit(1)

    if args.reset:
        reset_state(config)
        sys.exit(0)

    state = load_state(STATE_FILE, config)

    if args.status:
        print_status(config, state)
        sys.exit(0)

    try:
        execute_cycle(config, state, force=args.force, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Erro durante a execução: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
