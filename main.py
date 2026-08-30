# =============================================================================
# MURILO AGENT — main.py
# =============================================================================
# Ponto de entrada do bot. Faz 3 coisas em paralelo:
#   1. Escuta mensagens de texto → agente LangChain
#   2. Escuta cliques nos botões inline (✅/⬜) → atualiza tarefas
#   3. Agendador → mensagens automáticas nos horários certos
# =============================================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from agente import processar_mensagem
from tools import (
    carregar, salvar, BLOCOS, BLOCOS_SABADO, BLOCOS_DOMINGO, AULAS,
    inicializar_dia, get_aula_hoje, get_info_exercicio, sortear_tema,
    get_blocos_do_dia, agora_br, hoje_br, dia_semana,
)
from dotenv import load_dotenv
import os, datetime

load_dotenv()

# =============================================================================
# HORÁRIOS DO AGENDADOR (Brasília UTC-3)
# =============================================================================
# (hora, minuto, slug)

HORARIOS = [
    (7,  0,  "rotina"),       # Rotina matinal — meditação, banho, dentes, creme
    (7,  30, "lista_dia"),    # Lista simples com todas as tarefas do dia
    (12, 0,  "almoco"),       # Lembrete do almoço
    (12, 45, "pos_almoco"),   # Pós-almoço — dentes + inglês com tema
    (17, 55, "entretempo"),   # Intervalo das 18h — inglês + aula do dia
    (19, 0,  "faculdade"),    # Entrada na faculdade (ou exercício às quartas)
    (21, 30, "checkin"),      # Check-in noturno — reflexão do dia
    (22, 30, "rezar"),        # Lembrete para rezar antes de dormir
    (23, 0,  "resumo"),       # Pontuação final do dia
]

# =============================================================================
# HORÁRIOS DE FIM DE SEMANA
# =============================================================================

HORARIOS_SABADO = [
    (10, 0,  "rotina"),
    (10, 30, "lista_dia"),
    (12, 0,  "estudo_sab"),
    (17, 30, "ingles_sab"),
    (19, 0,  "organizacao"),
    (21, 30, "checkin"),
    (22, 30, "rezar"),
    (23, 0,  "resumo"),
]

HORARIOS_DOMINGO = [
    (10, 0,  "rotina"),
    (10, 30, "lista_dia"),
    (15, 30, "treino_dom"),
    (21, 30, "checkin"),
    (22, 30, "rezar"),
    (23, 0,  "resumo"),
]


def get_horarios_do_dia():
    """Retorna a lista de horários correta pro dia da semana."""
    d = dia_semana()
    if d == 5:
        return HORARIOS_SABADO
    if d == 6:
        return HORARIOS_DOMINGO
    return HORARIOS


# =============================================================================
# TECLADO INLINE (BOTÕES ✅/⬜)
# =============================================================================

def construir_teclado(chaves, tarefas):
    botoes = []
    for k in chaves:
        t = tarefas.get(k)
        if not t or t.get("cancelado"):
            continue
        marca = "✅" if t.get("done") else "⬜"
        botoes.append([InlineKeyboardButton(
            f"{marca} {t['name']} (+{t['points']} pts)",
            callback_data=f"done:{k}"
        )])
    botoes.append([InlineKeyboardButton("📊 Ver pontuação", callback_data="status")])
    return InlineKeyboardMarkup(botoes)


# =============================================================================
# HELPERS DE MENSAGENS
# =============================================================================

def msg_rotina():
    dia_nomes = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    dia = dia_nomes[dia_semana()]
    return (
        f"🌅 *Bom dia! {dia}* — Começa com o pé direito:\n\n"
        "☑️ Meditar (5–10 min)\n"
        "☑️ Tomar banho\n"
        "☑️ Escovar os dentes\n"
        "☑️ Passar creme\n\n"
        "_Tá na sequência. Bora!_ 💪"
    )


def msg_almoco():
    return (
        "⏰ *12h — Almoço!*\n\n"
        "🥗 Almoço de verdade\n"
        "🦷 Dentes após almoço\n"
        "🍎 Lanche saudável se der"
    )


def msg_pos_almoco(dados):
    tema = sortear_tema(dados)
    return (
        f"🇬🇧 *12h45 — Inglês agora!*\n\n"
        f"Tema sorteado: *\"{tema}\"*\n"
        f"Fala sobre isso com a IA por 20 min 🎯\n\n"
        f"_(dificuldade atual: {dados.get('config_ingles', {}).get('dificuldade', 'medio')})_"
    )


def msg_entretempo(dados):
    aula = get_aula_hoje()
    tema = sortear_tema(dados)
    d    = dia_semana()

    if d == 2:  # quarta — sem aula, exercício
        return (
            "⏰ *18h — Intervalo!*\n\n"
            "🎧 Inglês — podcast no caminho\n"
            f"Tema: *\"{tema}\"*\n\n"
            "🏃 *Hoje é dia de exercício à noite!*\n"
            "_Sem faculdade — aproveita!_"
        )

    if aula:
        return (
            f"⏰ *18h — Intervalo!*\n\n"
            "🎧 Inglês — podcast no caminho\n"
            f"Tema: *\"{tema}\"*\n\n"
            f"📚 Hoje: {aula['nome']} — {aula['sala']}"
        )

    return (
        "⏰ *18h — Intervalo!*\n\n"
        "🎧 Inglês — podcast ou música sem legenda PT\n"
        f"Tema: *\"{tema}\"*\n\n"
        "😴 Descansa um pouco antes da noite"
    )


def msg_faculdade():
    d    = dia_semana()
    aula = get_aula_hoje()

    if d == 2:  # quarta
        return "🏃 *Hora do exercício!* Sem aula hoje — bora treinar 💪"

    if aula:
        return f"🎓 *19h — {aula['nome']}*\n{aula['sala']}\n\nBoa aula, Murilo! 📚"

    if d >= 5:  # fds
        return "🌙 *Boa noite!* Sem aula hoje. Aproveita bem o descanso 😴"

    return "🎓 *19h — Faculdade!*\nChegou a hora. Foca!"


def msg_checkin():
    d    = dia_semana()
    ex   = get_info_exercicio()
    ex_linha = f"\n{ex}?" if ex else ""
    return (
        "📋 *Check-in do dia!*\n\n"
        "Passa um olho no que você fez:\n\n"
        "🌅 Rotina matinal?\n"
        "📖 Curso (1h)?\n"
        "💻 Quantas horas de prática hoje?\n"
        "📝 Quantas horas de estudo?"
        f"{ex_linha}\n"
        "🇬🇧 Inglês (manhã e intervalo)?\n"
        "🥗 Almoço de verdade?\n"
        "🍎 Lanche saudável?\n\n"
        "_Cada missão feita é ponto. Amanhã tem mais._ 💪"
    )


def msg_rezar():
    return "🙏 *Antes de fechar os olhos — bora rezar.*\n\nBoas noites, Murilo. Descansa bem 🌙"


def msg_estudo_sab():
    return (
        "📖 *12h — Hora de estudar!*\n\n"
        "Sábado é dia de revisar e praticar.\n"
        "_Foca no que viu na semana._ 💪"
    )


def msg_ingles_sab(dados):
    tema = sortear_tema(dados)
    return (
        f"🇬🇧 *17h30 — Inglês!*\n\n"
        f"📱 LingQ — tema: *\"{tema}\"*\n"
        f"_(dificuldade: {dados.get('config_ingles', {}).get('dificuldade', 'medio')})_"
    )


def msg_organizacao():
    return (
        "📋 *19h — Organização!*\n\n"
        "💰 Financeiro — contas, gastos, pendências\n"
        "📋 Semanal — o que foi feito, o que falta\n\n"
        "_Organiza agora pra semana começar leve._ 🧠"
    )


def msg_treino_dom():
    return "🏃 *15h30 — Hora do treino!*\n\nDomingo é dia de mexer o corpo. Bora! 💪"


# =============================================================================
# HANDLER DE MENSAGENS DE TEXTO
# =============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto   = update.message.text
    chat_id = update.effective_chat.id

    dados = carregar()
    if dados.get("chat_id") is None:
        dados["chat_id"] = chat_id
        salvar(dados)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta = processar_mensagem(texto)
    await update.message.reply_text(resposta)


# =============================================================================
# HANDLER DE CLIQUE EM BOTÃO INLINE
# =============================================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    chat_id = query.message.chat_id
    cb_data = query.data

    await query.answer()

    dados   = carregar()
    tarefas = dados.get("tarefas", {})

    if cb_data.startswith("done:"):
        chave = cb_data.split(":", 1)[1]

        if chave in tarefas:
            t = tarefas[chave]
            t["done"] = not t["done"]
            salvar(dados)

            chaves_atuais = [
                btn.callback_data.split(":", 1)[1]
                for row in query.message.reply_markup.inline_keyboard
                for btn in row
                if btn.callback_data and btn.callback_data.startswith("done:")
            ]

            novo_teclado = construir_teclado(chaves_atuais, tarefas)
            await query.edit_message_reply_markup(reply_markup=novo_teclado)

            if t["done"]:
                await context.bot.send_message(chat_id, f"🎉 +{t['points']} pts!")
            else:
                await context.bot.send_message(chat_id, "↩️ Desmarcado.")

    elif cb_data == "status":
        tarefas_ativas = {k: v for k, v in tarefas.items() if not v.get("cancelado")}
        pts     = sum(t["points"] for t in tarefas_ativas.values() if t.get("done"))
        pts_max = sum(t["points"] for t in tarefas_ativas.values())
        pct     = int(pts / pts_max * 100) if pts_max else 0
        barra   = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        await context.bot.send_message(
            chat_id,
            f"📊 *{pts}/{pts_max} pts hoje*\n[{barra}] {pct}%",
            parse_mode="Markdown"
        )


# =============================================================================
# AGENDADOR — MENSAGENS AUTOMÁTICAS
# =============================================================================

async def enviar_notificacao(context: ContextTypes.DEFAULT_TYPE):
    """
    Roda a cada 60 segundos.
    1. Inicializa o dia se ainda não foi inicializado
    2. Verifica alertas customizados agendados pelo usuário
    3. Envia mensagens nos horários programados
    """
    agora   = agora_br()
    hoje    = agora.date().isoformat()
    h, m    = agora.hour, agora.minute

    # Garante que o dia está inicializado (idempotente)
    dados   = inicializar_dia()
    chat_id = dados.get("chat_id")

    if not chat_id:
        return

    tarefas  = dados.get("tarefas", {})
    enviados = dados.get("enviados", [])

    # ── Alertas customizados (agendar_lembrete) ───────────────────────────────
    alertas_pendentes = dados.get("alertas", [])
    alertas_alterados = False

    for alerta in alertas_pendentes:
        if alerta.get("enviado"):
            continue
        try:
            ah, am = map(int, alerta["hora"].split(":"))
        except Exception:
            continue
        if h == ah and m == am:
            await context.bot.send_message(
                chat_id,
                f"⏰ *Lembrete:* {alerta['texto']}",
                parse_mode="Markdown"
            )
            alerta["enviado"] = True
            alertas_alterados = True

    if alertas_alterados:
        dados["alertas"] = alertas_pendentes
        salvar(dados)

    # ── Mensagens agendadas fixas ─────────────────────────────────────────────
    horarios_hoje = get_horarios_do_dia()
    blocos_hoje   = get_blocos_do_dia()

    for hora_agend, min_agend, slug in horarios_hoje:
        chave = f"{hoje}-{hora_agend}:{min_agend:02d}-{slug}"

        if h == hora_agend and m == min_agend and chave not in enviados:

            # ── 7h00 — Rotina matinal ─────────────────────────────────────────
            if slug == "rotina":
                chaves = [k for k, t in tarefas.items() if t.get("bloco") == "rotina"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_rotina(),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )

            # ── Lista do dia (substitui briefing) ─────────────────────────────
            elif slug == "lista_dia":
                tarefas_ativas = {k: v for k, v in tarefas.items()
                                  if not v.get("cancelado") and v.get("bloco") != "rotina"}
                pts_max = sum(t["points"] for t in tarefas.values() if not t.get("cancelado"))

                linhas = [f"☀️ *Bom dia, Murilo!* Meta: *{pts_max} pts*\n"]
                for bloco, info in blocos_hoje.items():
                    if bloco == "rotina":
                        continue
                    nomes = [t["name"] for k, t in tarefas.items()
                             if t.get("bloco") == bloco and not t.get("cancelado")]
                    if nomes:
                        linhas.append(f"\n*{info['titulo']}*")
                        for n in nomes:
                            linhas.append(f"  • {n}")

                linhas.append("\n_Escreve o que fez e eu registro._")
                await context.bot.send_message(
                    chat_id, "\n".join(linhas),
                    parse_mode="Markdown"
                )

            # ── 12h00 — Almoço ────────────────────────────────────────────────
            elif slug == "almoco":
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == "almoco"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_almoco(),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )

            # ── 12h45 — Pós-almoço: inglês com tema ──────────────────────────
            elif slug == "pos_almoco":
                dados_atuais = carregar()
                await context.bot.send_message(
                    chat_id, msg_pos_almoco(dados_atuais),
                    parse_mode="Markdown"
                )

            # ── 17h55 — Intervalo das 18h ─────────────────────────────────────
            elif slug == "entretempo":
                dados_atuais = carregar()
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == "entretempo"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_entretempo(dados_atuais),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )

            # ── 19h00 — Faculdade ─────────────────────────────────────────────
            elif slug == "faculdade":
                chaves = [k for k, t in tarefas.items() if t.get("bloco") == "faculdade"]
                msg    = msg_faculdade()
                if chaves:
                    teclado = construir_teclado(chaves, tarefas)
                    await context.bot.send_message(
                        chat_id, msg,
                        parse_mode="Markdown",
                        reply_markup=teclado
                    )
                else:
                    await context.bot.send_message(
                        chat_id, msg,
                        parse_mode="Markdown"
                    )

            # ── 21h30 — Check-in noturno ──────────────────────────────────────
            elif slug == "checkin":
                await context.bot.send_message(
                    chat_id, msg_checkin(),
                    parse_mode="Markdown"
                )

            # ── 22h30 — Rezar ─────────────────────────────────────────────────
            elif slug == "rezar":
                await context.bot.send_message(
                    chat_id, msg_rezar(),
                    parse_mode="Markdown"
                )

            # ── Sábado: 12h — Estudo ──────────────────────────────────────────
            elif slug == "estudo_sab":
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == "estudo"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_estudo_sab(),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )
                # Também mostra tarefas de faculdade do sábado (se houver)
                chaves_fac = [k for k, t in tarefas.items() if t.get("bloco") == "faculdade"]
                if chaves_fac:
                    teclado_fac = construir_teclado(chaves_fac, tarefas)
                    await context.bot.send_message(
                        chat_id, "*📚 Tarefas de faculdade para hoje:*",
                        parse_mode="Markdown",
                        reply_markup=teclado_fac
                    )

            # ── Sábado: 17h30 — Inglês ───────────────────────────────────────
            elif slug == "ingles_sab":
                dados_atuais = carregar()
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == "ingles"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_ingles_sab(dados_atuais),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )

            # ── Sábado: 19h — Organização ─────────────────────────────────────
            elif slug == "organizacao":
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == "organizacao"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_organizacao(),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )

            # ── Domingo: 15h30 — Treino ───────────────────────────────────────
            elif slug == "treino_dom":
                chaves  = [k for k, t in tarefas.items() if t.get("bloco") == "treino"]
                teclado = construir_teclado(chaves, tarefas)
                await context.bot.send_message(
                    chat_id, msg_treino_dom(),
                    parse_mode="Markdown",
                    reply_markup=teclado
                )

            # ── 23h00 — Resumo final ──────────────────────────────────────────
            elif slug == "resumo":
                tarefas_ativas = {k: v for k, v in tarefas.items() if not v.get("cancelado")}
                pts     = sum(t["points"] for t in tarefas_ativas.values() if t.get("done"))
                pts_max = sum(t["points"] for t in tarefas_ativas.values())
                pct     = int(pts / pts_max * 100) if pts_max else 0

                if pct >= 80:   emoji = "🏆 Arrasou!"
                elif pct >= 50: emoji = "💪 Bom esforço!"
                else:           emoji = "📈 Amanhã é uma nova chance."

                await context.bot.send_message(
                    chat_id,
                    f"🌙 *Resumo do dia!*\n\n"
                    f"Pontuação final: *{pts}/{pts_max} pts* ({pct}%)\n\n"
                    f"{emoji}",
                    parse_mode="Markdown"
                )

            enviados.append(chave)
            dados["enviados"] = enviados
            salvar(dados)


# =============================================================================
# INICIALIZAÇÃO DO BOT
# =============================================================================

def main():
    token = os.getenv("BOT_TOKEN")

    # Inicializa o dia já no startup (cria tarefas se necessário)
    inicializar_dia()

    app = ApplicationBuilder().token(token).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Agendador a cada 60 segundos
    app.job_queue.run_repeating(enviar_notificacao, interval=60, first=10)

    print("🤖 Murilo Agent rodando! (Ctrl+C para parar)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
