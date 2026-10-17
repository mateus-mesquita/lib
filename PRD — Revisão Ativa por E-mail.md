# PRD — Revisão Ativa por E-mail

Oct 16, 2026 · @mateus

## Resumo e problema

O produto envia por e-mail, ao longo do dia, um lembrete dizendo qual parte de qual dos 4 documentos de estudo ler agora, com pausas aleatórias de 1 a 2 horas, e roda sozinho no GitHub Actions.

Os 4 documentos são longos demais para uma leitura única. O programa não lê nem envia o conteúdo deles: só divide cada documento em blocos de leitura (ex.: 10 páginas), alterna entre os documentos e cobra a leitura na hora certa. Cada lembrete traz também perguntas de recuperação ativa (lembrar antes de reler), que retém mais do que releitura passiva.

## Objetivos, não-objetivos e métricas

**Objetivos**

- Dividir cada um dos 4 documentos em blocos de leitura de 3 a 5 minutos (ex.: 5 a 10 páginas), definidos na configuração.
- Enviar 1 lembrete por vez, com intervalo aleatório de 60 a 120 minutos, só na janela de estudo (padrão: 08h às 22h, fuso de São Paulo).
- Rodar sem computador ligado, sem custo de servidor e sem intervenção diária.
- Incluir em cada lembrete perguntas de recuperação ativa e, periodicamente, um lembrete para rever um bloco já lido.

**Não-objetivos (v1)**

- Ler, extrair ou enviar o conteúdo dos documentos: o lembrete só aponta onde ler.
- Painel web ou aplicativo.
- Confirmar automaticamente que o bloco foi lido.
- Suportar mais de um usuário.

**Métricas de sucesso**

| Métrica | Meta |
| --- | --- |
| Atraso entre horário sorteado e envio real | até 30 min (limite do agendador) |
| Lembretes duplicados ou perdidos por dia | 0 |
| Intervalo entre lembretes consecutivos | entre 60 e 120 min, mais até 30 min de atraso |
| Blocos lidos por dia (autorrelato) | 6 a 10 |
| Ciclo completo dos 4 documentos | prazo definido pelo usuário (ver decisões em aberto) |

## Usuário e cenário de uso

O usuário é um estudante com 4 documentos longos que quer revisá-los de forma ativa e distribuída, sem precisar decidir a cada hora o que ler.

Um dia típico: o primeiro lembrete chega por volta das 08h, os seguintes a cada 1 a 2 horas, e o último antes das 22h, o que dá de 6 a 10 lembretes. Cada um é lido em segundos no celular: diz o que ler, o usuário abre o documento onde ele já está, lê o bloco e tenta responder de memória às perguntas. Fora da janela de estudo nada é enviado.

## Método de estudo

Cada lembrete combina três técnicas: recuperação ativa, intercalação e repetição espaçada.

1. **Recuperação ativa.** O lembrete abre com uma pergunta sobre o bloco anterior daquele documento. O usuário tenta responder antes de começar o bloco novo.
2. **Bloco de leitura.** O lembrete informa o documento, o intervalo (ex.: páginas 21 a 30), a posição (bloco 3 de 12) e o tempo estimado.
3. **Perguntas de fixação.** Depois de ler, 2 a 3 perguntas para responder de memória: ideia central, um conceito com as próprias palavras e uma pergunta que uma prova faria. Como o programa não vê o conteúdo, as perguntas são genéricas.
4. **Intercalação.** Os lembretes alternam entre os 4 documentos (A, B, C, D, A...), em vez de esgotar um por vez.
5. **Revisão espaçada.** A cada 4º lembrete, em vez de bloco novo, o usuário é mandado rever um bloco já indicado, priorizando os mais antigos: escrever de memória o que lembra e só depois conferir no documento.

## Requisitos funcionais

P0 é o mínimo para a v1 funcionar, P1 melhora o estudo e P2 fica para depois.

| ID | Requisito | Prioridade |
| --- | --- | --- |
| RF1 | Ler da configuração a lista dos 4 documentos (nome, total de páginas, tamanho do bloco) | P0 |
| RF2 | Dividir cada documento em blocos sequenciais (ex.: páginas 1–10, 11–20...) | P0 |
| RF3 | Alternar entre os 4 documentos e guardar a posição de cada um | P0 |
| RF4 | Sortear o próximo envio entre 60 e 120 min após o último | P0 |
| RF5 | Enviar apenas dentro da janela configurável (padrão 08h–22h, America/Sao\_Paulo) | P0 |
| RF6 | Enviar o lembrete por e-mail via SMTP, em texto simples e curto | P0 |
| RF7 | Persistir o estado (posições, próximo horário, histórico) entre execuções | P0 |
| RF8 | Reiniciar o ciclo ao terminar todos os blocos, registrando o número da rodada | P0 |
| RF9 | Incluir perguntas de recuperação ativa genéricas em todo lembrete | P0 |
| RF10 | Mandar rever um bloco antigo a cada N lembretes (padrão N = 4) | P1 |
| RF11 | Modo `--dry-run` (imprime sem enviar) e `--force` (ignora horário e janela) | P1 |
| RF12 | Disparo manual pelo GitHub (`workflow_dispatch`) para teste | P1 |
| RF13 | Aceitar blocos nomeados (capítulos, seções) no lugar de intervalos de páginas | P1 |
| RF14 | Incluir no lembrete o link do documento (ex.: Drive, Notion) | P2 |
| RF15 | Resumo diário com o progresso por documento | P2 |
| RF16 | Marcar um bloco como lido, por link ou resposta ao e-mail | P2 |

## Requisitos não funcionais

- **Custo:** zero de infraestrutura. O consumo de minutos do Actions deve caber no plano gratuito (ver riscos).
- **Privacidade:** o conteúdo dos documentos nunca entra no repositório nem no e-mail. O repositório guarda só nomes, tamanhos e posição de leitura. Ainda assim, usar repositório **privado**, para não expor o que você estuda.
- **Credenciais:** usuário e senha SMTP só em GitHub Secrets, nunca no código. Usar senha de aplicativo, não a senha da conta de e-mail.
- **Idempotência:** se duas execuções coincidirem, só uma envia. O workflow usa `concurrency` e o script confere o horário sorteado antes de enviar.
- **Falha segura:** se o envio falhar, o estado não avança e a próxima execução tenta de novo.
- **Simplicidade:** um script Python que usa só a biblioteca padrão (`smtplib`, `json`, `zoneinfo`), sem dependências para instalar e sem banco de dados. O estado é um arquivo JSON versionado no repositório.

## Arquitetura no GitHub Actions

O GitHub Actions não serve para manter um programa rodando o dia todo: cada job tem limite de 6 horas e ficar dormindo entre e-mails consumiria minutos à toa. A arquitetura troca o processo contínuo por execuções curtas e frequentes, que decidem sozinhas se já é hora de enviar.

1. Um agendamento (`cron`) dispara o workflow a cada 30 minutos, só nas horas da janela de estudo.
2. O workflow faz checkout do repositório e inicia o script Python.
3. O script lê `state.json` e compara a hora atual com o campo `next_send_at`.
4. Se ainda não é hora, ou se está fora da janela, o script encerra em poucos segundos.
5. Se é hora, o script escolhe o próximo documento e bloco, monta o lembrete e envia por SMTP.
6. Após o envio, o script sorteia o próximo horário (60 a 120 min à frente) e atualiza `state.json`.
7. O workflow faz commit do `state.json` atualizado no repositório.

**Limites da plataforma que moldam o desenho**

- O agendador do GitHub não é pontual: execuções atrasam, sobretudo em horários de pico. Por isso o intervalo real vai ser de 60 a 120 min mais um atraso de até cerca de 30 min.
- O intervalo mínimo do `cron` é de 5 minutos, mas execuções a cada 30 min já bastam e economizam minutos.
- Em repositórios públicos, o GitHub desativa workflows agendados após 60 dias sem atividade no repositório. Confirmar na documentação do GitHub se os commits automáticos do estado contam como atividade; se não contarem, é preciso um commit manual a cada 2 meses.
- Estimativa de consumo: cerca de 28 execuções por dia, de 1 minuto cada (o GitHub arredonda para cima), perto de 850 minutos por mês. Em repositório privado o plano gratuito inclui 2.000 minutos por mês; confirmar esse valor na documentação do GitHub antes de implantar.

## Repositório, configuração e e-mail

**Estrutura do repositório**

```
.
├── send_reminder.py           # script principal
├── config.json                # documentos, janela, intervalos
├── state.json                 # estado persistido pelo workflow
├── README.md
└── .github/workflows/study.yml
```

Os documentos não ficam no repositório: a configuração só descreve cada um.

**Configuração (`config.json`)**

```json
{
  "documents": [
    { "name": "Documento A", "total": 120, "block_size": 10 },
    { "name": "Documento B", "total": 80,  "block_size": 8 },
    { "name": "Documento C", "total": 200, "block_size": 10 },
    { "name": "Documento D", "total": 60,  "block_size": 6 }
  ]
}
```

| Chave | Padrão | Função |
| --- | --- | --- |
| `documents[].name` | — | nome que aparece no lembrete |
| `documents[].total` | — | total de páginas do documento |
| `documents[].block_size` | — | páginas por bloco de leitura |
| `timezone` | America/Sao\_Paulo | fuso da janela de envio |
| `active_start` / `active_end` | 8 / 22 | horas em que pode enviar |
| `min_interval_min` / `max_interval_min` | 60 / 120 | sorteio do intervalo |
| `review_every` | 4 | frequência dos lembretes de revisão |

Os números do exemplo são ilustrativos; os reais dependem das respostas em "Decisões em aberto".

**Segredos do repositório:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO` (pode ser o mesmo endereço do remetente).

**Anatomia do lembrete**

1. Assunto: `[Estudo] Documento B · páginas 21–30` (ou `· revisão`).
2. Ação: "Leia o Documento B, páginas 21 a 30 (bloco 3 de 12, cerca de 5 min)."
3. Pergunta de abertura: "Antes de abrir: o que você lembra das páginas 11 a 20?"
4. Duas ou três perguntas de fixação para responder de memória depois de ler.
5. Progresso do documento (ex.: 25%).
6. Em lembretes de revisão: "Sem abrir o documento, escreva o que lembra das páginas 1 a 10; depois confira."

## Riscos e mitigações

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Agendador do GitHub atrasa ou pula execuções | Intervalo irregular | Aceitar a imprecisão; o sorteio é por horário, não por contagem de execuções |
| Gmail bloqueia o login SMTP | Nenhum lembrete enviado | Usar senha de aplicativo (exige verificação em duas etapas); alternativa: serviço de e-mail transacional ou notificação push |
| Lembretes caem em spam | Estudo não acontece | Enviar para si mesmo, marcar como "não é spam" uma vez e criar filtro |
| Total de páginas errado na configuração | Blocos que não existem | O script limita o último bloco ao total e avisa no log |
| Lembrete sem contexto (você esquece onde parou) | Perda de tempo procurando a página | Cada lembrete traz o intervalo exato; link do documento como melhoria (RF14) |
| Repositório público por engano | Expõe o que você estuda e seu progresso | README alerta; usar repositório privado |
| Consumo de minutos acima do plano gratuito | Workflow parado | Reduzir a frequência do `cron` ou restringir às horas de estudo |

## Plano de entrega e critérios de aceite

| Fase | Entrega | Critério de aceite |
| --- | --- | --- |
| 1. Núcleo | Script que lê a configuração, calcula os blocos dos 4 documentos e envia 1 lembrete manualmente | `--dry-run` lista os blocos corretos dos 4 documentos; um e-mail real chega com assunto, intervalo e perguntas |
| 2. Agendamento | Estado persistente, janela, intervalo aleatório e workflow no GitHub | Em 1 dia, entre 6 e 10 lembretes, nenhum fora da janela, nenhum duplicado |
| 3. Revisão ativa | Intercalação, revisão a cada 4 lembretes e reinício de ciclo | Os 4 documentos aparecem em sequência alternada; revisões apontam blocos já indicados |
| 4. Melhorias | Blocos nomeados, link do documento, resumo diário, marcar como lido | Lembrete mostra o título do capítulo e abre o documento com um toque |

## Decisões em aberto

- [ ] Quantas páginas tem cada um dos 4 documentos? Se algum não tem páginas (ex.: Notion), os blocos podem ser capítulos listados pelo nome.
- [ ] Quantas páginas por bloco de leitura? Sugestão: 5 a 10, para caber em 3 a 5 minutos.
- [ ] Qual e-mail envia e qual recebe? Podem ser o mesmo. Se for Gmail, a verificação em duas etapas está ativa?
- [ ] A janela de 08h às 22h e o intervalo de 60 a 120 min estão bons?
- [ ] O repositório será privado? (recomendado)
- [ ] Os lembretes devem incluir o link de cada documento (Drive, Notion, outro)?
- [ ] E-mail mesmo, ou prefere notificação no celular (Telegram, ntfy)? Para um lembrete curto, a notificação pode ser mais prática.
- [ ] Prazo desejado para terminar o primeiro ciclo completo?

## Prompt melhorado

Use este texto para pedir a implementação a uma IA ou a um colega. Ele troca o "roda o dia todo" por um desenho que funciona no GitHub Actions e já traz os critérios de aceite.

```markdown
Quero estudar 4 documentos longos com revisão ativa. Construa um programa em Python que me envia, ao longo do dia, só um lembrete por e-mail dizendo qual parte ler, rodando no GitHub Actions. O programa NÃO lê nem envia o conteúdo dos documentos.

## Contexto
- 4 documentos: <nome e número de páginas (ou capítulos) de cada um>.
- Não consigo ler tudo de uma vez; quero blocos de 3 a 5 minutos.
- Objetivo: lembrar do conteúdo, não só reler.

## Comportamento
1. Configuração em `config.json`: lista dos 4 documentos (nome, total de páginas, tamanho do bloco, link opcional).
2. Dividir cada documento em blocos sequenciais (ex.: páginas 1–10, 11–20...).
3. Alternar entre os 4 documentos e guardar a posição de cada um.
4. Enviar 1 lembrete por vez, com intervalo aleatório de 60 a 120 minutos, só entre 08h e 22h (America/Sao_Paulo).
5. Cada lembrete traz: o que ler (documento e intervalo), uma pergunta sobre o bloco anterior e 2 a 3 perguntas genéricas para responder de memória depois da leitura.
6. A cada 4º lembrete, mandar rever um bloco antigo, sem abrir o documento antes.
7. Ao terminar todos os blocos, reiniciar o ciclo.

## Restrições técnicas
- O processo não pode ficar dormindo: o workflow roda a cada 30 min, o script lê `state.json`, envia só se `next_send_at` já passou e sorteia o próximo horário.
- Só biblioteca padrão do Python (`smtplib`, `json`, `zoneinfo`).
- Envio por SMTP; credenciais em GitHub Secrets (senha de aplicativo).
- Repositório privado; `state.json` salvo por commit ao fim de cada execução.
- Flags `--dry-run` e `--force` para testar.

## Entregáveis
`send_reminder.py`, `config.json`, `.github/workflows/study.yml` e um README com o passo a passo de configuração.

## Critério de aceite
Em 1 dia: 6 a 10 lembretes, nenhum fora da janela, nenhum duplicado, os 4 documentos alternados.
```

Para a v1, o mínimo é o prompt acima mais as respostas às decisões em aberto, principalmente número de páginas de cada documento, tamanho do bloco e e-mail de envio.
