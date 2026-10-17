# 📚 Revisão Ativa por E-mail

Sistema automatizado de lembretes periódicos de estudo que distribui a leitura de **4 documentos longos** ao longo do dia, utilizando **recuperação ativa (active recall)**, **intercalação (interleaving)** e **repetição espaçada (spaced repetition)**.

O programa roda 100% no **GitHub Actions** sem necessidade de computador ligado, sem custo de servidor, sem banco de dados e utilizando exclusivamente a biblioteca padrão do Python (`smtplib`, `json`, `zoneinfo`).

---

## 🎯 Como Funciona o Método de Estudo

1. **Blocos Curtos de Leitura:** Cada documento é dividido em blocos de 3 a 5 minutos (ex.: 5 a 10 páginas ou seções/capítulos).
2. **Intercalação:** Em vez de ler um documento inteiro de uma vez, os lembretes alternam entre os 4 documentos sequencialmente (`Doc A ➡️ Doc B ➡️ Doc C ➡️ Doc D ➡️ Doc A...`).
3. **Recuperação Ativa Pré-Leitura:** Todo lembrete regular inicia com uma pergunta sobre o bloco anterior lido daquele documento, forçando você a resgatar o conteúdo da memória antes de abrir o novo trecho.
4. **Fixação Pós-Leitura:** Ao final da leitura, 3 perguntas genéricas de fixação devem ser respondidas de cabeça (ideia central, explicação com as próprias palavras e formulação de questão de prova).
5. **Repetição Espaçada:** A cada **4º lembrete**, o sistema não avança para um bloco novo; ele envia um **Lembrete de Revisão Espaçada**, mandando você escrever de memória tudo o que lembra de um bloco antigo já lido antes de conferir no material.
6. **Reinício de Ciclo:** Ao concluir todos os blocos de todos os documentos, a rodada (`cycle`) avança automaticamente e o ciclo recomeça para fixação a longo prazo.

---

## 🗂️ Estrutura do Repositório

```text
.
├── send_reminder.py           # Script principal (lógica de blocos, rotação, SMTP e estado)
├── config.json                # Configuração dos documentos, janelas e intervalos
├── state.json                 # Estado persistido automaticamente a cada execução
├── tests/
│   └── test_reminder.py       # Suíte de testes unitários com unittest
├── .github/
│   └── workflows/
│       └── study.yml          # Workflow do GitHub Actions (cron a cada 30 min)
└── README.md                  # Este guia completo de configuração
```

---

## ⚙️ Configuração dos Documentos (`config.json`)

Edite o arquivo `config.json` para definir os seus 4 materiais de estudo e suas preferências:

```json
{
  "documents": [
    {
      "name": "Probabilidade e Variáveis Aleatórias",
      "total": 120,
      "block_size": 10,
      "link": "https://drive.google.com/..."
    },
    {
      "name": "Inferência Estatística e Estimação",
      "total": 80,
      "block_size": 8,
      "link": "https://notion.so/..."
    },
    {
      "name": "Modelos de Regressão e ANOVA",
      "chapters": [
        "Capítulo 1: Regressão Linear Simples",
        "Capítulo 2: Diagnóstico de Resíduos",
        "Capítulo 3: ANOVA de Um Fator"
      ],
      "link": ""
    },
    {
      "name": "Estatística Não-Paramétrica e Testes",
      "total": 60,
      "block_size": 6,
      "link": ""
    }
  ],
  "timezone": "America/Sao_Paulo",
  "active_start": 8,
  "active_end": 22,
  "min_interval_min": 60,
  "max_interval_min": 120,
  "review_every": 4,
  "est_minutes_per_block": 5
}
```

### Parâmetros Suportados:

| Chave | Padrão | Descrição |
| --- | --- | --- |
| `documents[].name` | — | Nome do documento exibido no assunto e corpo do e-mail |
| `documents[].total` | — | Total de páginas do documento (para divisão automática) |
| `documents[].block_size` | 10 | Quantidade de páginas lidas por lembrete |
| `documents[].start_page` | 1 | Página inicial (opcional, útil se o conteúdo começar na página 15, por exemplo) |
| `documents[].chapters` | — | Lista de capítulos/seções nomeadas (alternativa a páginas, ideal para Notion ou PDFs sem páginas) |
| `documents[].link` | `""` | Link direto para o documento no Drive, Notion, web, etc. (opcional) |
| `timezone` | `America/Sao_Paulo` | Fuso horário para controle da janela de estudo |
| `active_start` / `active_end` | 8 / 22 | Horário em que os lembretes são permitidos (08:00 às 22:00) |
| `min_interval_min` / `max_interval_min` | 60 / 120 | Intervalo aleatório sorteado entre lembretes consecutivos |
| `review_every` | 4 | Frequência da revisão espaçada (a cada N lembretes enviados) |
| `est_minutes_per_block` | 5 | Tempo estimado sugerido para a leitura |

---

## 🚀 Instalação e Configuração no GitHub Actions

### 1. Criar Repositório Privado
Por privacidade e segurança dos seus dados de estudo, mantenha este repositório como **Privado** no GitHub.

### 2. Habilitar Permissões de Escrita no Workflow
Para que o bot do GitHub Actions consiga atualizar e salvar o arquivo `state.json` automaticamente:
1. No seu repositório no GitHub, acesse: **Settings** > **Actions** > **General**.
2. Role até a seção **Workflow permissions**.
3. Selecione a opção **Read and write permissions**.
4. Clique em **Save**.

### 3. Configurar os Segredos do Repositório (GitHub Secrets)
Acesse: **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.

Cadastre as seguintes chaves:

| Secret | Exemplo / Descrição |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` (ou `smtp.office365.com` para Outlook) |
| `SMTP_PORT` | `587` (STARTTLS padrão) ou `465` (SSL) |
| `SMTP_USER` | Seu endereço de e-mail remetente (ex.: `seu.email@gmail.com`) |
| `SMTP_PASSWORD` | **Senha de Aplicativo** gerada na sua conta de e-mail |
| `EMAIL_TO` | E-mail onde você deseja receber os lembretes (pode ser o mesmo que `SMTP_USER`) |
| `EMAIL_FROM` | Remetente opcional (se omitido, usa `SMTP_USER`) |

#### 🔑 Como Gerar uma Senha de Aplicativo no Gmail:
1. Acesse sua Conta Google: [myaccount.google.com](https://myaccount.google.com/).
2. Vá em **Segurança** e confirme que a **Verificação em duas etapas** está ativada.
3. Na barra de pesquisa no topo, digite **Senhas de app**.
4. Crie uma nova senha de aplicativo chamada `Estudo Actions`.
5. Copie a senha de 16 letras gerada e cole no secret `SMTP_PASSWORD`.

---

## 💻 Uso e Testes Locais

Você pode executar o script no seu terminal local a qualquer momento:

```bash
# 1. Ver resumo do status atual (progresso dos documentos e próximo agendamento):
python send_reminder.py --status

# 2. Simular um envio sem disparar e-mail e sem alterar o estado (Dry-Run):
python send_reminder.py --dry-run --force

# 3. Forçar o envio real imediatamente (ignora janela e horário agendado):
# (Necessita das variáveis de ambiente SMTP configuradas localmente)
python send_reminder.py --force

# 4. Reiniciar o estado do zero (começar ciclo 1 novamente):
python send_reminder.py --reset

# 5. Executar os testes unitários automatizados:
python -m unittest discover tests
```

---

## ⚡ Disparo Manual pelo GitHub Actions

Você não precisa esperar o agendador automático para testar:
1. Vá na aba **Actions** do seu repositório no GitHub.
2. Selecione o workflow **Revisão Ativa por E-mail**.
3. Clique em **Run workflow**.
4. Marque a opção `force` (para enviar imediatamente) ou `dry_run` (para simular nos logs da execução).
5. Clique em **Run workflow**.

---

## 🛡️ Riscos e Boas Práticas

- **Consumo de minutos no GitHub Actions:** O workflow roda por cerca de 15 a 30 segundos a cada 30 minutos apenas dentro da janela de estudo (cerca de 28 a 30 execuções por dia). Isso consome aproximadamente 850 a 900 minutos por mês, muito abaixo do limite gratuito de **2.000 minutos/mês** do GitHub em repositórios privados.
- **Idempotência e Prevenção de Concorrência:** O workflow utiliza `concurrency: cancel-in-progress: false` para garantir que duas execuções simultâneas nunca ocorram ao mesmo tempo.
- **Falha Segura:** Caso o servidor SMTP apresente instabilidade ou falha de conexão, o estado **não avança**, garantindo que nenhum bloco seja pulado ou perdido.
- **Filtro Anti-Spam:** Ao receber o primeiro e-mail, adicione o remetente aos seus contatos e, se necessário, marque "Nunca enviar para Spam" no seu provedor de e-mail.
