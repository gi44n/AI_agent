🎧 Agente de Triagem de Suporte com IA

Agente de IA que faz triagem automática de mensagens de suporte ao cliente,
construído em Python com a API do Gemini (Google) e interface em Streamlit.

Para cada mensagem recebida, o agente decide sozinho qual ação tomar:


Classificar a categoria e a urgência do ticket (baixa/média/alta)
Responder dúvidas consultando uma base de conhecimento (RAG)
Escalar para um atendente humano, com resumo estruturado do caso


O diferencial em relação a um chatbot comum: o LLM não apenas gera texto —
ele escolhe e executa ferramentas (function calling) num loop de
raciocínio, recebendo os resultados de volta até concluir o atendimento.

Arquitetura

mensagem do cliente
        │
        ▼
   Agente (LLM) ◄──────────────┐
        │                      │
        ▼                      │ resultado da ferramenta
  escolhe uma ação ────────────┘
   ├─ classificar_ticket
   ├─ buscar_base_conhecimento (RAG)
   └─ escalar_para_humano
        │
        ▼
  resposta final ao cliente

O loop do agente é implementado manualmente (sem frameworks como LangChain)
justamente para deixar o mecanismo explícito: o modelo devolve um pedido
de função, o código Python faz o dispatch, executa e devolve o resultado
para o modelo continuar raciocinando. A interface exibe cada passo desse
"raciocínio" em tempo real.

Stack


Python 3 + google-genai
(SDK oficial do Gemini) — modelo gemini-3.5-flash
Streamlit para a interface da demo
RAG por palavra-chave sobre artigos em Markdown (evolução para
embeddings prevista no roadmap)
Prompts com resposta estruturada em JSON para a classificação


Como rodar

bash# 1. Clone o repositório e entre na pasta
git clone <url-do-repo>
cd agente-triagem

# 2. Crie e ative um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure sua chave (gratuita) do Google AI Studio
#    https://aistudio.google.com/apikey
export GOOGLE_API_KEY="sua-chave-aqui"

# 5. Teste rápido no terminal
python agente.py

# 6. Demo completa
streamlit run app.py

Dica: se a API retornar 404 para o modelo, liste os modelos disponíveis
para a sua conta — os nomes variam por conta e região:

bashpython -c "
from google import genai
for m in genai.Client().models.list():
    if 'generateContent' in (m.supported_actions or []):
        print(m.name)
"

Estrutura do projeto

├── agente.py            # Loop do agente + schemas das ferramentas + system prompt
├── ferramentas.py       # Implementação das 3 ferramentas
├── app.py               # Interface da demo (Streamlit)
└── data/
    ├── base_conhecimento/      # Artigos de FAQ (a "memória" do RAG)
    ├── mensagens_teste.json    # 8 mensagens fake, incluindo casos difíceis
    └── tickets_escalados.json  # Fila de escalados (gerado em runtime)

🔒 Lição aprendida: segurança vem dos dados também

Durante os testes, o agente pediu o CPF do cliente pelo chat — um dado
sensível num canal inadequado. Investigando, o problema não estava no
modelo nem no código: estava num artigo da base de conhecimento que
instruía exatamente isso. O agente apenas seguiu a política que recebeu.

Correções aplicadas:


O artigo da base foi reescrito para direcionar verificação de identidade
a um canal seguro
O system prompt ganhou uma regra explícita: nunca solicitar dados
sensíveis (CPF, documentos, senhas, cartão) pelo chat


Fica a lição: em sistemas com RAG, a base de conhecimento é parte da
superfície de segurança — auditar os dados importa tanto quanto auditar
o código.

Roadmap


 Trocar a busca por palavra-chave por embeddings (RAG semântico)
 Métricas na interface: % de tickets resolvidos automaticamente
 Testes automatizados: verificar se o agente usa as ferramentas
esperadas para cada mensagem de teste
 Unificar o nome do modelo numa configuração única (hoje aparece em
dois arquivos)


Créditos

Projeto desenvolvido como estudo de agentes de IA, com suporte do
Claude (Anthropic) na arquitetura, no código e no debugging — do
ambiente virtual ao incidente do CPF. A versão inicial do agente também
existe implementada com a API da Anthropic, o que ajudou a separar o que é
conceito de agente (loop, tool use, dispatch) do que é sintaxe de SDK.
