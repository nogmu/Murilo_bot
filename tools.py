# tools.py
# Define as ferramentas (ações) que o agente pode usar

from langchain_core.tools import tool
import json, os, datetime

DATA_FILE = "murilo_data.json"

def carregar():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"tarefas": {}, "dopamina": {}, "historico": {}}

def salvar(dados):
    with open(DATA_FILE, "w") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ── FERRAMENTA 1: Ver status do dia ──────────────────────────────────────────
@tool
def ver_status() -> str:
    """
    Retorna o status atual do dia: tarefas feitas, pendentes e pontuação.
    Use quando o usuário perguntar como está o dia, quantos pontos tem, etc.
    """
    dados   = carregar()
    tarefas = dados.get("tarefas", {})
    feitas    = [t for t in tarefas.values() if t.get("done")]
    pendentes = [t for t in tarefas.values() if not t.get("done")]
    pts     = sum(t["points"] for t in feitas)
    pts_max = sum(t["points"] for t in tarefas.values())

    resultado  = f"Pontuação: {pts}/{pts_max} pts\n"
    resultado += f"Feitas ({len(feitas)}): "    + ", ".join(t["name"] for t in feitas)    + "\n"
    resultado += f"Pendentes ({len(pendentes)}): " + ", ".join(t["name"] for t in pendentes)
    return resultado


# ── FERRAMENTA 2: Adicionar tarefa ───────────────────────────────────────────
@tool
def adicionar_tarefa(nome: str, bloco: str, pontos: int = 30) -> str:
    """
    Adiciona uma nova tarefa ao dia.
    - nome: nome da tarefa (ex: 'Cálculo - Lista 3')
    - bloco: onde a tarefa aparece. Opções: 'manha', 'almoco', 'entretempo', 'faculdade'
    - pontos: quantos pontos vale (padrão 30)
    Use quando o usuário quiser adicionar uma tarefa, estudo ou curso.
    """
    dados = carregar()
    chave = f"custom_{int(datetime.datetime.now().timestamp())}"
    dados["tarefas"][chave] = {
        "name":   f"📌 {nome}",
        "points": pontos,
        "done":   False,
        "bloco":  bloco
    }
    salvar(dados)
    return f"Tarefa '{nome}' adicionada no bloco '{bloco}' (+{pontos} pts)."


# ── FERRAMENTA 3: Marcar tarefa como feita ───────────────────────────────────
@tool
def marcar_tarefa(nome_parcial: str) -> str:
    """
    Marca uma tarefa como concluída.
    - nome_parcial: parte do nome da tarefa (ex: 'cálculo', 'inglês', 'exercício')
    Use quando o usuário disser que fez algo, terminou algo, concluiu algo.
    """
    dados      = carregar()
    tarefas    = dados["tarefas"]
    nome_lower = nome_parcial.lower()

    for chave, t in tarefas.items():
        if nome_lower in t["name"].lower() and not t.get("done"):
            t["done"] = True
            salvar(dados)
            return f"✅ '{t['name']}' marcada como feita! +{t['points']} pts"

    return f"Não encontrei tarefa pendente com '{nome_parcial}'. Use ver_status para ver as tarefas."


# ── FERRAMENTA 4: Registrar dopamina ─────────────────────────────────────────
@tool
def registrar_dopamina(app: str, minutos: int) -> str:
    """
    Registra o tempo de uso de redes sociais ou mídia.
    - app: nome do app (instagram, tiktok, youtube, musica, netflix, twitter)
    - minutos: quantos minutos usou
    Use quando o usuário mencionar que usou alguma rede social ou assistiu algo.
    """
    dados = carregar()
    dop   = dados.get("dopamina", {})
    dop[app.lower()] = dop.get(app.lower(), 0) + minutos
    dados["dopamina"] = dop
    salvar(dados)

    total = dop[app.lower()]
    return f"Registrado: {app} — {total} min total hoje."


# ── FERRAMENTA 5: Resetar marcações ──────────────────────────────────────────
@tool
def resetar_marcacoes() -> str:
    """
    Reseta todas as marcações do dia (volta tudo para não feito).
    Não apaga as tarefas, só desmarca as concluídas.
    Use quando o usuário pedir para resetar, reiniciar as marcações ou começar de novo.
    """
    dados   = carregar()
    tarefas = dados["tarefas"]
    for t in tarefas.values():
        t["done"] = False
    salvar(dados)
    return "🔄 Todas as marcações foram resetadas. As tarefas continuam salvas."


# Lista de todas as ferramentas disponíveis para o agente
TOOLS = [ver_status, adicionar_tarefa, marcar_tarefa, registrar_dopamina, resetar_marcacoes]
