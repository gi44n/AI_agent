"""
Ferramentas que o agente pode chamar.

Cada ferramenta é uma função Python comum. O agente (LLM) decide QUANDO
chamá-las e com QUAIS argumentos — esse é o coração do conceito de agente.
"""

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

PASTA_BASE = Path(__file__).parent / "data" / "base_conhecimento"
ARQUIVO_ESCALADOS = Path(__file__).parent / "data" / "tickets_escalados.json"


# ---------------------------------------------------------------------------
# Ferramenta 1: busca na base de conhecimento (RAG simples por palavra-chave)
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    """Remove acentos e deixa minúsculo, para a busca ser mais tolerante."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def buscar_base_conhecimento(pergunta: str) -> str:
    """Busca os artigos mais relevantes da base de conhecimento.

    Versão 1: busca por sobreposição de palavras (keyword matching).
    É simples, mas funciona bem para uma base pequena. No README há um
    exercício para evoluir isso para busca por embeddings (RAG "de verdade").
    """
    palavras_pergunta = set(re.findall(r"\w+", _normalizar(pergunta)))
    # Ignora palavras muito curtas ("de", "eu", "o"...), que não ajudam na busca
    palavras_pergunta = {p for p in palavras_pergunta if len(p) > 3}

    resultados = []
    for arquivo in PASTA_BASE.glob("*.md"):
        conteudo = arquivo.read_text(encoding="utf-8")
        palavras_artigo = set(re.findall(r"\w+", _normalizar(conteudo)))
        pontuacao = len(palavras_pergunta & palavras_artigo)
        if pontuacao > 0:
            resultados.append((pontuacao, arquivo.name, conteudo))

    if not resultados:
        return "Nenhum artigo relevante encontrado na base de conhecimento."

    # Ordena do mais relevante para o menos, e retorna só os 2 melhores
    resultados.sort(reverse=True, key=lambda r: r[0])
    top = resultados[:2]
    return "\n\n---\n\n".join(
        f"[Artigo: {nome}]\n{conteudo}" for _, nome, conteudo in top
    )


# ---------------------------------------------------------------------------
# Ferramenta 2: classificação de categoria e urgência
# ---------------------------------------------------------------------------

def classificar_ticket(mensagem: str, client) -> str:
    """Classifica a mensagem em categoria e urgência usando uma chamada
    dedicada ao LLM, pedindo resposta em JSON.

    Recebe o `client` do Gemini como parâmetro para não criar um novo
    a cada chamada.
    """
    # A mensagem do cliente vai entre tags <mensagem> para o modelo não
    # confundir o conteúdo dela com instruções (proteção básica contra
    # prompt injection). Repare também nos critérios explícitos de
    # urgência: sem eles, a classificação fica inconsistente.
    prompt_classificacao = f"""Você é um classificador de tickets de suporte.
Sua única função é classificar a mensagem abaixo. Você NÃO responde ao cliente.

<mensagem>
{mensagem}
</mensagem>

1. CATEGORIA — escolha exatamente uma:
   "cobranca", "tecnico", "cancelamento", "duvida_geral" ou "elogio_feedback"

2. URGENCIA — escolha exatamente uma, seguindo os critérios:
   - "alta": cliente ameaça cancelar ou acionar Procon/justiça, está
     impedido de usar o produto, ou relata perda financeira/de clientes
   - "media": problema real que atrapalha o uso, mas com contorno possível
     (cobrança a verificar, erro intermitente, dúvida que bloqueia uma ação)
   - "baixa": dúvida simples, feedback, elogio ou pedido sem impacto imediato

Responda SOMENTE com um JSON válido, sem texto antes ou depois, sem markdown:
{{"categoria": "...", "urgencia": "...", "justificativa": "uma frase curta"}}
"""

    resposta = client.models.generate_content(
    model="gemini-3.5-flash", 
      contents=prompt_classificacao,
    )
    texto = (resposta.text or "").strip()

    # Remove cercas de markdown caso o modelo as inclua, e valida o JSON
    texto = re.sub(r"^```(json)?|```$", "", texto, flags=re.MULTILINE).strip()
    try:
        classificacao = json.loads(texto)
        return json.dumps(classificacao, ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps(
            {"categoria": "duvida_geral", "urgencia": "media",
             "justificativa": "Falha ao interpretar classificação; usando padrão."},
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Ferramenta 3: escalar para atendimento humano
# ---------------------------------------------------------------------------

def escalar_para_humano(resumo: str, urgencia: str, cliente: str = "desconhecido") -> str:
    """'Envia' o ticket para a fila de atendimento humano.

    Na demo, isso significa salvar num arquivo JSON que o painel do
    Streamlit exibe. Em produção, seria uma chamada à API do Zendesk,
    Freshdesk, um webhook do Slack etc.
    """
    ticket = {
        "cliente": cliente,
        "resumo": resumo,
        "urgencia": urgencia,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
    }

    tickets = []
    if ARQUIVO_ESCALADOS.exists():
        tickets = json.loads(ARQUIVO_ESCALADOS.read_text(encoding="utf-8"))
    tickets.append(ticket)
    ARQUIVO_ESCALADOS.write_text(
        json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return (
        f"Ticket escalado com sucesso para a fila humana "
        f"(urgência: {urgencia}). Informe ao cliente que um atendente "
        f"entrará em contato."
    )
