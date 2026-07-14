# 🎧 Agente de Triagem de Suporte

Agente de IA que faz triagem automática de mensagens de suporte ao cliente.
Ele decide sozinho, para cada mensagem, qual ação tomar:

1. **Classificar** a categoria e a urgência do ticket
2. **Responder** dúvidas consultando uma base de conhecimento (RAG)
3. **Escalar** para um atendente humano, com resumo estruturado do caso

O diferencial em relação a um chatbot comum: o LLM não apenas gera texto —
ele **escolhe e executa ferramentas** (tool use) num loop de raciocínio,
recebendo os resultados de volta até concluir o atendimento.

## Arquitetura

```
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
```

## Como rodar

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Configure sua chave da API
export GOOGLE_API_KEY="sua-chave-aqui"      # Linux/Mac
# set GOOGLE_API_KEY=sua-chave-aqui         # Windows (cmd)

# 3. Teste rápido no terminal
python agente.py

# 4. Rode a demo completa
streamlit run app.py
```

## Estrutura do projeto

```
├── agente.py            # Loop do agente + definição das ferramentas
├── ferramentas.py       # Implementação das 3 ferramentas
├── app.py               # Interface da demo (Streamlit)
└── data/
    ├── base_conhecimento/   # Artigos de FAQ (a "memória" do RAG)
    ├── mensagens_teste.json # Mensagens fake de clientes para testar
    └── tickets_escalados.json  # Fila de escalados (gerado em runtime)
```

## ✍️ Exercícios (partes deixadas para completar)

Os 2 exercícios originais já estão resolvidos nesta versão (veja os comentários no código):

1. **`ferramentas.py` → `classificar_ticket`**: escrever o prompt de
   classificação (categorias, critérios de urgência e formato JSON).
2. **`agente.py` → `executar_ferramenta`**: completar o dispatch da
   ferramenta `escalar_para_humano`.

### Próximos níveis (para evoluir o portfólio)

- Trocar a busca por palavra-chave por **embeddings** (ChromaDB ou
  sentence-transformers) — RAG semântico de verdade
- Adicionar **métricas** na interface: % de tickets resolvidos
  automaticamente vs. escalados
- Criar uma ferramenta nova, ex.: `consultar_status_pedido(numero)`
  lendo de um JSON fake
- Escrever **testes automatizados**: para cada mensagem de teste, verificar
  se o agente usou as ferramentas esperadas
