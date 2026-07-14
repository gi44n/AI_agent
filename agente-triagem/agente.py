"""
Núcleo do agente de triagem — versão Gemini (google-genai).

O fluxo é o clássico "agent loop" com tool use:

  mensagem do cliente
        │
        ▼
  LLM decide ──► chamou ferramenta? ──► executa a função Python
        ▲                                       │
        └────── resultado volta pro LLM ◄───────┘
        │
        ▼
  resposta final ao cliente

A arquitetura é idêntica à versão com a API da Anthropic — só muda a
sintaxe do SDK. Comparar as duas versões é um ótimo exercício para ver
que o CONCEITO de agente independe do provedor.
"""

import json

from google import genai
from google.genai import types

from ferramentas import (
    buscar_base_conhecimento,
    classificar_ticket,
    escalar_para_humano,
)

try:
    client = genai.Client()  # lê GOOGLE_API_KEY (ou GEMINI_API_KEY) do ambiente
except ValueError as e:
    raise SystemExit(
        "\nERRO: chave da API não encontrada.\n"
        "Configure antes de rodar, no mesmo terminal:\n\n"
        '  export GOOGLE_API_KEY="sua-chave-do-ai-studio"\n\n'
        "Crie uma chave gratuita em: https://aistudio.google.com/apikey\n"
    ) from e

MODELO = "gemini-3.5-flash"
# ---------------------------------------------------------------------------
# 1. Descrição das ferramentas (o "cardápio" que o LLM enxerga)
# ---------------------------------------------------------------------------
# Atenção às descrições: é POR ELAS que o modelo decide qual ferramenta usar.
# Descrição vaga = agente errando a escolha. Essa é uma das partes mais
# importantes de engenharia de prompt em agentes.

DECLARACOES_FERRAMENTAS = [
    {
        "name": "buscar_base_conhecimento",
        "description": (
            "Busca artigos na base de conhecimento da empresa (FAQ) para "
            "responder dúvidas sobre: senha e login, reembolso, cobranças, "
            "cancelamento de assinatura e problemas técnicos comuns. Use "
            "SEMPRE que a dúvida do cliente puder estar coberta pela FAQ, "
            "antes de considerar escalar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "A dúvida do cliente, reescrita de forma objetiva",
                }
            },
            "required": ["pergunta"],
        },
    },
    {
        "name": "classificar_ticket",
        "description": (
            "Classifica a mensagem do cliente em categoria e nível de "
            "urgência. Use em TODA mensagem recebida, como primeiro passo, "
            "antes de qualquer outra ação."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mensagem": {
                    "type": "string",
                    "description": "A mensagem original do cliente, na íntegra",
                }
            },
            "required": ["mensagem"],
        },
    },
    {
        "name": "escalar_para_humano",
        "description": (
            "Encaminha o caso para um atendente humano. Use quando: o "
            "cliente está visivelmente irritado ou ameaça sair/acionar "
            "órgãos de defesa; a dúvida NÃO é coberta pela base de "
            "conhecimento; o caso envolve negociação comercial ou dados que "
            "você não tem acesso. Sempre gere um resumo objetivo do caso."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resumo": {
                    "type": "string",
                    "description": "Resumo objetivo do caso para o atendente (2-3 frases)",
                },
                "urgencia": {
                    "type": "string",
                    "enum": ["baixa", "media", "alta"],
                },
                "cliente": {
                    "type": "string",
                    "description": "Nome do cliente, se conhecido",
                },
            },
            "required": ["resumo", "urgencia"],
        },
    },
]

# ---------------------------------------------------------------------------
# 2. System prompt: a "personalidade" e as regras do agente
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é um agente de triagem de suporte da empresa fictícia \
NuvemSoft. Sua função é resolver o máximo de tickets sozinho e escalar bem \
os que não conseguir.

Regras:
1. SEMPRE comece classificando a mensagem com `classificar_ticket`.
2. Se for uma dúvida, busque na base de conhecimento ANTES de responder. \
Responda apenas com base no que a busca retornar — nunca invente políticas.
3. Se a base não cobrir o assunto, ou o cliente estiver irritado/ameaçando \
sair, escale para humano com um bom resumo.
4. Elogios e feedbacks: agradeça cordialmente, sem usar ferramentas além da \
classificação.
5. Responda sempre em português, em tom cordial e direto. Chame o cliente \
pelo nome quando ele for informado.
"""

CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[types.Tool(function_declarations=DECLARACOES_FERRAMENTAS)],
    # Desliga a execução automática de funções: queremos controlar o loop
    # manualmente para entender (e exibir) cada passo do agente.
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

# ---------------------------------------------------------------------------
# 3. O loop do agente
# ---------------------------------------------------------------------------


def executar_ferramenta(nome: str, argumentos: dict) -> str:
    """Faz o 'dispatch': recebe o nome da ferramenta que o LLM pediu
    e executa a função Python correspondente."""
    if nome == "buscar_base_conhecimento":
        return buscar_base_conhecimento(argumentos["pergunta"])

    if nome == "classificar_ticket":
        return classificar_ticket(argumentos["mensagem"], client)

    if nome == "escalar_para_humano":
        return escalar_para_humano(
            resumo=argumentos["resumo"],
            urgencia=argumentos["urgencia"],
            # "cliente" é opcional no schema, então o LLM pode não enviar.
            # .get() evita KeyError nesse caso.
            cliente=argumentos.get("cliente", "desconhecido"),
        )

    # Se o modelo pedir uma ferramenta que não existe, devolvemos o erro
    # como TEXTO para ele ler e se recuperar sozinho — em agentes, erros
    # viram mensagens para o modelo, não exceções que derrubam o programa.
    return f"Erro: ferramenta desconhecida '{nome}'."


def processar_mensagem(mensagem_cliente: str, nome_cliente: str = "") -> dict:
    """Processa uma mensagem de cliente do início ao fim.

    Retorna um dicionário com a resposta final e o histórico de ferramentas
    usadas (para exibir o 'raciocínio' do agente na interface).
    """
    contexto = f"Cliente: {nome_cliente}\n" if nome_cliente else ""
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=contexto + mensagem_cliente)],
        )
    ]
    ferramentas_usadas = []

    # O loop roda até o modelo parar de pedir ferramentas. O limite de 6
    # iterações é uma trava de segurança contra loops infinitos.
    for _ in range(6):
        resposta = client.models.generate_content(
            model=MODELO,
            contents=contents,
            config=CONFIG,
        )

        if not resposta.function_calls:
            # O modelo respondeu direto: fim do loop
            return {
                "resposta": resposta.text or "",
                "ferramentas": ferramentas_usadas,
            }

        # O modelo pediu uma ou mais ferramentas: guarda o turno dele no
        # histórico e executa cada pedido, devolvendo os resultados para
        # ele continuar raciocinando
        contents.append(resposta.candidates[0].content)

        partes_resultado = []
        for chamada in resposta.function_calls:
            argumentos = dict(chamada.args or {})
            saida = executar_ferramenta(chamada.name, argumentos)
            ferramentas_usadas.append(
                {"ferramenta": chamada.name, "entrada": argumentos, "saida": saida}
            )
            partes_resultado.append(
                types.Part.from_function_response(
                    name=chamada.name,
                    response={"result": saida},
                )
            )

        contents.append(types.Content(role="user", parts=partes_resultado))

    return {
        "resposta": "Não consegui concluir o atendimento. Escalando para humano.",
        "ferramentas": ferramentas_usadas,
    }


# ---------------------------------------------------------------------------
# Teste rápido pelo terminal: python agente.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    resultado = processar_mensagem(
        "Esqueci minha senha e o link não chegou no e-mail", "Mariana"
    )
    print("FERRAMENTAS USADAS:")
    for f in resultado["ferramentas"]:
        print(f"  - {f['ferramenta']}({json.dumps(f['entrada'], ensure_ascii=False)})")
    print("\nRESPOSTA FINAL:\n", resultado["resposta"])
