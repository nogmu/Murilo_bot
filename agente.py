# agente.py
# O cérebro do bot — usa LangGraph + Groq para entender linguagem natural
#
# POR QUE LANGGRAPH E NÃO LANGCHAIN PURO?
#   LangGraph é a evolução do LangChain para criar agentes.
#   É mais simples, mais estável e é o caminho recomendado atualmente.
#   create_react_agent() substitui o antigo create_tool_calling_agent().
#
# FLUXO:
#   Mensagem do usuário
#     → agente decide qual ferramenta usar (tools.py)
#       → ferramenta executa a ação
#         → agente formula a resposta
#           → resposta volta para o usuário

from langgraph.prebuilt import create_react_agent
# create_react_agent → cria um agente ReAct (Reasoning + Acting)
# ReAct = o agente raciocina sobre o que fazer, executa uma ferramenta,
#         observa o resultado, e decide o próximo passo

from langchain_groq import ChatGroq
# ChatGroq → conector com a API do Groq (LLM gratuito e rápido)

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# HumanMessage → mensagem do usuário
# AIMessage    → mensagem de resposta do agente
# SystemMessage → instrução de comportamento para o agente

from dotenv import load_dotenv
# Carrega as variáveis do .env (GROQ_API_KEY, BOT_TOKEN)

from tools import TOOLS
# Importa a lista de ferramentas definidas em tools.py

import os

load_dotenv()  # Lê o arquivo .env e disponibiliza as variáveis

# =============================================================================
# CONFIGURAÇÃO DO MODELO (LLM)
# =============================================================================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    # Modelo gratuito do Groq — rápido e muito capaz para português
    # Alternativas disponíveis: "mixtral-8x7b-32768", "gemma2-9b-it"

    api_key=os.getenv("GROQ_API_KEY"),
    # Chave lida do arquivo .env (nunca deixe a chave direta no código)

    temperature=0.2,
    # 0.0 = respostas mais determinísticas e precisas
    # 1.0 = respostas mais criativas e variadas
    # 0.2 é um bom equilíbrio para um assistente pessoal
)

# =============================================================================
# PROMPT DO SISTEMA
# =============================================================================
# Define quem o agente é e como ele deve se comportar.
# Este é o texto mais importante do agente — muda o prompt, muda o comportamento.

SYSTEM_PROMPT = """Você é o assistente pessoal do Murilo, um estudante com TDAH que:
- Trabalha das 9h às 18h
- Vai à faculdade às 19h
- Tem dois intervalos: almoço (12h-13h) e entre trabalho e faculdade (18h-19h)
- Objetivos principais: inglês, exercício, alimentação, faculdade

Seu trabalho é ajudá-lo a registrar e acompanhar as tarefas do dia.

REGRAS IMPORTANTES:
- Responda SEMPRE em português
- Seja direto e animado, sem textão — Murilo tem TDAH e não gosta de parede de texto
- Use no máximo 3-4 linhas por resposta
- Use emojis com moderação (1-2 por mensagem)
- SEMPRE use as ferramentas para buscar dados reais — nunca invente informações
- Se o usuário disser que fez algo → use marcar_tarefa
- Se mencionar redes sociais ou tempo de tela → use registrar_dopamina
- Se pedir status ou pontuação → use ver_status
- Se pedir para adicionar tarefa → use adicionar_tarefa

BLOCOS DO DIA:
- manha: 9h-12h (exercício, cursos)
- almoco: 12h-13h (almoço, inglês)
- entretempo: 18h-19h (inglês, descanso)
- faculdade: 19h+ (tarefas da faculdade, cursos noturnos)"""

# =============================================================================
# CRIAÇÃO DO AGENTE
# =============================================================================

# create_react_agent cria um agente com o modelo e as ferramentas
# O agente segue o ciclo: Pensar → Agir (usar ferramenta) → Observar → Responder
agente = create_react_agent(
    model=llm,
    tools=TOOLS,
    # prompt adiciona o prompt do sistema antes de cada conversa
    prompt=SystemMessage(content=SYSTEM_PROMPT)
)

# =============================================================================
# MEMÓRIA DA SESSÃO
# =============================================================================
# Armazena o histórico de mensagens da conversa atual.
# Permite que o agente lembre o que foi dito antes na mesma sessão.
# LIMITAÇÃO: esta memória é perdida quando o bot reinicia.
# (Memória persistente entre sessões será implementada futuramente com banco de dados)

historico_sessao = []

# =============================================================================
# FUNÇÃO PRINCIPAL — PROCESSAR MENSAGEM
# =============================================================================

def processar_mensagem(mensagem: str) -> str:
    """
    Recebe uma mensagem em linguagem natural e retorna a resposta do agente.

    Como funciona:
    1. Adiciona a nova mensagem ao histórico da sessão
    2. Passa o histórico completo para o agente (contexto da conversa)
    3. O agente decide se usa alguma ferramenta ou responde diretamente
    4. Extrai o texto da resposta
    5. Adiciona a resposta ao histórico para a próxima mensagem ter contexto
    6. Limita o histórico a 20 mensagens para não estourar o contexto do LLM

    Parâmetros:
    - mensagem: texto que o usuário digitou no Telegram

    Retorna:
    - string com a resposta do agente
    """
    global historico_sessao

    # Monta a lista de mensagens: histórico anterior + mensagem atual
    mensagens_entrada = historico_sessao + [HumanMessage(content=mensagem)]

    # Passa para o agente processar
    # O agente pode chamar ferramentas de tools.py antes de responder
    resultado = agente.invoke({"messages": mensagens_entrada})

    # Extrai a última mensagem da resposta (a resposta final do agente)
    mensagens_saida = resultado["messages"]
    resposta = mensagens_saida[-1].content

    # Atualiza o histórico com a nova troca de mensagens
    historico_sessao.append(HumanMessage(content=mensagem))
    historico_sessao.append(AIMessage(content=resposta))

    # Mantém apenas as últimas 20 mensagens para não estourar o limite do LLM
    # (cada modelo tem um limite máximo de tokens que aceita como contexto)
    if len(historico_sessao) > 20:
        historico_sessao = historico_sessao[-20:]

    return resposta


# =============================================================================
# TESTE DIRETO NO TERMINAL
# =============================================================================
# Este bloco só executa quando você roda: python agente.py
# Quando o main.py importa este arquivo, este bloco é ignorado.

if __name__ == "__main__":
    print("🤖 Agente do Murilo — teste no terminal")
    print("Digite sua mensagem (Ctrl+C para sair)\n")
    print("Exemplos:")
    print("  'como está meu dia?'")
    print("  'fiz o exercício agora'")
    print("  'adiciona tarefa de cálculo na faculdade'")
    print("  'usei 30 min de instagram'\n")

    while True:
        try:
            msg = input("Você: ").strip()
            if msg:
                print("\nBot: ", end="", flush=True)
                resposta = processar_mensagem(msg)
                print(resposta)
                print()
        except KeyboardInterrupt:
            print("\n\nAté mais! 👋")
            break
