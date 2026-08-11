# =============================================================================
# MURILO DAILY BOT v3 — Telegram
# =============================================================================
# O que este bot faz:
#   - Envia lembretes no horário certo (fuso UTC-3, Brasil)
#   - Organiza tarefas em blocos por horário do dia
#   - Permite marcar tarefas como feitas com botões inline
#   - Registra uso de redes sociais e calcula score de dopamina
#   - Permite adicionar tarefas customizadas (/add)
#   - Salva histórico de 14 dias — reseta automaticamente às 2h
#   - Exporta relatório do dia com /relatorio
# =============================================================================

import requests       # Para fazer chamadas à API do Telegram
import json           # Para salvar e carregar dados em arquivo
import time           # Para pausas e sleep no loop principal
import threading      # Para rodar o agendador em paralelo com o polling
import datetime       # Para checar hora atual e manipular datas
import os             # Para verificar arquivos e ler variáveis de ambiente

# =============================================================================
# CONFIGURAÇÃO PRINCIPAL
# =============================================================================

# Token do bot (lido da variável de ambiente BOT_TOKEN no Railway,
# ou usa o valor padrão caso não esteja configurado)
TOKEN = os.environ.get("BOT_TOKEN", "8572315166:AAGPC3ykHJzGCE4YygC5rbYkesIoZqGj5bw")

# URL base da API do Telegram — todas as chamadas partem daqui
BASE = f"https://api.telegram.org/bot{TOKEN}"

# Arquivo onde os dados do dia e o histórico ficam salvos no servidor
DATA_FILE = "/tmp/murilo_data.json"

# Fuso horário: Brasil (Brasília) = UTC - 3 horas
# Railway roda em UTC, então precisamos subtrair 3h para pegar o horário certo
FUSO_BRASIL = datetime.timedelta(hours=-3)

def agora_br():
    """Retorna o datetime atual no horário de Brasília (UTC-3)."""
    return datetime.datetime.utcnow() + FUSO_BRASIL

def hoje_br():
    """Retorna a data de hoje no formato 'YYYY-MM-DD' (horário de Brasília)."""
    return agora_br().date().isoformat()

# =============================================================================
# DEFINIÇÃO DOS BLOCOS E TAREFAS FIXAS
# =============================================================================
# Cada bloco representa um período do dia.
# Cada tarefa tem: nome, pontos e se foi concluída.
# O campo "bloco" indica a qual período a tarefa pertence.

BLOCOS = {
    "manha": {
        "titulo": "☀️ Manhã (9h–12h)",
        "tasks": {
            "exercicio": {"name": "🏃 Exercício físico",          "points": 40},
            "curso":     {"name": "📖 Curso durante o expediente", "points": 30},
        }
    },
    "almoco": {
        "titulo": "🥗 Almoço (12h–13h)",
        "tasks": {
            "almoco":  {"name": "🥗 Almoço de verdade", "points": 20},
            "ingles1": {"name": "🇬🇧 Inglês 20 min",    "points": 25},
            "lanche":  {"name": "🍎 Lanche saudável",   "points": 15},
        }
    },
    "entretempo": {
        "titulo": "⏳ Entre trabalho e faculdade (18h–19h)",
        "tasks": {
            "ingles2":  {"name": "🎧 Inglês sem legenda", "points": 20},
            "descanso": {"name": "😴 Descanso real",      "points": 20},
        }
    },
    "faculdade": {
        "titulo": "📚 Faculdade / Cursos (19h+)",
        "tasks": {}
        # Tarefas adicionadas com /add aparecem aqui
    },
}

# =============================================================================
# HORÁRIOS DE ENVIO AUTOMÁTICO (HORÁRIO DE BRASÍLIA)
# =============================================================================
# Formato: (hora, minuto, identificador_do_bloco)
# O agendador verifica a cada 30 segundos se chegou a hora de enviar.

HORARIOS = [
    (7,  30, "briefing"),      # Briefing completo do dia ao acordar
    (12,  0, "almoco"),        # Bloco do almoço
    (18,  0, "entretempo"),    # Bloco entre trabalho e faculdade
    (19,  0, "faculdade"),     # Bloco da faculdade/cursos
    (23,  0, "resumo"),        # Resumo final de pontos do dia
]

# Textos das mensagens enviadas em cada bloco
MSGS_BLOCO = {
    "almoco":     "⏰ *12h — Intervalo do almoço!*\n\nAproveita os 60 min 👇",
    "entretempo": "⏰ *18h — Entre o trampo e a facul!*\n\nRecarrega antes de começar 👇",
    "faculdade":  "🎓 *19h — Hora da faculdade!*\n\nSuas tarefas de hoje 👇",
}

# =============================================================================
# PERSISTÊNCIA DE DADOS (SALVAR E CARREGAR)
# =============================================================================

def carregar_dados():
    """
    Carrega os dados salvos do arquivo JSON.
    Se o arquivo não existir ou estiver corrompido, retorna estrutura vazia.

    Estrutura dos dados:
    {
      "chat_id": 123456,          ← ID do usuário no Telegram
      "data_atual": "2026-08-11", ← Data do dia atual
      "tarefas": { ... },         ← Tarefas do dia com status done/not done
      "enviados": [...],          ← Quais mensagens automáticas já foram enviadas hoje
      "dopamina": { ... },        ← Registro de uso de redes sociais
      "historico": {              ← Histórico dos últimos 14 dias
        "2026-08-10": { ... },
        "2026-08-09": { ... },
      }
    }
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except:
            pass  # Se der erro ao ler, começa do zero
    # Estrutura inicial quando não há dados salvos
    return {
        "chat_id": None,
        "data_atual": "",
        "tarefas": {},
        "enviados": [],
        "dopamina": {},
        "historico": {}
    }

def salvar_dados(dados):
    """Salva os dados no arquivo JSON no servidor."""
    with open(DATA_FILE, "w") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def montar_tarefas_do_dia():
    """
    Cria o dicionário de tarefas do dia a partir dos blocos fixos.
    Cada tarefa começa com done=False (não concluída).
    """
    tarefas = {}
    for bloco, info in BLOCOS.items():
        for chave, t in info["tasks"].items():
            tarefas[chave] = {
                "name":   t["name"],
                "points": t["points"],
                "done":   False,
                "bloco":  bloco   # qual bloco esta tarefa pertence
            }
    return tarefas

def salvar_historico_e_resetar(dados):
    """
    Salva o dia atual no histórico e prepara um novo dia zerado.

    - Guarda os dados do dia anterior (tarefas, dopamina, pontos)
    - Remove dias com mais de 14 dias do histórico
    - Cria novas tarefas zeradas para o dia atual
    Isso acontece automaticamente às 2h da manhã.
    """
    data_anterior = dados.get("data_atual", "")

    # Só salva no histórico se havia um dia anterior com dados
    if data_anterior:
        historico = dados.get("historico", {})

        # Salva o resumo do dia anterior
        historico[data_anterior] = {
            "tarefas":  dados.get("tarefas", {}),
            "dopamina": dados.get("dopamina", {}),
            "pts":      calcular_pontos(dados.get("tarefas", {})),
            "pts_max":  calcular_pontos_max(dados.get("tarefas", {})),
        }

        # Remove entradas mais antigas que 14 dias
        limite = (agora_br().date() - datetime.timedelta(days=14)).isoformat()
        historico = {d: v for d, v in historico.items() if d >= limite}

        dados["historico"] = historico

    # Zera o dia atual
    dados["data_atual"] = hoje_br()
    dados["tarefas"]    = montar_tarefas_do_dia()
    dados["enviados"]   = []
    dados["dopamina"]   = {}

    salvar_dados(dados)
    return dados

def verificar_reset_diario(dados):
    """
    Verifica se precisa resetar para um novo dia.
    O reset acontece quando a data mudou (e são mais de 2h da manhã,
    para dar tempo de registrar o resumo da meia-noite antes de resetar).
    """
    hoje = hoje_br()
    hora_atual = agora_br().hour

    # Se a data mudou e já passou das 2h, faz o reset
    if dados.get("data_atual") != hoje and hora_atual >= 2:
        dados = salvar_historico_e_resetar(dados)

    return dados

# =============================================================================
# CHAMADAS À API DO TELEGRAM
# =============================================================================

def api(metodo, **kwargs):
    """
    Faz uma requisição POST para a API do Telegram.
    Parâmetros são passados como JSON no corpo da requisição.
    Retorna o JSON da resposta ou dicionário vazio em caso de erro.
    """
    try:
        resposta = requests.post(f"{BASE}/{metodo}", json=kwargs, timeout=15)
        return resposta.json()
    except Exception as e:
        print(f"[API erro] {metodo}: {e}")
        return {}

def enviar(chat_id, texto, teclado=None):
    """
    Envia uma mensagem de texto para o usuário.
    Suporta formatação Markdown (negrito com *, itálico com _).
    Se 'teclado' for passado, exibe botões inline abaixo da mensagem.
    """
    params = {
        "chat_id":    chat_id,
        "text":       texto,
        "parse_mode": "Markdown"  # Permite usar *negrito*, _itálico_, etc.
    }
    if teclado:
        params["reply_markup"] = teclado
    return api("sendMessage", **params)

def editar_mensagem(chat_id, msg_id, texto, teclado=None):
    """
    Edita uma mensagem já enviada.
    Usado para atualizar os botões quando o usuário marca uma tarefa.
    """
    params = {
        "chat_id":    chat_id,
        "message_id": msg_id,
        "text":       texto,
        "parse_mode": "Markdown"
    }
    if teclado:
        params["reply_markup"] = teclado
    api("editMessageText", **params)

def responder_callback(callback_id, texto="✅"):
    """
    Responde a um clique de botão inline.
    Mostra uma notificação breve na tela do usuário (tipo toast/popup).
    """
    api("answerCallbackQuery", callback_query_id=callback_id, text=texto)

# =============================================================================
# CONSTRUÇÃO DOS TECLADOS INLINE (BOTÕES)
# =============================================================================

def construir_teclado(chaves_tarefas, tarefas):
    """
    Cria um teclado inline com botões para cada tarefa.

    - Tarefas concluídas mostram ✅, tarefas pendentes mostram ⬜
    - Cada botão tem callback_data='done:chave' para identificar qual tarefa foi clicada
    - Um botão extra no final mostra a pontuação atual
    """
    botoes = []
    for chave in chaves_tarefas:
        t = tarefas.get(chave)
        if not t:
            continue  # Pula se a tarefa não existir

        marca = "✅" if t.get("done") else "⬜"
        label = f"{marca} {t['name']} (+{t['points']} pts)"
        botoes.append([{
            "text":          label,
            "callback_data": f"done:{chave}"  # Enviado quando o botão é clicado
        }])

    # Botão de status no final
    botoes.append([{"text": "📊 Ver pontuação", "callback_data": "status"}])

    return {"inline_keyboard": botoes}

def chaves_do_bloco(bloco, tarefas):
    """
    Retorna as chaves de todas as tarefas que pertencem a um bloco específico.
    Ex: chaves_do_bloco('almoco', tarefas) → ['almoco', 'ingles1', 'lanche']
    """
    return [k for k, t in tarefas.items() if t.get("bloco") == bloco]

# =============================================================================
# CÁLCULO DE PONTOS E SCORE DE DOPAMINA
# =============================================================================

def calcular_pontos(tarefas):
    """Soma os pontos de todas as tarefas marcadas como concluídas."""
    return sum(t["points"] for t in tarefas.values() if t.get("done"))

def calcular_pontos_max(tarefas):
    """Soma os pontos máximos possíveis (todas as tarefas concluídas)."""
    return sum(t["points"] for t in tarefas.values())

def calcular_score_dopamina(dopamina):
    """
    Calcula o score de controle de dopamina (0 a 100).
    Quanto maior o score, melhor o controle.

    Limites saudáveis considerados:
    - Instagram: até 15 min sem penalidade
    - TikTok: até 10 min (mais viciante, penalidade maior)
    - YouTube: até 30 min
    - Música: até 90 min (menos dopamina rápida)
    - Facebook/Twitter: até 15 min

    A penalidade é calculada pelo excesso além do limite.
    """
    instagram = dopamina.get("instagram", 0)
    tiktok    = dopamina.get("tiktok", 0)
    youtube   = dopamina.get("youtube", 0)
    musica    = dopamina.get("musica", 0)
    facebook  = dopamina.get("facebook", 0)
    twitter   = dopamina.get("twitter", 0)
    netflix   = dopamina.get("netflix", 0)

    # Calcula penalidade: minutos além do limite × fator de impacto
    penalidade = (
        max(0, instagram - 15) * 1.5 +   # Instagram: penalidade moderada
        max(0, tiktok    - 10) * 2.0 +   # TikTok: penalidade alta (scroll infinito)
        max(0, youtube   - 30) * 1.0 +   # YouTube: penalidade média
        max(0, musica    - 90) * 0.3 +   # Música: penalidade baixa
        max(0, facebook  - 15) * 1.0 +
        max(0, twitter   - 15) * 1.2 +
        max(0, netflix   - 60) * 0.8
    )

    # Score vai de 0 a 100, nunca negativo
    return max(0, int(100 - penalidade))

def emoji_dopamina(score):
    """Retorna emoji de semáforo baseado no score de dopamina."""
    if score >= 85: return "🟢"   # Ótimo controle
    if score >= 60: return "🟡"   # Moderado
    return "🔴"                   # Muito uso de redes/estímulos

# =============================================================================
# TEXTOS DE STATUS E RELATÓRIO
# =============================================================================

def texto_status(dados):
    """
    Gera o texto completo de status do dia:
    - Pontuação atual vs máxima com barra de progresso
    - Cada bloco com suas tarefas (marcadas ou não)
    - Score de dopamina com registro de apps usados
    """
    tarefas  = dados["tarefas"]
    pts      = calcular_pontos(tarefas)
    pts_max  = calcular_pontos_max(tarefas)
    dopamina = dados.get("dopamina", {})
    score_dop = calcular_score_dopamina(dopamina)

    # Barra de progresso visual (ex: [████░░░░░░] 40%)
    pct = int(pts / pts_max * 10) if pts_max else 0
    barra = "█" * pct + "░" * (10 - pct)
    percentual = int(pts / pts_max * 100) if pts_max else 0

    linhas = [
        f"*📊 Pontuação do dia: {pts}/{pts_max} pts*",
        f"[{barra}] {percentual}%\n"
    ]

    # Lista as tarefas de cada bloco
    for bloco, info in BLOCOS.items():
        chaves = chaves_do_bloco(bloco, tarefas)
        if not chaves:
            continue
        linhas.append(f"*{info['titulo']}*")
        for k in chaves:
            t = tarefas[k]
            marca = "✅" if t.get("done") else "⬜"
            linhas.append(f"{marca} {t['name']} (+{t['points']})")
        linhas.append("")  # Linha em branco entre blocos

    # Score de dopamina
    emoji = emoji_dopamina(score_dop)
    linhas.append(f"*{emoji} Score de Dopamina: {score_dop}/100*")
    if dopamina:
        for app, mins in dopamina.items():
            linhas.append(f"  • {app.capitalize()}: {mins} min")
    else:
        linhas.append("  _Nenhum registro. Use /dopamina para registrar._")

    return "\n".join(linhas)

def texto_relatorio(dados):
    """
    Gera um relatório completo do dia para exportação.
    Pode ser copiado e colado para análise externa.
    """
    tarefas  = dados["tarefas"]
    pts      = calcular_pontos(tarefas)
    pts_max  = calcular_pontos_max(tarefas)
    dopamina = dados.get("dopamina", {})
    score_dop = calcular_score_dopamina(dopamina)
    pct = int(pts / pts_max * 100) if pts_max else 0

    linhas = [
        f"📋 *Relatório — {dados.get('data_atual', 'hoje')}*",
        f"Pontuação: *{pts}/{pts_max} pts* ({pct}%)",
        f"Score dopamina: *{score_dop}/100*\n",
        "*Tarefas:*"
    ]

    for t in tarefas.values():
        marca = "✅" if t.get("done") else "❌"
        linhas.append(f"{marca} {t['name']} (+{t['points']})")

    if dopamina:
        linhas.append("\n*Uso de redes/mídia:*")
        for app, mins in dopamina.items():
            linhas.append(f"• {app.capitalize()}: {mins} min")

    return "\n".join(linhas)

def texto_historico(dados):
    """
    Gera um resumo dos últimos dias salvos no histórico.
    Mostra pontuação e score de dopamina de cada dia.
    """
    historico = dados.get("historico", {})

    if not historico:
        return "📅 *Histórico vazio.*\nO histórico começa a aparecer a partir do segundo dia de uso."

    # Ordena do mais recente para o mais antigo
    datas_ordenadas = sorted(historico.keys(), reverse=True)

    linhas = ["📅 *Histórico dos últimos 14 dias:*\n"]
    for data in datas_ordenadas:
        d = historico[data]
        pts     = d.get("pts", 0)
        pts_max = d.get("pts_max", 1)
        dop     = calcular_score_dopamina(d.get("dopamina", {}))
        pct     = int(pts / pts_max * 100) if pts_max else 0
        emoji   = emoji_dopamina(dop)

        # Formata data de YYYY-MM-DD para DD/MM
        try:
            dt = datetime.date.fromisoformat(data)
            data_fmt = dt.strftime("%d/%m")
        except:
            data_fmt = data

        linhas.append(f"*{data_fmt}* — {pts}/{pts_max} pts ({pct}%) | {emoji} Dopamina: {dop}/100")

    return "\n".join(linhas)

# =============================================================================
# BRIEFING MATINAL (ENVIADO ÀS 7h30)
# =============================================================================

def enviar_briefing(chat_id, dados):
    """
    Envia o briefing completo do dia às 7h30.
    Mostra todos os blocos com botões para marcar tarefas.
    """
    tarefas = dados["tarefas"]
    pts_max = calcular_pontos_max(tarefas)

    # Mensagem introdutória
    enviar(chat_id,
        "🌅 *Bom dia, Murilo!* Seus blocos de hoje:\n\n"
        f"*Meta do dia: {pts_max} pts*\n\n"
        "📌 Use /add para adicionar tarefas da faculdade ou cursos\n"
        "📲 Use /dopamina para registrar redes sociais\n"
        "📊 Use /status para ver pontuação a qualquer hora"
    )

    # Envia cada bloco com seus botões
    for bloco, info in BLOCOS.items():
        chaves = chaves_do_bloco(bloco, tarefas)
        if chaves:  # Só envia se o bloco tiver tarefas
            teclado = construir_teclado(chaves, tarefas)
            enviar(chat_id, f"*{info['titulo']}*", teclado=teclado)

# =============================================================================
# PROCESSAMENTO DAS MENSAGENS E CALLBACKS
# =============================================================================

def processar_update(update, dados):
    """
    Processa cada mensagem ou clique de botão recebido do Telegram.

    Tipos de update:
    - 'message': mensagem de texto enviada pelo usuário
    - 'callback_query': clique em botão inline
    """

    # --- MENSAGEM DE TEXTO ---
    if "message" in update:
        msg     = update["message"]
        chat_id = msg["chat"]["id"]
        texto   = msg.get("text", "").strip()

        # Primeiro contato: registra o chat_id e ativa o bot
        if dados["chat_id"] is None:
            dados["chat_id"] = chat_id
            salvar_dados(dados)
            enviar(chat_id,
                "👋 *Bot ativado, Murilo!*\n\n"
                "Você vai receber lembretes automáticos nos horários:\n"
                "• 7h30 — briefing do dia\n"
                "• 12h — almoço e inglês\n"
                "• 18h — intervalo 2\n"
                "• 19h — faculdade\n"
                "• 23h — resumo de pontos\n\n"
                "*Comandos disponíveis:*\n"
                "/tarefas — ver missões com botões\n"
                "/add [nome] — adicionar tarefa da facul ou curso\n"
                "/dopamina [app] [min] — registrar uso de redes\n"
                "/status — ver pontuação atual\n"
                "/historico — ver últimos 14 dias\n"
                "/relatorio — exportar resumo do dia\n"
                "/reset — reiniciar o dia manualmente\n"
                "/ajuda — ver todos os comandos"
            )
            return

        # /start ou /ajuda — mostra lista de comandos
        if texto in ("/start", "/ajuda"):
            enviar(chat_id,
                "📱 *Comandos disponíveis:*\n\n"
                "/tarefas — missões do dia com botões\n"
                "/add [nome] — adicionar tarefa da faculdade ou curso\n"
                "  Ex: `/add Cálculo - Lista 3`\n\n"
                "/dopamina [app] [min] — registrar uso de redes\n"
                "  Ex: `/dopamina instagram 20 tiktok 15 musica 40`\n\n"
                "/status — pontuação atual do dia\n"
                "/historico — resumo dos últimos 14 dias\n"
                "/relatorio — texto exportável do dia\n"
                "/reset — reiniciar o dia (zera tarefas)\n"
                "/ajuda — esta mensagem"
            )

        # /status — mostra pontuação atual com todos os detalhes
        elif texto == "/status":
            enviar(chat_id, texto_status(dados))

        # /tarefas — envia cada bloco com botões para marcar
        elif texto == "/tarefas":
            tarefas = dados["tarefas"]
            for bloco, info in BLOCOS.items():
                chaves = chaves_do_bloco(bloco, tarefas)
                if chaves:
                    teclado = construir_teclado(chaves, tarefas)
                    enviar(chat_id, f"*{info['titulo']}*", teclado=teclado)

        # /relatorio — exporta resumo do dia em texto
        elif texto == "/relatorio":
            enviar(chat_id, texto_relatorio(dados))

        # /historico — mostra histórico dos últimos 14 dias
        elif texto == "/historico":
            enviar(chat_id, texto_historico(dados))

        # /reset — força o reset do dia (zera tudo)
        elif texto == "/reset":
            dados = salvar_historico_e_resetar(dados)
            enviar(chat_id, "🔄 Dia reiniciado! Todas as tarefas foram zeradas.")

        # /add [nome da tarefa] — adiciona tarefa customizada no bloco faculdade
        elif texto.lower().startswith("/add "):
            nome = texto[5:].strip()
            if not nome:
                enviar(chat_id,
                    "⚠️ Precisa informar o nome da tarefa.\n"
                    "Ex: `/add Cálculo - Lista 3`"
                )
                return

            # Cria uma chave única para esta tarefa
            chave = f"custom_{len(dados['tarefas'])}_{int(time.time())}"
            dados["tarefas"][chave] = {
                "name":   f"📌 {nome}",
                "points": 35,          # 35 pontos por tarefa customizada
                "done":   False,
                "bloco":  "faculdade"  # Aparece no bloco da faculdade
            }
            salvar_dados(dados)
            enviar(chat_id, f"✅ Tarefa adicionada: *{nome}* (+35 pts)\n\nUse /tarefas para ver com botões.")

        # /dopamina [app] [min] [app2] [min2] ... — registra uso de redes sociais
        elif texto.lower().startswith("/dopamina"):
            partes = texto.split()[1:]  # Remove o /dopamina e pega o resto

            # Precisa de pelo menos um par app + minutos
            if len(partes) < 2 or len(partes) % 2 != 0:
                enviar(chat_id,
                    "⚠️ Formato incorreto.\n\n"
                    "Use: `/dopamina [app] [minutos]`\n"
                    "Ex: `/dopamina instagram 20 tiktok 15 musica 40`\n\n"
                    "Apps reconhecidos:\n"
                    "instagram, tiktok, youtube, musica, netflix, facebook, twitter"
                )
                return

            dopamina = dados.get("dopamina", {})
            registros = []

            # Processa pares (app, minutos)
            for i in range(0, len(partes), 2):
                app = partes[i].lower()
                try:
                    mins = int(partes[i + 1])
                except ValueError:
                    enviar(chat_id, f"⚠️ '{partes[i+1]}' não é um número válido.")
                    return

                # Acumula: se já tinha 10 min de instagram e adiciona 10, fica 20
                dopamina[app] = dopamina.get(app, 0) + mins
                registros.append(f"• {app.capitalize()}: {dopamina[app]} min total hoje")

            dados["dopamina"] = dopamina
            salvar_dados(dados)

            score = calcular_score_dopamina(dopamina)
            emoji = emoji_dopamina(score)

            # Mensagem de feedback baseada no score
            if score >= 85:
                feedback = "_Ótimo controle hoje!_ 💚"
            elif score >= 60:
                feedback = "_Moderado. Tenta reduzir um pouco amanhã._ 🟡"
            else:
                feedback = "_Muita dopamina rápida hoje. Amanhã foca no descanso real._ 🔴"

            enviar(chat_id,
                f"📲 *Dopamina registrada!*\n\n"
                + "\n".join(registros) +
                f"\n\n{emoji} *Score de controle: {score}/100*\n"
                + feedback
            )

        # Comando desconhecido
        else:
            enviar(chat_id, "❓ Comando não reconhecido. Use /ajuda para ver os comandos.")

    # --- CLIQUE EM BOTÃO INLINE ---
    elif "callback_query" in update:
        cb      = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id  = cb["message"]["message_id"]
        cb_id   = cb["id"]
        cb_data = cb.get("data", "")

        # Botão de tarefa: done:chave_da_tarefa
        if cb_data.startswith("done:"):
            chave = cb_data.split(":", 1)[1]

            if chave in dados["tarefas"]:
                tarefa = dados["tarefas"][chave]

                # Toggle: se estava feita, desmarca; se não estava, marca
                tarefa["done"] = not tarefa["done"]
                salvar_dados(dados)

                # Notificação que aparece brevemente na tela
                if tarefa["done"]:
                    responder_callback(cb_id, f"+{tarefa['points']} pts! 🎉")
                else:
                    responder_callback(cb_id, "Desmarcado")

                # Descobre quais chaves estavam no teclado desta mensagem
                # (para recriar o teclado atualizado na mesma mensagem)
                chaves_atuais = [
                    btn["callback_data"].split(":", 1)[1]
                    for row in cb["message"].get("reply_markup", {}).get("inline_keyboard", [])
                    for btn in row
                    if btn.get("callback_data", "").startswith("done:")
                ]

                # Atualiza a mensagem com teclado refletindo o novo estado
                novo_teclado = construir_teclado(
                    chaves_atuais or list(dados["tarefas"].keys()),
                    dados["tarefas"]
                )
                editar_mensagem(chat_id, msg_id, cb["message"].get("text", ""), teclado=novo_teclado)

                # Mensagem especial se completou todas as tarefas
                if all(t.get("done") for t in dados["tarefas"].values()):
                    enviar(chat_id, "🏆 *Todas as tarefas concluídas! Incrível!* 🌙")

        # Botão de status
        elif cb_data == "status":
            responder_callback(cb_id)
            enviar(chat_id, texto_status(dados))

# =============================================================================
# AGENDADOR — RODA EM THREAD SEPARADA
# =============================================================================

def agendador():
    """
    Loop infinito que verifica a cada 30 segundos se chegou a hora
    de enviar alguma mensagem automática.

    Usa o horário de Brasília (UTC-3) para todas as comparações.
    Cada mensagem é marcada como 'enviada' para não repetir no mesmo dia.
    """
    while True:
        try:
            agora      = agora_br()           # Horário atual em Brasília
            hoje       = agora.date().isoformat()
            hora, min_ = agora.hour, agora.minute

            dados  = carregar_dados()
            dados  = verificar_reset_diario(dados)  # Verifica se precisa resetar (após 2h)
            chat_id = dados.get("chat_id")

            if chat_id:  # Só envia se o usuário já tiver ativado o bot
                enviados = dados.get("enviados", [])

                for hora_agend, min_agend, slug in HORARIOS:
                    # Chave única para este envio (data + hora + slug)
                    chave_envio = f"{hoje}-{hora_agend}:{min_agend:02d}-{slug}"

                    # Verifica se é a hora certa E se ainda não foi enviado hoje
                    if hora == hora_agend and min_ == min_agend and chave_envio not in enviados:

                        if slug == "briefing":
                            # Envia o briefing completo do dia
                            enviar_briefing(chat_id, dados)

                        elif slug in ("almoco", "entretempo", "faculdade"):
                            # Envia o bloco específico com botões das tarefas daquele período
                            chaves = chaves_do_bloco(slug, dados["tarefas"])
                            msg    = MSGS_BLOCO[slug]

                            if chaves:
                                teclado = construir_teclado(chaves, dados["tarefas"])
                                enviar(chat_id, msg, teclado=teclado)
                            else:
                                # Bloco de faculdade pode estar vazio se não usou /add
                                enviar(chat_id, msg + "\n\n_(Nenhuma tarefa adicionada. Use /add para adicionar.)_")

                        elif slug == "resumo":
                            # Resumo final às 23h
                            pts     = calcular_pontos(dados["tarefas"])
                            pts_max = calcular_pontos_max(dados["tarefas"])

                            if pts >= pts_max * 0.8:
                                conclusao = "🏆 *Arrasou hoje! Descansa bem.*"
                            elif pts >= pts_max * 0.5:
                                conclusao = "💪 *Bom esforço! Amanhã vai além.*"
                            else:
                                conclusao = "📈 *Amanhã é uma nova chance. Um passo de cada vez.*"

                            enviar(chat_id,
                                f"🌙 *Resumo do dia!*\n\n"
                                f"{texto_status(dados)}\n\n"
                                f"{conclusao}"
                            )

                        # Marca como enviado para não repetir
                        enviados.append(chave_envio)
                        dados["enviados"] = enviados
                        salvar_dados(dados)

        except Exception as e:
            print(f"[Agendador erro] {e}")

        # Aguarda 30 segundos antes de checar novamente
        time.sleep(30)

# =============================================================================
# INICIALIZAÇÃO E LOOP PRINCIPAL (LONG POLLING)
# =============================================================================

# Inicia o agendador em uma thread separada (roda em paralelo)
# daemon=True faz a thread encerrar automaticamente quando o programa principal fechar
threading.Thread(target=agendador, daemon=True).start()

print("🤖 Murilo Daily Bot v3 rodando! (Horário: Brasília UTC-3)")

# Long polling: fica perguntando ao Telegram se chegou alguma mensagem nova
# offset garante que cada mensagem seja processada apenas uma vez
offset = 0
while True:
    try:
        # Pede atualizações ao Telegram (timeout=30 faz esperar até 30s por resposta)
        resposta = requests.get(
            f"{BASE}/getUpdates",
            params={"offset": offset, "timeout": 30},
            timeout=35
        )
        updates = resposta.json().get("result", [])

        for update in updates:
            offset = update["update_id"] + 1  # Avança o offset para não reprocessar
            dados  = carregar_dados()
            dados  = verificar_reset_diario(dados)
            processar_update(update, dados)

    except Exception as e:
        print(f"[Polling erro] {e}")
        time.sleep(5)  # Espera 5s antes de tentar de novo em caso de erro
