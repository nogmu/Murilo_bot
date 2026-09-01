# =============================================================================
# MURILO AGENT — tools.py
# =============================================================================
# Define as ferramentas (ações) que o agente pode usar e os dados do dia.
#
# NOTA DE MANUTENÇÃO (mesclagem 30/08): esta versão junta duas linhas de
# desenvolvimento que haviam divergido:
#   1) a versão com 13 tools completas (cancelar_bloco, cancelar_agenda,
#      justificar_pendencia, editar_bloco, ajuda, tarefas rápida/repetida,
#      memória qualitativa, blocos_custom) — tinha um bug de sintaxe
#      (chave não fechada em BLOCOS["manha"]) que nunca foi publicado;
#   2) a versão publicada no GitHub/Railway, mais simples (8 tools), mas
#      com os blocos de sábado/domingo e tarefas periódicas (psicóloga,
#      tranças) que a primeira não tinha.
# Este arquivo tem as duas coisas: as 13 tools + os blocos de fim de semana.
# =============================================================================
from langchain_core.tools import tool
import json, os, datetime, random
import logging
import re
import unicodedata

logger = logging.getLogger("agente")

DATA_FILE = "/tmp/murilo_data.json"  # caminho do Railway (disco efêmero em /tmp)

# =============================================================================
# BLOCOS DO DIA (segunda a sexta)
# =============================================================================
BLOCOS = {
    "rotina": {
        "titulo": "🌅 Rotina Matinal",
        "tasks": {
            "meditacao":    {"name": "🧘 Meditação / Yoga",  "points": 10},
            "banho":        {"name": "🚿 Banho",             "points": 5},
            "dentes_manha": {"name": "🦷 Dentes + Creme",    "points": 10},
        }
    },
    "manha": {
        "titulo": "💼 Trabalho (9h–12h)",
        "tasks": {
            "curso":   {"name": "📖 Curso (1h)",  "points": 10},
            "pratica": {"name": "💻 Prática",     "points": 15},
        }
    },
    "almoco": {
        "titulo": "🥗 Almoço (12h–13h)",
        "tasks": {
            "almoco":        {"name": "🥗 Almoço de verdade",  "points": 20},
            "dentes_almoco": {"name": "🦷 Dentes após almoço", "points": 10},
            "lingq":         {"name": "📱 LingQ (inglês)",      "points": 25},
        }
    },
    "entretempo": {
        "titulo": "⏳ Intervalo (18h–19h)",
        "tasks": {
            "filme_serie": {"name": "🎬 Filme/série em inglês", "points": 20},
            "ia_ingles":   {"name": "💬 Conversa com IA em inglês", "points": 20},
            "descanso":    {"name": "😴 Descanso real", "points": 20},
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
            "meditacao":      {"name": "🧘 Meditação / Yoga", "points": 10},
            "rezar_manha":    {"name": "🙏 Rezar",            "points": 5},
            "descanso_manha": {"name": "☕ Descanso / Café",   "points": 5},
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
    "autocuidado": {
        "titulo": "🧴 Autocuidado (Sábado)",
        "tasks": {
            "banho_premium_sab": {"name": "🛁 Banho premium",            "points": 10},
            "dentes_11h_sab":    {"name": "🦷 Escovar os dentes (11h)",  "points": 5},
            "almoco_sab":        {"name": "🍽️ Almoço (15h)",             "points": 15},
            "dentes_almoco_sab": {"name": "🦷 Escovar os dentes (pós-almoço)", "points": 5},
            "janta_sab":         {"name": "🍽️ Janta (22h)",              "points": 15},
            "dentes_janta_sab":  {"name": "🦷 Escovar os dentes (pós-janta)",  "points": 5},
        }
    },
}

# =============================================================================
# BLOCOS DE DOMINGO
# =============================================================================
BLOCOS_DOMINGO = {
    "rotina": {
        "titulo": "🌅 Rotina Matinal (Domingo)",
        "tasks": {
            "meditacao":   {"name": "🧘 Meditação / Yoga", "points": 10},
            "rezar_manha": {"name": "🙏 Rezar",            "points": 5},
            "banho_sol":   {"name": "☀️ Banho de sol",      "points": 10},
        }
    },
    "treino": {
        "titulo": "🏃 Treino (15h30)",
        "tasks": {
            "treino": {"name": "🏃 Treino", "points": 30},
        }
    },
    "autocuidado": {
        "titulo": "🧴 Autocuidado (Domingo)",
        "tasks": {
            "banho_premium_dom": {"name": "🛁 Banho premium",            "points": 10},
            "dentes_11h_dom":    {"name": "🦷 Escovar os dentes (11h)",  "points": 5},
            "almoco_dom":        {"name": "🍽️ Almoço (15h)",             "points": 15},
            "dentes_almoco_dom": {"name": "🦷 Escovar os dentes (pós-almoço)", "points": 5},
            "janta_dom":         {"name": "🍽️ Janta (22h)",              "points": 15},
            "dentes_janta_dom":  {"name": "🦷 Escovar os dentes (pós-janta)",  "points": 5},
            "caminhada_dom":     {"name": "🚶 Andar 5 min",               "points": 10},
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
# HORÁRIO DE REFERÊNCIA DE CADA BLOCO
# =============================================================================
# O sistema não guarda um horário exato por tarefa — só sabe o bloco (ex:
# "faculdade"). Essa tabela dá uma hora aproximada pra cada bloco, usada por
# ajustar_agenda() pra saber quais tarefas caem dentro de uma janela de
# ausência (ex: "vou sair agora, demoro 4 horas"). Valores em (hora, minuto).
HORARIO_APROXIMADO_BLOCO = {
    # segunda a sexta
    "rotina":      (7, 0),
    "manha":       (9, 0),   # bloco corre até 12h — usamos o início como referência
    "almoco":      (12, 0),
    "entretempo":  (18, 0),
    "faculdade":   (19, 0),
    # sábado
    "estudo":      (12, 0),
    "ingles":      (17, 30),
    "organizacao": (19, 0),
    # domingo
    "treino":      (15, 30),
    # sábado e domingo
    "autocuidado": (11, 0),  # bloco tem 3 sub-horários (11h/15h/22h) — ver nota abaixo
}

# =============================================================================
# INGLÊS — TEMAS POR NÍVEL
# =============================================================================
TEMAS_INGLES = {
    "facil": [
        "Your daily morning routine", "Favorite childhood memory", "Describe your hometown",
        "Best meal you've ever eaten", "A hobby you enjoy", "Your dream vacation",
        "Pros and cons of working from home", "Describe your best friend", "A movie that made you cry",
        "Your favorite season and why", "How you spend weekends", "A skill you'd like to learn",
        "Your morning coffee/tea ritual", "Describe your pet (or a pet you'd like)", "A book you recently read",
        "Your favorite type of music", "Cooking vs. eating out", "A tradition in your family",
        "Your ideal weekend getaway", "Describe your workplace", "A gift you loved receiving",
        "Your favorite holiday", "City life vs. countryside life", "A sport you enjoy watching or playing",
        "Your comfort food", "Describe your bedroom", "A teacher who influenced you",
        "Your favorite app and why", "Weekend chores you dislike", "A place you'd like to visit",
        "Your favorite season for travel", "Describe a typical Sunday", "Your first job experience",
        "A language you'd like to learn", "Your favorite type of weather", "Shopping online vs. in stores",
        "A funny family story", "Your go-to karaoke song", "Describe your neighborhood",
        "A habit you're trying to build", "Your favorite dessert", "Board games vs. video games",
        "A compliment you received recently", "Your ideal Saturday night", "Describe your morning commute",
    ],
    "medio": [
        "The impact of social media on relationships", "Remote work vs. office culture",
        "The ethics of artificial intelligence", "How climate change affects your country",
        "The pros and cons of a four-day workweek", "Cultural differences in communication styles",
        "The role of failure in personal growth", "How technology has changed education",
        "The importance of mental health awareness", "Should college education be free?",
        "The influence of advertising on consumer behavior", "Work-life balance in modern society",
        "The rise of streaming services vs. traditional TV", "How social media influencers shape opinions",
        "The gig economy: freedom or exploitation?", "Should voting be mandatory?",
        "The effects of gentrification on communities", "Minimalism as a lifestyle choice",
        "The psychology behind procrastination", "How globalization affects local cultures",
        "The debate over standardized testing", "Online dating vs. traditional dating",
        "The role of nostalgia in marketing", "Should companies monitor employee productivity?",
        "The impact of fast fashion on the environment", "How urban planning affects quality of life",
        "The ethics of eating meat", "Should there be a universal basic income?",
        "The influence of parents on career choices", "How misinformation spreads online",
        "The value of a gap year", "Should tipping culture be abolished?",
        "The psychology of consumer debt", "How pets improve mental well-being",
        "The debate over school uniforms", "Should public transportation be free?",
        "The impact of automation on jobs", "Cultural appropriation vs. appreciation",
        "The role of humor in difficult conversations", "Should social media have age restrictions?",
        "The pressure of maintaining a personal brand online", "Is multitasking actually effective?",
        "The ethics of genetic testing", "How birth order affects personality",
        "Should homework be abolished?", "The impact of noise pollution on health",
        "Renting vs. buying a home", "The role of luck in success",
        "Should zoos exist in modern society?", "How childhood experiences shape adult relationships",
        "The debate over daylight saving time", "Should plastic be banned in packaging?",
        "The influence of celebrity culture on youth", "Is competition healthier than collaboration?",
        "The ethics of self-driving cars", "Should companies pay for employee mental health days",
        "The impact of fast food on public health", "How language shapes the way we think",
        "Should professional athletes be paid so much?", "The pros and cons of social media anonymity",
        "Debating movie and TV series plots and themes",
    ],
    "dificil": [
        "The philosophical implications of free will vs. determinism",
        "Should nations prioritize economic growth over environmental sustainability?",
        "The ethics of using AI in judicial sentencing",
        "How postcolonial history shapes modern geopolitics",
        "Is objective morality possible without religion?",
        "The paradox of choice in consumer societies",
        "Should reparations be paid for historical injustices?",
        "The epistemology of \"fake news\" and truth in the digital age",
        "Is the concept of nationhood becoming obsolete?",
        "The ethical dilemmas of gene editing (CRISPR)",
        "Should there be limits on free speech to prevent hate speech?",
        "The trolley problem and its real-world applications",
        "Is capitalism inherently at odds with environmental preservation?",
        "The philosophical question of consciousness in AI",
        "Should wealthy nations be obligated to accept more refugees?",
        "The tension between individual liberty and collective security",
        "Is meritocracy a myth or a reality?",
        "The ethics of surveillance capitalism",
        "Should euthanasia be legalized universally?",
        "How does linguistic relativity affect cross-cultural understanding?",
        "The role of cognitive biases in political polarization",
        "Is technological progress always beneficial to humanity?",
        "The ethics of animal testing in medical research",
        "Should historical monuments tied to oppression be removed?",
        "The paradox of tolerance in liberal democracies",
        "Is there a moral obligation to future generations regarding climate change?",
        "The philosophical debate on the nature of identity",
        "Should artificial intelligence have legal rights?",
        "The ethics of wealth inequality and taxation",
        "Is democracy the best form of governance for all societies?",
        "The psychological effects of living under constant digital surveillance",
        "Should countries be allowed to control immigration based on economic need alone?",
        "The ethics of designer babies and human enhancement",
        "Is objective journalism truly achievable?",
        "The philosophical implications of simulation theory",
        "Should corporations have the same rights as individuals?",
        "The tension between cultural relativism and universal human rights",
        "Is the pursuit of happiness a valid societal goal?",
        "The ethics of space colonization and resource exploitation",
        "Should there be a global governing body above nation-states?",
        "The philosophical roots of justice systems across cultures",
        "Is privacy a fundamental right or a negotiable privilege in the digital era?",
        "The ethics of predictive policing algorithms",
        "Should biological parenthood carry more legal weight than adoptive parenthood?",
        "Is human nature inherently selfish or cooperative?",
    ],
}

# Pesos extras: alguns temas caem mais vezes que os outros no sorteio.
# Tema não listado aqui tem peso 1 (padrão). Peso 3 = sorteia ~3x mais que os outros.
PESO_EXTRA_TEMAS = {
    "Debating movie and TV series plots and themes": 3,
}

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
    """
    Sorteia um tema de inglês baseado na config salva.
    Sorteio é PONDERADO — temas em PESO_EXTRA_TEMAS caem com mais frequência
    (ex: peso 3 = ~3x mais chance que um tema comum, peso 1).
    """
    config = (dados or {}).get("config_ingles", CONFIG_INGLES_PADRAO)
    nivel  = config.get("dificuldade", "medio")
    temas  = TEMAS_INGLES.get(nivel, TEMAS_INGLES["medio"])
    pesos  = [PESO_EXTRA_TEMAS.get(t, 1) for t in temas]
    return random.choices(temas, weights=pesos, k=1)[0]


def get_blocos_do_dia():
    """Retorna os blocos corretos baseado no dia da semana."""
    d = dia_semana()
    if d == 5:  # sábado
        return BLOCOS_SABADO
    if d == 6:  # domingo
        return BLOCOS_DOMINGO
    return BLOCOS  # seg-sex


# ── Persistência (com tratamento de erro) ───────────────────────────────────
def carregar():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # Um JSON corrompido ou erro de disco não derruba a resposta
            # inteira — cai pro padrão vazio e loga o problema.
            logger.error(f"falha ao ler {DATA_FILE}: {e}")
    return {
        "tarefas": {},
        "dopamina": {},
        "alertas": [],
        "enviados": [],
        "config_ingles": CONFIG_INGLES_PADRAO.copy(),
    }


def salvar(dados):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"falha ao salvar {DATA_FILE}: {e}")


# ── Memória qualitativa (formato tabela: lista de registros) ────────────────
MEMORIA_FILE = "/tmp/murilo_memoria.json"


def carregar_memoria() -> list:
    if os.path.exists(MEMORIA_FILE):
        try:
            with open(MEMORIA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"falha ao ler {MEMORIA_FILE}: {e}")
    return []


def salvar_memoria(registros: list):
    try:
        with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"falha ao salvar {MEMORIA_FILE}: {e}")


def _registrar_evento(tarefa: str, status: str, justificativa: str = ""):
    """Uso interno (não é tool): adiciona uma linha na memória qualitativa."""
    registros = carregar_memoria()
    registros.append({
        "data_hora":     datetime.datetime.now().isoformat(timespec="seconds"),
        "tarefa":        tarefa,
        "status":        status,
        "justificativa": justificativa,
    })
    salvar_memoria(registros)


def inicializar_dia():
    """
    Inicializa as tarefas fixas a partir dos BLOCOS do dia atual (semana,
    sábado ou domingo). Chamada uma vez por dia — detecta automaticamente
    se já foi rodada hoje. Preserva: tarefas custom ainda válidas, alertas
    agendados, config de inglês, tarefas periódicas concluídas.
    """
    dados    = carregar()
    hoje_str = hoje_br().isoformat()
    if dados.get("ultimo_dia") == hoje_str:
        return dados  # já inicializado hoje

    def _ainda_vale(v):
        # Tarefa "repetida" nunca expira sozinha (some só se o usuário
        # cancelar). Tarefa "rapida" some depois que a data dela já passou —
        # sem isso, um evento de um dia só voltaria pra sempre todo dia.
        if v.get("tipo", "rapida") == "repetida":
            return True
        return v.get("data", hoje_str) >= hoje_str

    custom = {
        k: v for k, v in dados.get("tarefas", {}).items()
        if k.startswith("custom_") and _ainda_vale(v)
    }
    alertas = dados.get("alertas", [])
    config  = dados.get("config_ingles", CONFIG_INGLES_PADRAO.copy())

    # Mescla as tarefas fixas dos blocos do dia com as edições salvas pelo
    # usuário via editar_bloco (guardadas em dados["blocos_custom"]). Isso
    # permite mudar nome/pontos, ou adicionar uma tarefa fixa nova a um
    # bloco, sem precisar editar o código — a alteração persiste em /tmp e
    # sobrevive a um restart do bot.
    overrides   = dados.get("blocos_custom", {})
    blocos_hoje = get_blocos_do_dia()

    novas_tarefas = {}
    for bloco, info in blocos_hoje.items():
        tasks_do_bloco = dict(info["tasks"])
        tasks_do_bloco.update(overrides.get(bloco, {}))  # overrides por cima do padrão
        for chave, t in tasks_do_bloco.items():
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
                    "name":      tp["name"],
                    "points":    tp["points"],
                    "done":      False,
                    "bloco":     tp["bloco"],
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

    if not tarefas:
        return "Nenhuma tarefa ativa hoje ainda."

    feitas    = [t for t in tarefas.values() if t.get("done")]
    pendentes = [t for t in tarefas.values() if not t.get("done")]
    pts     = sum(t["points"] for t in feitas)
    pts_max = sum(t["points"] for t in tarefas.values())
    pct     = round((pts / pts_max) * 100) if pts_max > 0 else 0

    res  = f"📊 {pts}/{pts_max} pts ({pct}%)\n"
    res += f"✅ Feitas: " + (", ".join(t["name"] for t in feitas) or "nenhuma") + "\n"
    res += f"⬜ Pendentes: " + (", ".join(t["name"] for t in pendentes) or "nenhuma")
    return res


@tool
def adicionar_tarefa(nome: str, bloco: str, pontos: int = 30, tipo: str = "rapida",
                      frequencia: str = "", data: str = "") -> str:
    """
    Adiciona uma nova tarefa ao dia.
    - nome: nome da tarefa (ex: 'Cálculo - Lista 3')
    - bloco: bloco válido do dia atual (varia entre semana, sábado e domingo —
      use ver_status ou ajuda se tiver dúvida sobre os blocos de hoje)
    - pontos: quantos pontos vale (padrão 30)
    - tipo: 'rapida' (acontece uma vez só, some depois da data) ou 'repetida'
      (se repete em vários dias, segundo a frequência)
    - frequencia: obrigatório se tipo='repetida'. Ex: 'todo dia', 'toda segunda'
    - data: data-alvo no formato AAAA-MM-DD. Se não informado, usa hoje.
    Use quando o usuário quiser adicionar tarefa, estudo ou atividade.
    Se o usuário mencionar mais de um dia ou repetição, use tipo='repetida' com
    frequencia preenchida. Se for um evento de um dia só, use tipo='rapida'.
    Se faltar informação de data/frequência para decidir, pergunte ao usuário
    antes de chamar esta ferramenta.
    """
    dados = carregar()
    chave = f"custom_{int(datetime.datetime.now().timestamp())}"
    data_alvo = data or hoje_br().isoformat()  # sem data informada -> hoje
    dados["tarefas"][chave] = {
        "name":       f"📌 {nome}",
        "points":     pontos,
        "done":       False,
        "bloco":      bloco,
        "tipo":       tipo,         # "rapida" ou "repetida"
        "frequencia": frequencia,   # só relevante se tipo == "repetida"
        "data":       data_alvo,    # usado pra expirar tarefas "rapida"
    }
    salvar(dados)

    if tipo == "repetida":
        return f"✅ Tarefa repetida '{nome}' adicionada no bloco '{bloco}' (+{pontos} pts) — frequência: {frequencia}."
    return f"✅ Tarefa rápida '{nome}' adicionada no bloco '{bloco}' (+{pontos} pts) para {data_alvo}."


def _normalizar_texto(texto: str) -> str:
    """Remove acentos, emojis e pontuação para comparar nomes com mais precisão."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


@tool
def marcar_tarefa(nome_parcial: str) -> str:
    """
    Marca uma tarefa como concluída.
    - nome_parcial: parte do nome da tarefa (ex: 'cálculo', 'inglês', 'exercício')
    Use quando o usuário disser que fez, terminou ou concluiu algo.
    """
    dados = carregar()
    tarefas = dados["tarefas"]
    busca = _normalizar_texto(nome_parcial)

    if not busca:
        return "Preciso do nome da tarefa para marcar como concluída."

    candidatas = []
    for chave, t in tarefas.items():
        if t.get("done") or t.get("cancelado"):
            continue
        nome_norm = _normalizar_texto(t["name"])
        score = 0

        if busca == nome_norm:
            score = 100
        elif busca in nome_norm:
            score = 80
        elif nome_norm in busca:
            score = 60
        elif busca.replace(" ", "") in nome_norm.replace(" ", ""):
            score = 50

        if score:
            candidatas.append({"chave": chave, "tarefa": t, "score": score, "nome": t["name"]})

    if not candidatas:
        return f"Não encontrei tarefa pendente com '{nome_parcial}'. Use ver_status para listar."

    melhor_score = max(item["score"] for item in candidatas)
    melhores = [item for item in candidatas if item["score"] == melhor_score]

    if len(melhores) > 1 and melhor_score < 100:
        nomes = ", ".join(item["nome"] for item in melhores)
        return f"Encontrei mais de uma tarefa parecida com '{nome_parcial}': {nomes}. Seja mais específico."

    item = melhores[0]
    chave = item["chave"]
    t = item["tarefa"]
    t["done"] = True

    if t.get("periodica"):
        periodicas = dados.get("periodicas_feitas", {})
        periodicas[chave] = hoje_br().isoformat()
        dados["periodicas_feitas"] = periodicas

    salvar(dados)
    return f"🎉 '{t['name']}' marcada! +{t['points']} pts"


@tool
def cancelar_tarefa(nome_parcial: str, motivo: str = "") -> str:
    """
    Cancela (remove do dia) UMA tarefa específica pelo nome.
    - nome_parcial: parte do nome da tarefa (ex: 'exercício', 'inglês', 'curso')
    - motivo: opcional, se o usuário disser por que está cancelando
    Use SÓ para uma tarefa isolada. Para cancelar um bloco inteiro (ex: "cancela
    a faculdade hoje"), use cancelar_bloco. Para cancelar o dia inteiro, use
    cancelar_agenda.
    """
    dados      = carregar()
    tarefas    = dados["tarefas"]
    nome_lower = nome_parcial.lower()

    candidatas = [
        (chave, t) for chave, t in tarefas.items()
        if nome_lower in t["name"].lower() and not t.get("cancelado")
    ]

    if not candidatas:
        return f"Não encontrei '{nome_parcial}' para cancelar."

    if len(candidatas) > 1:
        nomes = ", ".join(t["name"] for _, t in candidatas)
        return f"Encontrei mais de uma tarefa com '{nome_parcial}': {nomes}. Seja mais específico."

    chave, t = candidatas[0]
    t["cancelado"] = True
    salvar(dados)
    _registrar_evento(t["name"], "cancelado", motivo)

    if motivo:
        return f"🚫 '{t['name']}' cancelada para hoje. Motivo: {motivo}"
    return f"🚫 '{t['name']}' cancelada para hoje."


@tool
def cancelar_bloco(bloco: str, motivo: str = "") -> str:
    """
    Cancela TODAS as tarefas de um bloco/grande área do dia de uma vez.
    - bloco: bloco válido do dia atual
    - motivo: opcional, se o usuário disser por que está cancelando
    Use quando o usuário disser para cancelar um bloco inteiro, ex: "cancela a
    faculdade hoje", "hoje não vou fazer nada da manhã", "sem trabalho hoje".
    """
    dados   = carregar()
    tarefas = dados["tarefas"]

    afetadas = [t for t in tarefas.values() if t.get("bloco") == bloco and not t.get("cancelado")]
    if not afetadas:
        return f"Não encontrei tarefas ativas no bloco '{bloco}'."

    for t in afetadas:
        t["cancelado"] = True
    salvar(dados)
    _registrar_evento(f"bloco:{bloco}", "cancelado", motivo)

    nomes = ", ".join(t["name"] for t in afetadas)
    if motivo:
        return f"🚫 Bloco '{bloco}' cancelado ({nomes}). Motivo: {motivo}"
    return f"🚫 Bloco '{bloco}' cancelado ({nomes})."


@tool
def cancelar_agenda(motivo: str = "") -> str:
    """
    Cancela TODAS as tarefas do dia inteiro, de todos os blocos.
    - motivo: opcional, se o usuário disser por que está cancelando
    Use SÓ quando o usuário pedir para cancelar o dia inteiro / toda a agenda
    de hoje, não para uma tarefa ou bloco isolado.
    """
    dados   = carregar()
    tarefas = dados["tarefas"]

    afetadas = [t for t in tarefas.values() if not t.get("cancelado")]
    if not afetadas:
        return "Não havia tarefas ativas para cancelar hoje."

    for t in afetadas:
        t["cancelado"] = True
    salvar(dados)
    _registrar_evento("agenda completa", "cancelado", motivo)

    if motivo:
        return f"🚫 Agenda de hoje cancelada inteira ({len(afetadas)} tarefas). Motivo: {motivo}"
    return f"🚫 Agenda de hoje cancelada inteira ({len(afetadas)} tarefas)."


@tool
def justificar_pendencia(nome_parcial: str, motivo: str) -> str:
    """
    Registra o motivo pelo qual uma tarefa ainda não foi feita, SEM cancelar
    nem marcar como concluída — ela continua pendente e ativa na agenda.
    - nome_parcial: parte do nome da tarefa (ex: 'cálculo')
    - motivo: a justificativa dada pelo usuário
    Use quando o usuário explicar por que não fez algo ainda, sem pedir pra cancelar.
    """
    dados      = carregar()
    tarefas    = dados["tarefas"]
    nome_lower = nome_parcial.lower()

    candidatas = [t["name"] for t in tarefas.values() if nome_lower in t["name"].lower()]
    nome_tarefa = candidatas[0] if candidatas else nome_parcial

    _registrar_evento(nome_tarefa, "nao_feito", motivo)
    return f"📝 Justificativa registrada para '{nome_tarefa}': {motivo}. A tarefa continua pendente."


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


def _tarefas_dentro_da_janela(tarefas: dict, inicio_min: int, fim_min: int) -> list:
    """
    Uso interno: retorna [(chave, tarefa, hora_ref_min)] para tarefas ativas
    cujo horário de referência do bloco cai dentro da janela [inicio_min, fim_min)
    (minutos desde 00:00). Ignora tarefas custom (sem bloco fixo conhecido) e
    tarefas já feitas/canceladas.
    """
    resultado = []
    for chave, t in tarefas.items():
        if t.get("done") or t.get("cancelado"):
            continue
        bloco = t.get("bloco")
        ref = HORARIO_APROXIMADO_BLOCO.get(bloco)
        if not ref:
            continue  # bloco sem horário de referência conhecido (ex: custom sem mapeamento)
        h_ref, m_ref = ref
        min_ref = h_ref * 60 + m_ref
        if inicio_min <= min_ref < fim_min:
            resultado.append((chave, t, min_ref))
    return sorted(resultado, key=lambda x: x[2])


@tool
def ajustar_agenda(duracao_horas: float, motivo: str = "") -> str:
    """
    Ajusta a agenda de hoje quando o usuário vai sair/ficar indisponível por um
    período. Identifica as tarefas cujo horário cai dentro da janela de
    ausência, sugere um novo horário pra cada uma (logo após o retorno) e
    PROPÕE isso ao usuário — não move nada sozinho ainda.
    - duracao_horas: quantas horas o usuário ficará fora (ex: 4 para "4 horas")
    - motivo: opcional, o que o usuário vai fazer (ex: 'cinema')
    Use quando o usuário disser algo como 'vou sair agora, demoro X horas,
    ajusta minha agenda' ou 'vou ficar fora até tal hora'. Depois que o
    usuário CONFIRMAR os novos horários sugeridos nesta resposta, use
    confirmar_ajuste_agenda para cada tarefa com o horário definido.
    """
    dados   = carregar()
    tarefas = dados.get("tarefas", {})

    agora = agora_br()
    inicio_min = agora.hour * 60 + agora.minute
    fim_min    = inicio_min + int(duracao_horas * 60)

    afetadas = _tarefas_dentro_da_janela(tarefas, inicio_min, fim_min)

    if not afetadas:
        return (f"✅ Nenhuma tarefa cai no horário que você vai ficar fora "
                f"(próximas {duracao_horas:.0f}h). Pode ir tranquilo!")

    volta_min = fim_min % (24 * 60)
    volta_h, volta_m = divmod(volta_min, 60)

    linhas = [f"📋 Você vai ficar fora por {duracao_horas:.0f}h"
              + (f" ({motivo})" if motivo else "")
              + f", volta às {volta_h:02d}:{volta_m:02d}.",
              "",
              "Essas tarefas caem nesse período — sugestão de novo horário:"]

    sugestao_min = volta_min
    for chave, t, _ in afetadas:
        sh, sm = divmod(sugestao_min, 60)
        linhas.append(f"• {t['name']} → sugestão: {sh:02d}:{sm:02d} (chave: {chave})")
        sugestao_min += 30  # espaça as sugestões em 30min pra não empilhar tudo junto

    linhas.append("")
    linhas.append("Os horários acima estão certos pra você, ou quer mudar algum? "
                   "Depois de confirmar, eu aplico o ajuste.")
    return "\n".join(linhas)


@tool
def confirmar_ajuste_agenda(chave_tarefa: str, novo_horario: str) -> str:
    """
    Aplica o reagendamento de UMA tarefa depois que o usuário confirmou (ou
    corrigiu) o horário sugerido por ajustar_agenda.
    - chave_tarefa: a chave da tarefa (mostrada entre parênteses na resposta
      de ajustar_agenda, ex: 'faculdade' vira a chave real da tarefa daquele
      bloco no momento — use exatamente a chave informada antes)
    - novo_horario: no formato 'HH:MM' (ex: '20:00')
    Use uma vez para cada tarefa que o usuário confirmou. A tarefa original
    é marcada como cancelada (não dispara mais na notificação fixa do bloco)
    e um lembrete novo é criado pra notificar e reabrir a tarefa no novo
    horário.
    """
    dados   = carregar()
    tarefas = dados.get("tarefas", {})

    t = tarefas.get(chave_tarefa)
    if not t:
        return f"Não encontrei a tarefa com chave '{chave_tarefa}'. Confira o nome exato."

    # Cancela a ocorrência original (a notificação fixa do bloco não dispara
    # mais pra essa tarefa hoje), mas guarda os dados pra reabrir depois.
    t["cancelado"] = True
    t["reagendada_para"] = novo_horario

    alertas = dados.get("alertas", [])
    alertas.append({
        "hora":          novo_horario,
        "texto":         t["name"],
        "enviado":       False,
        "reabrir_chave": chave_tarefa,  # main.py usa isso pra reativar a tarefa
    })
    dados["alertas"] = alertas
    salvar(dados)
    _registrar_evento(t["name"], "reagendada", f"novo horário: {novo_horario}")

    return f"🔄 '{t['name']}' reagendada para {novo_horario}. Vou te avisar na hora."


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


@tool
def editar_bloco(bloco: str, chave_tarefa: str, nome: str = "", pontos: int = 0) -> str:
    """
    Cria ou edita uma tarefa FIXA de um bloco (ela passa a nascer todo dia
    automaticamente, diferente de adicionar_tarefa que cria algo pontual).
    - bloco: bloco válido do dia atual
    - chave_tarefa: identificador curto sem espaço (ex: 'ioga', 'leitura').
      Se já existir uma tarefa com essa chave nesse bloco, ela é atualizada.
    - nome: nome de exibição (ex: '🧘 Yoga'). Deixe vazio para não alterar.
    - pontos: quantos pontos vale. Deixe 0 para não alterar (numa tarefa nova,
      0 não é permitido — informe um valor).
    Use quando o usuário pedir para mudar o que tem em um bloco, adicionar uma
    tarefa fixa que se repete todo dia, ou mudar a pontuação de algo do bloco.
    Exemplos: "no bloco da manhã, muda o curso pra valer 40 pontos",
    "adiciona yoga na rotina, vale 15 pontos".
    """
    blocos_hoje = get_blocos_do_dia()
    if bloco not in blocos_hoje:
        return f"Bloco '{bloco}' não existe hoje. Opções de hoje: {', '.join(blocos_hoje.keys())}."

    dados = carregar()
    overrides = dados.setdefault("blocos_custom", {})
    bloco_overrides = overrides.setdefault(bloco, {})

    # Pega o valor atual (do padrão do bloco ou de um override já existente)
    # pra permitir editar só o nome OU só os pontos, sem apagar o outro campo.
    atual = bloco_overrides.get(chave_tarefa) or blocos_hoje[bloco]["tasks"].get(chave_tarefa) or {}
    novo_nome    = nome or atual.get("name", chave_tarefa)
    novos_pontos = pontos or atual.get("points", 20)

    bloco_overrides[chave_tarefa] = {"name": novo_nome, "points": novos_pontos}
    dados["blocos_custom"] = overrides
    salvar(dados)

    return (f"✏️ Bloco '{bloco}' atualizado: '{novo_nome}' (+{novos_pontos} pts). "
            f"Vale a partir de amanhã (ou do próximo /start do dia).")


@tool
def ajuda() -> str:
    """
    Mostra a lista de comandos/exemplos de frase que o agente entende e qual
    ferramenta cada um aciona. Use quando o usuário pedir ajuda, pedir a lista
    de comandos, perguntar o que o bot sabe fazer, ou disser '/ajuda'.
    """
    return (
        "🤖 *O que você pode me dizer:*\n\n"
        "✅ *Marcar feito:* \"fiz o exercício\", \"já almocei\" → marcar_tarefa\n"
        "📌 *Adicionar tarefa:* \"adiciona cálculo na faculdade\" → adicionar_tarefa\n"
        "   (diga se é só hoje ou se repete, senão eu pergunto)\n"
        "🚫 *Cancelar 1 tarefa:* \"cancela o inglês hoje\" → cancelar_tarefa\n"
        "🚫 *Cancelar um bloco:* \"cancela a faculdade hoje\" → cancelar_bloco\n"
        "🚫 *Cancelar o dia todo:* \"cancela a agenda de hoje\" → cancelar_agenda\n"
        "📝 *Justificar sem cancelar:* \"não fiz cálculo pq...\" → justificar_pendencia\n"
        "📊 *Ver status:* \"como tá meu dia?\" → ver_status\n"
        "📱 *Redes sociais:* \"usei 20 min de instagram\" → registrar_dopamina\n"
        "⏰ *Lembrete:* \"me lembra às 20h de estudar\" → agendar_lembrete\n"
        "🇬🇧 *Inglês:* \"muda o inglês pra difícil\" → alterar_ingles\n"
        "✏️ *Editar bloco fixo:* \"no bloco da manhã, curso vale 40 pontos agora\" → editar_bloco\n"
        "🔄 *Resetar o dia:* \"reseta tudo\" → resetar_marcacoes\n"
        "🗓️ *Vou sair, ajusta a agenda:* \"vou sair agora, demoro 4h\" → ajustar_agenda\n"
        "   (eu sugiro novos horários pras tarefas atropeladas, você confirma)\n\n"
        "_Pode falar naturalmente, não precisa decorar os nomes das ferramentas._"
    )


# Lista de todas as ferramentas disponíveis para o agente
TOOLS = [
    ver_status,
    adicionar_tarefa,
    marcar_tarefa,
    cancelar_tarefa,
    cancelar_bloco,
    cancelar_agenda,
    justificar_pendencia,
    agendar_lembrete,
    alterar_ingles,
    registrar_dopamina,
    resetar_marcacoes,
    editar_bloco,
    ajuda,
    ajustar_agenda,
    confirmar_ajuste_agenda,
]
