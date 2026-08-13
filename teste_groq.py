# teste_groq.py
# Demonstração dos 4 conceitos do LangChain + ferramentas do agente

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from dotenv import load_dotenv
import json, os, datetime

load_dotenv()

# ── CONCEITO 1: ChatModel ────────────────────────────────────────────────────
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3,
)

print("=== CONCEITO 1: ChatModel ===")
resposta = llm.invoke([HumanMessage(content="Me diga em uma frase o que é LangChain.")])
print(resposta.content)


# ── CONCEITO 2: PromptTemplate ───────────────────────────────────────────────
print("\n=== CONCEITO 2: PromptTemplate ===")
prompt_simples = ChatPromptTemplate.from_messages([
    ("system", "Você é um assistente de produtividade do Murilo."),
    ("human", "{mensagem_do_usuario}")
])

mensagem = prompt_simples.format_messages(mensagem_do_usuario="Sugira uma tarefa curta para hoje.")
resposta2 = llm.invoke(mensagem)
print(resposta2.content)


# ── ETAPA 4: Funções de dados (base das ferramentas) ────────────────────────
DATA_FILE = "murilo_data.json"

def carregar():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"tarefas": {}, "dopamina": {}, "historico": {}}

def salvar(dados):
    with open(DATA_FILE, "w") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ── CONCEITO 3: Tools ────────────────────────────────────────────────────────
@tool
def adicionar_tarefa(nome: str, bloco: str) -> str:
    """Adiciona uma nova tarefa ao bloco especificado do dia (manha, tarde, noite)."""
    dados = carregar()
    hoje = datetime.date.today().isoformat()
    dados["tarefas"].setdefault(hoje, {}).setdefault(bloco, []).append(nome)
    salvar(dados)
    return f"Tarefa '{nome}' adicionada ao bloco '{bloco}' em {hoje}."

@tool
def listar_tarefas(data: str = "") -> str:
    """Lista as tarefas do dia. Se data não for informada, usa o dia de hoje."""
    dados = carregar()
    alvo = data or datetime.date.today().isoformat()
    tarefas = dados["tarefas"].get(alvo, {})
    if not tarefas:
        return f"Nenhuma tarefa registrada para {alvo}."
    linhas = [f"Tarefas de {alvo}:"]
    for bloco, itens in tarefas.items():
        linhas.append(f"  {bloco}: {', '.join(itens)}")
    return "\n".join(linhas)

tools = [adicionar_tarefa, listar_tarefas]


# ── CONCEITO 4: Agent ────────────────────────────────────────────────────────
print("\n=== CONCEITO 4: Agent ===")
prompt_agente = ChatPromptTemplate.from_messages([
    ("system", "Você é um assistente de produtividade do Murilo. Use as ferramentas disponíveis quando necessário."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt_agente)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

resultado = executor.invoke({"input": "Adiciona a tarefa 'estudar LangChain' no bloco da tarde e depois lista as tarefas de hoje."})
print("\nResposta final:", resultado["output"])
