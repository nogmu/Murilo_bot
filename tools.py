# =============================================================================
# MURILO AGENT — tools.py
# =============================================================================
# Define as ferramentas (ações) que o agente pode usar e os dados do dia.
# =============================================================================

from langchain_core.tools import tool
import json, os, datetime, random

DATA_FILE = "/tmp/murilo_data.json"

# =============================================================================
# BLOCOS DO DIA
# =============================================================================

BLOCOS = {
    "rotina": {
        "titulo": "🌅 Rotina Matinal",
        "tasks": {
            "meditacao":    {"name": "🧘 Meditação / Yoga",  "points": 10},
            "banho":        {"name": "🚿 Banho",            "points": 5},
            "dentes_manha": {"name": "🦷 Dentes + Creme",  "points": 10},
        }
    },
    "manha": {
        "titulo": "💼 Trabalho (9h–12h)",
        "tasks": {
            "curso":   {"name": "📖 Curso (1h)",  "points": 25},
            "pratica": {"name": "💻 Prática",     "points": 35},  # mais pontos!
            "estudo":  {"name": "📝 Estudo",      "points": 25},
        }
    },
    "almoco": {
        "titulo": "🥗 Almoço (12h–13h)",
        "tasks": {
            "almoco":        {"name": "🥗 Almoço de verdade",   "points": 20},
            "dentes_almoco": {"name": "🦷 Dentes após almoço",  "points": 10},
            "lingq":         {"name": "📱 LingQ (inglês)",         "points": 25},
        }
    },
    "entretempo": {
        "titulo": "⏳ Intervalo (18h–19h)",
        "tasks": {
            "ingles2":  {"name": "🎬 Filme/série + debate com IA (inglês)", "points": 20},
            "descanso": {"name": "😴 Descanso real",    "points": 20},
        }
    },
    "faculdade": {
        "titulo": "📚 Faculdade / Noite (19h+)",
        "tasks": {}  # Preenchido dinamicamente com adicionar_tarefa
    },
}

# =============================================================================
# BLOCOS DE SÁBADO
# =============================================================================

BLOCOS_SABADO = {
    "rotina": {
        "titulo": "🌅 Rotina Matinal (Sábado)",
        "tasks": {
            "meditacao":      {"name": "🧘 Meditação / Yoga",  "points": 10},
            "rezar_manha":    {"name": "🙏 Rezar",             "points": 5},
            "descanso_manha": {"name": "☕ Descanso / Café",    "points": 5},
        }
    },
    "estudo": {
        "titulo": "📖 Estudo (12h)",
        "tasks": {
            "estudo_sab": {"name": "📖 Estudo do dia", "points": 30},
        }
    },
    "ingles": {
        "titulo": "🇬🇧 Inglês (17h30)",
        "tasks": {
            "lingq_sab": {"name": "📱 LingQ (inglês)", "points": 20},
        }
    },
    "organizacao": {
        "titulo": "📋 Organização (19h)",
        "tasks": {
            "financeiro": {"name": "💰 Organização financeira", "points": 15},
            "semanal":    {"name": "📋 Organização semanal",    "points": 15},
        }
    },
    "faculdade": {
        "titulo": "📚 Faculdade (Sábado)",
        "tasks": {}  # Preenchido via adicionar_tarefa — praticar o que viu na aula
    },
}

# =============================================================================
# BLOCOS DE DOMINGO
# =============================================================================

BLOCOS_DOMINGO = {
    "rotina": {
        "titulo": "🌅 Rotina Matinal (Domingo)",
        "tasks": {
            "meditacao":   {"name": "🧘 Meditação / Yoga",  "points": 10},
            "rezar_manha": {"name": "🙏 Rezar",             "points": 5},
            "banho_sol":   {"name": "☀️ Banho de sol",       "points": 10},
        }
    },
    "treino": {
        "titulo": "🏃 Treino (15h30)",
        "tasks": {
            "treino": {"name": "🏃 Treino", "points": 30},
        }
    },
}

# =============================================================================
# TAREFAS PERIÓDICAS (quinzenal / mensal) — aparecem no sábado
# =============================================================================

TAREFAS_PERIODICAS = [
    {
        "chave": "psicologa",
        "name": "🧠 Psicóloga",
        "points": 15,
        "bloco": "estudo",          # aparece junto com estudo no sábado
        "frequencia_dias": 15,      # quinzenal
    },
    {
        "chave": "trancas",
        "name": "💇 Tranças",
        "points": 10,
        "bloco": "organizacao",
        "frequencia_dias": 30,      # mensal
    },
]

# =============================================================================
# GRADE DE AULAS
# =============================================================================
# weekday(): 0=segunda, 1=terça, 2=quarta, 3=quinta, 4=sexta, 5=sáb, 6=dom

AULAS = {
    0: {"nome": "POO Lab",              "sala": "Lab 8 🔵 Azul"},
    1: {"nome": "Estatística",          "sala": "Sala 14S"},
    2: None,  # quarta: sem aula — dia de exercício
    3: {"nome": "Programação Linear",   "sala": "Sala 14S"},
    4: {"nome": "Lab Eng. Software",    "sala": "Lab 05 🟢 Verde"},
    5: None,  # sábado
    6: None,  # domingo
}

# =============================================================================
# INGLÊS — TEMAS POR NÍVEL
# =============================================================================

TEMAS_INGLES = {
    "facil": [
        "rotina diária",
        "comida e restaurantes",
        "clima e estações",
        "hobbies e passatempos",
        "família e amigos",
    ],
    "medio": [
        "filmes e séries",
        "histórias de viagem",
        "tecnologia e apps",
        "esportes",
        "cultura pop",
        "desafios no trabalho",
    ],
    "dificil": [
        "notícias e atualidades",
        "dilemas éticos",
        "desenvolvimento de carreira",
        "análise de enredos complexos",
        "debates filosóficos",
    ],
}

# Dificuldade e contextos padrão — atualizáveis pelo usuário via bot
CONFIG_INGLES_PADRAO = {
    "dificuldade": "medio",
    "contextos": ["filmes", "tecnologia", "cotidiano", "viagens"],
}

# =============================================================================
# HELPERS
# =============================================================================

FUSO = datetime.timedelta(hours=-3)

def agora_br():
    return datetime.datetime.utcnow() + FUSO

def hoje_br():
    return agora_br().date()

def dia_semana():
    """0=segunda ... 6=domingo"""
    return hoje_br().weekday()

def get_aula_hoje():
    """Retorna dict com 'nome' e 'sala', ou None se não tiver aula."""
    return AULAS.get(dia_semana())

def get_info_exercicio():
    """Retorna string descritiva do exercício do dia, ou None se não tiver."""
    d = dia_semana()
    if d == 1: return "🏃 Exercício — de manhã, antes das 9h"
    if d == 2: return "🏃 Exercício — à noite, depois da faculdade"
    if d == 5: return "🏃 Exercício — sábado (combinado!)"
    if d == 6: return "🏃 Exercício — domingo (combinado!)"
    return None

def sortear_tema(dados=None):
    """Sorteia um tema de inglês baseado na config salva."""
    config = (dados or {}).get("config_ingles", CONFIG_INGLES_PADRAO)
    nivel  = config.get("dificuldade", "medio")
    temas  = TEMAS_INGLES.get(nivel, TEMAS_INGLES["medio"])
    return random.choice(temas)

def get_blocos_do_dia():
    """Retorna os blocos corretos baseado no dia da semana."""
    d = dia_semana()
    if d == 5:  # sábado
        return BLOCOS_SABADO
    if d == 6:  # domingo
        return BLOCOS_DOMINGO
    return BLOCOS  # seg-sex


def carregar():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "tarefas": {},
        "dopamina": {},
        "alertas": [],
        "enviados": [],
        "config_ingles": CONFIG_INGLES_PADRAO.copy(),
    }

def salvar(dados):
    with open(DATA_FILE, "w") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def inicializar_dia():
    """
    Inicializa as tarefas fixas a partir dos BLOCOS para o dia atual.
    Chamada uma vez por dia — detecta automaticamente se já foi rodada hoje.
    Preserva: tarefas custom adicionadas, alertas agendados, config de inglês.
    """
    dados    = carregar()
    hoje_str = hoje_br().isoformat()

    if dados.get("ultimo_dia") == hoje_str:
        return dados  # já inicializado hoje

    # Preserva custom tasks (adicionadas pelo usuário) e alertas
    custom  = {k: v for k, v in dados.get("tarefas", {}).items() if k.startswith("custom_")}
    alertas = dados.get("alertas", [])
    config  = dados.get("config_ingles", CONFIG_INGLES_PADRAO.copy())

    novas_tarefas = {}

    # Popula tarefas fixas dos blocos (escolhe seg-sex / sáb / dom)
    blocos_hoje = get_blocos_do_dia()
    for bloco, info in blocos_hoje.items():
        for chave, t in info["tasks"].items():
            novas_tarefas[chave] = {
                "name":   t["name"],
                "points": t["points"],
                "done":   False,
                "bloco":  bloco,
            }

    # Exercício físico — condicional por dia da semana
    info_ex = get_info_exercicio()
    if info_ex:
        d = dia_semana()
        # Terça → bloco manhã / Quarta → bloco faculdade / FDS → bloco manha
        bloco_ex = "manha" if d == 1 else "faculdade" if d == 2 else "manha"
        novas_tarefas["exercicio"] = {
            "name":   info_ex,
            "points": 40,
            "done":   False,
            "bloco":  bloco_ex,
        }

    # Tarefas periódicas (quinzenal/mensal) — só no sábado
    if dia_semana() == 5:
        periodicas_feitas = dados.get("periodicas_feitas", {})
        for tp in TAREFAS_PERIODICAS:
            ultima = periodicas_feitas.get(tp["chave"])
            incluir = True
            if ultima:
                dias_desde = (hoje_br() - datetime.date.fromisoformat(ultima)).days
                if dias_desde < tp["frequencia_dias"]:
                    incluir = False
            if incluir:
                novas_tarefas[tp["chave"]] = {
                    "name":   tp["name"],
                    "points": tp["points"],
                    "done":   False,
                    "bloco":  tp["bloco"],
                    "periodica": True,
                }

    # Reincorpora custom tasks (desmarcadas)
    for k, v in custom.items():
        v["done"] = False
        novas_tarefas[k] = v

    dados["tarefas"]       = novas_tarefas
    dados["dopamina"]      = {}
    dados["enviados"]      = []
    dados["ultimo_dia"]    = hoje_str
    dados["alertas"]       = alertas
    dados["config_ingles"] = config

    salvar(dados)
    return dados


# =============================================================================
# FERRAMENTAS DO AGENTE
# =============================================================================

@tool
def ver_status() -> str:
    """
    Retorna o status atual do dia: tarefas feitas, pendentes e pontuação.
    Use quando o usuário perguntar como está o dia, quantos pontos tem,
    o que fez, o que falta, etc.
    """
    dados   = carregar()
    tarefas = {k: v for k, v in dados.get("tarefas", {}).items() if not v.get("cancelado")}
    feitas    = [t for t in tarefas.values() if t.get("done")]
    pendentes = [t for t in tarefas.values() if not t.get("done")]
    pts     = sum(t["points"] for t in feitas)
    pts_max = sum(t["points"] for t in tarefas.values())

    res  = f"📊 {pts}/{pts_max} pts\n"
    res += f"✅ Feitas: " + (", ".join(t["name"] for t in feitas) or "nenhuma") + "\n"
    res += f"⬜ Pendentes: " + (", ".join(t["name"] for t in pendentes) or "nenhuma")
    return res


@tool
def adicionar_tarefa(nome: str, bloco: str, pontos: int = 30) -> str:
    """
    Adiciona uma nova tarefa ao dia.
    - nome: nome da tarefa (ex: 'Cálculo - Lista 3')
    - bloco: 'rotina', 'manha', 'almoco', 'entretempo' ou 'faculdade'
    - pontos: quantos pontos vale (padrão 30)
    Use quando o usuário quiser adicionar tarefa, estudo ou atividade.
    """
    dados = carregar()
    chave = f"custom_{int(datetime.datetime.now().timestamp())}"
    dados["tarefas"][chave] = {
        "name":   f"📌 {nome}",
        "points": pontos,
        "done":   False,
        "bloco":  bloco,
    }
    salvar(dados)
    return f"✅ Tarefa '{nome}' adicionada no bloco '{bloco}' (+{pontos} pts)."


@tool
def marcar_tarefa(nome_parcial: str) -> str:
    """
    Marca uma tarefa como concluída.
    - nome_parcial: parte do nome da tarefa (ex: 'cálculo', 'inglês', 'exercício')
    Use quando o usuário disser que fez, terminou ou concluiu algo.
    """
    dados      = carregar()
    tarefas    = dados["tarefas"]
    nome_lower = nome_parcial.lower()

    for chave, t in tarefas.items():
        if nome_lower in t["name"].lower() and not t.get("done") and not t.get("cancelado"):
            t["done"] = True
            # Registra data de conclusão para tarefas periódicas
            if t.get("periodica"):
                periodicas = dados.get("periodicas_feitas", {})
                periodicas[chave] = hoje_br().isoformat()
                dados["periodicas_feitas"] = periodicas
            salvar(dados)
            return f"🎉 '{t['name']}' marcada! +{t['points']} pts"

    return f"Não encontrei tarefa pendente com '{nome_parcial}'. Use ver_status para listar."


@tool
def cancelar_tarefa(nome_parcial: str) -> str:
    """
    Cancela (remove do dia) uma tarefa específica.
    - nome_parcial: parte do nome da tarefa (ex: 'exercício', 'inglês', 'curso')
    Use quando o usuário disser para cancelar, pular ou remover uma tarefa do dia.
    Também use quando ele disser que não vai ter aula ou que algo foi desmarcado.
    """
    dados      = carregar()
    tarefas    = dados["tarefas"]
    nome_lower = nome_parcial.lower()

    for chave, t in tarefas.items():
        if nome_lower in t["name"].lower() and not t.get("cancelado"):
            t["cancelado"] = True
            salvar(dados)
            return f"🚫 '{t['name']}' cancelada para hoje."

    return f"Não encontrei '{nome_parcial}' para cancelar."


@tool
def agendar_lembrete(hora: str, texto: str) -> str:
    """
    Agenda um lembrete para um horário específico hoje.
    - hora: no formato 'HH:MM' (ex: '20:00', '15:30')
    - texto: o que lembrar (ex: 'estudar cálculo', 'ligar para dentista')
    Use quando o usuário disser 'me lembra às X', 'me notifica às X para fazer Y'.
    """
    dados = carregar()
    alertas = dados.get("alertas", [])
    alertas.append({
        "hora":    hora,
        "texto":   texto,
        "enviado": False,
    })
    dados["alertas"] = alertas
    salvar(dados)
    return f"⏰ Lembrete agendado para {hora}: '{texto}'"


@tool
def alterar_ingles(dificuldade: str = None, contexto: str = None) -> str:
    """
    Altera a configuração da sessão de inglês.
    - dificuldade: 'facil', 'medio' ou 'dificil'
    - contexto: adiciona um contexto/tema preferido (ex: 'filmes', 'música')
    Use quando o usuário pedir para mudar a dificuldade do inglês ou adicionar contexto.
    """
    dados  = carregar()
    config = dados.get("config_ingles", CONFIG_INGLES_PADRAO.copy())

    msg_partes = []

    if dificuldade and dificuldade in TEMAS_INGLES:
        config["dificuldade"] = dificuldade
        msg_partes.append(f"dificuldade → {dificuldade}")

    if contexto:
        if contexto not in config["contextos"]:
            config["contextos"].append(contexto)
            msg_partes.append(f"contexto '{contexto}' adicionado")
        else:
            msg_partes.append(f"contexto '{contexto}' já estava na lista")

    dados["config_ingles"] = config
    salvar(dados)

    if msg_partes:
        return "🇬🇧 Inglês atualizado: " + ", ".join(msg_partes)
    return "Nada alterado. Use: dificuldade='facil'/'medio'/'dificil' ou contexto='filmes'."


@tool
def registrar_dopamina(app: str, minutos: int) -> str:
    """
    Registra o tempo de uso de redes sociais ou mídia.
    - app: nome do app (instagram, tiktok, youtube, netflix, etc.)
    - minutos: quantos minutos usou
    Use quando o usuário mencionar que usou rede social ou assistiu algo.
    """
    dados = carregar()
    dop   = dados.get("dopamina", {})
    dop[app.lower()] = dop.get(app.lower(), 0) + minutos
    dados["dopamina"] = dop
    salvar(dados)

    total = dop[app.lower()]
    aviso = " ⚠️ Já passando de 1h!" if total > 60 else ""
    return f"📱 {app}: {total} min total hoje.{aviso}"


@tool
def resetar_marcacoes() -> str:
    """
    Reseta todas as marcações do dia (volta tudo para não feito).
    Não apaga as tarefas, só desmarca as concluídas.
    Use quando o usuário pedir para resetar, reiniciar ou começar de novo.
    """
    dados   = carregar()
    tarefas = dados["tarefas"]
    for t in tarefas.values():
        t["done"]      = False
        t["cancelado"] = False
    salvar(dados)
    return "🔄 Marcações resetadas. As tarefas continuam salvas."


# Lista de todas as ferramentas disponíveis para o agente
TOOLS = [
    ver_status,
    adicionar_tarefa,
    marcar_tarefa,
    cancelar_tarefa,
    agendar_lembrete,
    alterar_ingles,
    registrar_dopamina,
    resetar_marcacoes,
]
