# =============================================================================
# MURILO AGENT — main.py
# =============================================================================
# RESPONSABILIDADE DESTE ARQUIVO:
#   É o ponto de entrada do bot. Ele faz 3 coisas em paralelo:
#   1. Escuta mensagens de texto do Telegram e passa para o agente LangChain
#   2. Escuta cliques nos botões inline (✅/⬜) e atualiza as tarefas
#   3. Roda um agendador que envia mensagens automáticas nos horários certos
#
# FLUXO GERAL:
#   Usuário escreve no Telegram
#     → handle_message() recebe o texto
#       → processar_mensagem() (agente.py) decide o que fazer
#         → agente chama tools.py se precisar
#           → resposta volta pro usuário
#
# ARQUIVOS DO PROJETO:
#   main.py    → este arquivo (entrada do bot + agendador)
#   agente.py  → cérebro com LangChain + Groq (entende linguagem natural)
#   tools.py   → ações que o agente pode executar (add, marcar, status, etc.)
#   .env       → chaves de API (nunca sobe pro GitHub)
# =============================================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# Update          → representa uma atualização recebida do Telegram (mensagem, clique, etc.)
# InlineKeyboardButton → um botão dentro de uma mensagem
# InlineKeyboardMarkup → o conjunto de botões (teclado inline)

from telegram.ext import (
    ApplicationBuilder,     # Constrói a aplicação do bot
    MessageHandler,         # Lida com mensagens de texto
    CallbackQueryHandler,   # Lida com cliques em botões inline
    filters,                # Filtra quais mensagens cada handler processa
    ContextTypes            # Tipagem para o contexto da aplicação
)

from agente import processar_mensagem
# Importa a função principal do agente LangChain
# Ela recebe texto em linguagem natural e decide o que fazer

from tools import carregar, salvar, BLOCOS
# carregar() → lê os dados do arquivo murilo_data.json
# salvar()   → salva os dados no arquivo murilo_data.json
# BLOCOS     → dicionário com os blocos do dia (manhã, almoço, etc.)

from dotenv import load_dotenv
# Carrega as variáveis do arquivo .env (BOT_TOKEN, GROQ_API_KEY)

import os, datetime

load_dotenv()  # Lê o .env e disponibiliza as variáveis com os.getenv()


# =============================================================================
# FUSO HORÁRIO — BRASÍLIA (UTC-3)
# =============================================================================
# O servidor Railway roda em UTC. Para pegar o horário correto de Brasília,
# subtraímos 3 horas do UTC em todas as comparações de tempo.

FUSO = datetime.timedelta(hours=-3)

def agora_br():
    """Retorna o datetime atual no horário de Brasília (UTC-3)."""
    return datetime.datetime.utcnow() + FUSO

def hoje_br():
    """Retorna a data de hoje no formato 'YYYY-MM-DD' (horário de Brasília)."""
    return agora_br().date().isoformat()


# =============================================================================
# TECLADO INLINE (BOTÕES ✅/⬜)
# =============================================================================

def construir_teclado(chaves, tarefas):
    """
    Cria um teclado inline com botões para cada tarefa passada em 'chaves'.

    Como funciona:
    - Para cada chave de tarefa, cria um botão com ✅ (feita) ou ⬜ (pendente)
    - O botão tem callback_data='done:chave' — isso é o que o bot recebe
      quando o usuário clica no botão
    - Um botão extra no final mostra a pontuação atual

    Parâmetros:
    - chaves:  lista de chaves das tarefas a exibir (ex: ['exercicio', 'curso'])
    - tarefas: dicionário completo de tarefas do dia (lido do JSON)

    Retorna:
    - InlineKeyboardMarkup: objeto que o Telegram entende como teclado de botões
    """
    botoes = []
    for k in chaves:
        t = tarefas.get(k)
        if not t:
            continue  # Pula se a chave não existir nas tarefas
        marca = "✅" if t.get("done") else "⬜"
        botoes.append([InlineKeyboardButton(
            f"{marca} {t['name']} (+{t['points']} pts)",
            callback_data=f"done:{k}"  # Identificador enviado ao clicar
        )])

    # Botão extra para ver pontuação atual
    botoes.append([InlineKeyboardButton("📊 Ver pontuação", callback_data="status")])

    return InlineKeyboardMarkup(botoes)


# =============================================================================
# HANDLER DE MENSAGENS DE TEXTO
# =============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Chamado automaticamente toda vez que o usuário envia uma mensagem de texto.

    O que faz:
    1. Extrai o texto e o chat_id da mensagem recebida
    2. Salva o chat_id no JSON (necessário para o agendador enviar mensagens)
    3. Mostra "digitando..." enquanto o agente processa (feedback visual)
    4. Passa o texto para o agente LangChain (processar_mensagem)
    5. Envia a resposta de volta para o usuário

    O agente LangChain (agente.py) interpreta a mensagem em linguagem natural
    e decide sozinho qual ferramenta de tools.py usar.
    Ex: "fiz o exercício" → agente chama marcar_tarefa("exercicio")
    """
    texto   = update.message.text          # Texto que o usuário digitou
    chat_id = update.effective_chat.id     # ID único do chat (necessário para enviar mensagens)

    # Salva o chat_id no arquivo de dados para o agendador poder usar
    dados = carregar()
    if dados.get("chat_id") is None:
        dados["chat_id"] = chat_id
        salvar(dados)

    # Mostra animação de "digitando..." enquanto o agente pensa
    # Isso dá feedback visual ao usuário que algo está acontecendo
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Passa o texto para o agente LangChain processar e retorna a resposta
    resposta = processar_mensagem(texto)

    # Envia a resposta de volta para o usuário
    await update.message.reply_text(resposta)


# =============================================================================
# HANDLER DE CLIQUE EM BOTÃO INLINE
# =============================================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Chamado automaticamente quando o usuário clica em um botão inline (✅/⬜).

    O que faz:
    1. Recebe o callback_data do botão clicado (ex: 'done:exercicio')
    2. Identifica qual tarefa foi clicada
    3. Faz o toggle: se estava feita → desmarca, se estava pendente → marca
    4. Salva os dados atualizados
    5. Atualiza os botões da mensagem original para refletir o novo estado
    6. Envia uma confirmação breve (+X pts! ou Desmarcado)

    Por que editar a mensagem em vez de enviar uma nova?
    Porque atualizar o botão na mesma mensagem é mais limpo e não polui o chat.
    """
    query   = update.callback_query        # Objeto com os dados do clique
    chat_id = query.message.chat_id        # ID do chat onde o clique ocorreu
    cb_data = query.data                   # Dado do botão (ex: 'done:exercicio')

    await query.answer()  # Obrigatório: remove o loading/spinner do botão clicado

    dados   = carregar()
    tarefas = dados.get("tarefas", {})

    # ── Clique em botão de tarefa ──────────────────────────────────────────────
    if cb_data.startswith("done:"):
        chave = cb_data.split(":", 1)[1]   # Extrai a chave (ex: 'exercicio')

        if chave in tarefas:
            t = tarefas[chave]

            # Toggle: inverte o estado done (True → False, False → True)
            t["done"] = not t["done"]
            salvar(dados)

            # Descobre quais chaves estavam no teclado desta mensagem específica
            # (cada mensagem de bloco tem chaves diferentes)
            chaves_atuais = [
                btn.callback_data.split(":", 1)[1]
                for row in query.message.reply_markup.inline_keyboard
                for btn in row
                if btn.callback_data and btn.callback_data.startswith("done:")
            ]

            # Reconstrói o teclado com o novo estado (✅ ou ⬜ atualizado)
            novo_teclado = construir_teclado(chaves_atuais, tarefas)

            # Edita a mensagem original para mostrar os botões atualizados
            await query.edit_message_reply_markup(reply_markup=novo_teclado)

            # Envia confirmação breve
            if t["done"]:
                await context.bot.send_message(chat_id, f"🎉 +{t['points']} pts!")
            else:
                await context.bot.send_message(chat_id, "↩️ Desmarcado.")

    # ── Clique no botão "Ver pontuação" ───────────────────────────────────────
    elif cb_data == "status":
        pts     = sum(t["points"] for t in tarefas.values() if t.get("done"))
        pts_max = sum(t["points"] for t in tarefas.values())
        pct     = int(pts / pts_max * 100) if pts_max else 0
        barra   = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        await context.bot.send_message(
            chat_id,
            f"📊 *{pts}/{pts_max} pts hoje*\n[{barra}] {pct}%",
            parse_mode="Markdown"
        )


# =============================================================================
# AGENDADOR — MENSAGENS AUTOMÁTICAS NOS HORÁRIOS CERTOS
# =============================================================================

# Tabela de horários: (hora, minuto, identificador_do_bloco)
# Todos os horários são em Brasília (UTC-3)
HORARIOS = [
    (7,  30, "briefing"),      # Briefing completo com todos os blocos do dia
    (12,  0, "almoco"),        # Lembrete do bloco do almoço
    (18,  0, "entretempo"),    # Lembrete do intervalo entre trabalho e faculdade
    (19,  0, "faculdade"),     # Lembrete do bloco da faculdade
    (23,  0, "resumo"),        # Resumo de pontos do final do dia
]

# Textos das mensagens automáticas para cada bloco
MSGS = {
    "almoco":     "⏰ *12h — Almoço!*\n\nDuas missões agora:\n🥗 Almoço de verdade\n🇬🇧 Inglês por 20 min",
    "entretempo": "⏰ *18h — Intervalo!*\n\nAntes da faculdade:\n🎧 Inglês sem legenda\n😴 Descansa de verdade",
    "faculdade":  "🎓 *19h — Faculdade!*\n\nSuas tarefas de hoje 👇",
    "resumo":     "🌙 *Resumo do dia!*\n\nComo foi? Digite /status para ver os pontos finais.",
}

async def enviar_notificacao(context: ContextTypes.DEFAULT_TYPE):
    """
    Função chamada pelo JobQueue a cada 60 segundos.

    O que faz:
    1. Pega o horário atual em Brasília (UTC-3)
    2. Verifica se é hora de enviar alguma das mensagens agendadas
    3. Usa uma chave única (data + hora + slug) para garantir que cada
       mensagem seja enviada apenas UMA VEZ por dia
    4. Para o briefing: envia mensagem introdutória + um bloco por mensagem
    5. Para outros blocos: envia a mensagem com botões das tarefas do bloco
    6. Marca o envio como feito para não repetir

    Por que a cada 60 segundos e não exatamente no horário?
    O JobQueue não garante execução exata no segundo certo,
    então verificamos frequentemente e usamos a chave única para evitar duplicatas.
    """
    agora   = agora_br()
    hoje    = agora.date().isoformat()
    h, m    = agora.hour, agora.minute
    dados   = carregar()
    chat_id = dados.get("chat_id")

    # Só executa se o usuário já tiver ativado o bot (mandado pelo menos 1 mensagem)
    if not chat_id:
        return

    enviados = dados.get("enviados", [])

    for hora_agend, min_agend, slug in HORARIOS:
        # Chave única para este envio específico — garante que não repita no mesmo dia
        chave = f"{hoje}-{hora_agend}:{min_agend:02d}-{slug}"

        # Condições para enviar:
        # 1. É a hora certa (hora e minuto batem)
        # 2. Esta mensagem ainda não foi enviada hoje
        if h == hora_agend and m == min_agend and chave not in enviados:

            if slug == "briefing":
                # ── Briefing das 7h30: mensagem introdutória + blocos com botões ──
                tarefas = dados.get("tarefas", {})
                pts_max = sum(t["points"] for t in tarefas.values())

                # Mensagem principal do briefing
                await context.bot.send_message(
                    chat_id,
                    f"🌅 *Bom dia, Murilo!* Meta de hoje: *{pts_max} pts*\n\n"
                    "Escreve o que fez e eu registro. Ou usa os botões abaixo 👇\n"
                    "Exemplos: 'fiz o exercício', 'já almocei', 'usei 20 min de instagram'",
                    parse_mode="Markdown"
                )

                # Envia um bloco por mensagem, cada um com seus botões
                for bloco, info in BLOCOS.items():
                    chaves = [k for k, t in tarefas.items() if t.get("bloco") == bloco]
                    if chaves:  # Só envia se o bloco tiver tarefas
                        teclado = construir_teclado(chaves, tarefas)
                        await context.bot.send_message(
                            chat_id,
                            f"*{info['titulo']}*",
                            parse_mode="Markdown",
                            reply_markup=teclado
                        )

            elif slug == "resumo":
                # ── Resumo das 23h: pontuação final do dia ──
                tarefas = dados.get("tarefas", {})
                pts     = sum(t["points"] for t in tarefas.values() if t.get("done"))
                pts_max = sum(t["points"] for t in tarefas.values())
                pct     = int(pts / pts_max * 100) if pts_max else 0

                if pct >= 80:
                    emoji_final = "🏆 Arrasou!"
                elif pct >= 50:
                    emoji_final = "💪 Bom esforço!"
                else:
                    emoji_final = "📈 Amanhã é uma nova chance."

                await context.bot.send_message(
                    chat_id,
                    f"🌙 *Resumo do dia!*\n\n"
                    f"Pontuação final: *{pts}/{pts_max} pts* ({pct}%)\n\n"
                    f"{emoji_final}",
                    parse_mode="Markdown"
                )

            else:
                # ── Outros blocos (almoço, entretempo, faculdade) ──
                tarefas = dados.get("tarefas", {})
                # Filtra apenas as tarefas do bloco atual
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == slug]
                msg     = MSGS.get(slug, "")

                if chaves:
                    # Envia mensagem com botões das tarefas do bloco
                    teclado = construir_teclado(chaves, tarefas)
                    await context.bot.send_message(
                        chat_id, msg,
                        parse_mode="Markdown",
                        reply_markup=teclado
                    )
                else:
                    # Bloco sem tarefas (ex: faculdade sem /add ainda)
                    await context.bot.send_message(
                        chat_id,
                        msg + "\n\n_(Nenhuma tarefa adicionada. Diga 'adiciona tarefa X')_",
                        parse_mode="Markdown"
                    )

            # Marca este envio como feito para não repetir hoje
            enviados.append(chave)
            dados["enviados"] = enviados
            salvar(dados)


# =============================================================================
# INICIALIZAÇÃO DO BOT
# =============================================================================

def main():
    """
    Ponto de entrada da aplicação.

    O que faz:
    1. Lê o token do bot do arquivo .env
    2. Cria a aplicação com python-telegram-bot
    3. Registra os handlers (quem processa o quê)
    4. Configura o agendador para rodar a cada 60 segundos
    5. Inicia o polling — fica perguntando ao Telegram se há mensagens novas

    Handlers registrados:
    - MessageHandler → processa mensagens de texto → handle_message()
    - CallbackQueryHandler → processa cliques em botões → handle_callback()

    JobQueue:
    - run_repeating() → roda enviar_notificacao() a cada 60 segundos
    - first=10 → começa 10 segundos após o bot iniciar
    """
    token = os.getenv("BOT_TOKEN")  # Lê o token do .env

    # Constrói a aplicação do bot com o token
    app = ApplicationBuilder().token(token).build()

    # Handler para mensagens de texto (qualquer texto que não seja comando /)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Handler para cliques em botões inline (✅/⬜)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Agendador: chama enviar_notificacao() a cada 60 segundos
    # interval=60 → intervalo em segundos entre cada execução
    # first=10    → aguarda 10 segundos antes da primeira execução
    app.job_queue.run_repeating(enviar_notificacao, interval=60, first=10)

    print("🤖 Murilo Agent rodando! (Ctrl+C para parar)")

    # Inicia o polling: fica em loop perguntando ao Telegram se há updates novos
    # drop_pending_updates=True → ignora mensagens enviadas enquanto o bot estava offline
    app.run_polling(drop_pending_updates=True)


# Garante que main() só rode quando este arquivo for executado diretamente
# (não quando for importado por outro arquivo)
if __name__ == "__main__":
    main()
