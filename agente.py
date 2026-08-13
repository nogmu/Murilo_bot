# agente.py
# O agente: recebe mensagem em linguagem natural e decide o que fazer

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.messages import AIMessage, HumanMessage
from dotenv import load_dotenv
from tools import TOOLS
import os

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", """
Você é o assistente pessoal do Murilo, um estudante com TDAH que trabalha das 9h às 18h
e vai à faculdade às 19h.

Seu trabalho é ajudá-lo a gerenciar as tarefas do dia, registrar hábitos e manter o foco.

Regras:
- Responda SEMPRE em português
- Seja direto e animado, sem textão
- Use emojis com moderação
- Se o usuário disser que fez algo, use marcar_tarefa
- Se mencionar redes sociais, use registrar_dopamina
- Se pedir status, use ver_status
- Nunca invente dados — sempre use as ferramentas para buscar informação real

Blocos do dia:
- manha: 9h-12h (exercício, cursos)
- almoco: 12h-13h (almoço, inglês)
- entretempo: 18h-19h (inglês, descanso)
- faculdade: 19h+ (tarefas da facul, cursos)
"""),
    MessagesPlaceholder(variable_name="historico"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, TOOLS, prompt)

executor = AgentExecutor(
    agent=agent,
    tools=TOOLS,
    verbose=True,
    max_iterations=5
)

historico_sessao = []

def processar_mensagem(mensagem: str) -> str:
    global historico_sessao

    resultado = executor.invoke({
        "input":     mensagem,
        "historico": historico_sessao
    })

    resposta = resultado["output"]

    historico_sessao.append(HumanMessage(content=mensagem))
    historico_sessao.append(AIMessage(content=resposta))

    if len(historico_sessao) > 20:
        historico_sessao = historico_sessao[-20:]

    return resposta


if __name__ == "__main__":
    print("Agente do Murilo — digite sua mensagem (Ctrl+C para sair)\n")
    while True:
        try:
            msg = input("Você: ")
            if msg.strip():
                resposta = processar_mensagem(msg)
                print(f"\nBot: {resposta}\n")
        except KeyboardInterrupt:
            print("\nAté mais!")
            break
