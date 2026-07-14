"""
Interface da demo em Streamlit.

Rodar com: streamlit run app.py
"""

import json
from pathlib import Path

import streamlit as st

from agente import processar_mensagem
from ferramentas import ARQUIVO_ESCALADOS

st.set_page_config(page_title="Agente de Triagem de Suporte", page_icon="🎧")

st.title("🎧 Agente de Triagem de Suporte")
st.caption(
    "O agente classifica cada mensagem, responde dúvidas consultando a "
    "base de conhecimento e escala casos complexos para humanos."
)

# --- Barra lateral: mensagens de exemplo e fila de escalados ---------------

with st.sidebar:
    st.header("Mensagens de teste")
    mensagens_teste = json.loads(
        (Path(__file__).parent / "data" / "mensagens_teste.json").read_text(
            encoding="utf-8"
        )
    )
    opcoes = {f"#{m['id']} — {m['cliente']}": m for m in mensagens_teste}
    escolha = st.selectbox("Escolha um exemplo", list(opcoes.keys()))
    exemplo = opcoes[escolha]
    st.text_area("Prévia", exemplo["mensagem"], height=100, disabled=True)
    usar_exemplo = st.button("Usar esta mensagem", use_container_width=True)

    st.divider()
    st.header("🚨 Fila de escalados")
    if ARQUIVO_ESCALADOS.exists():
        tickets = json.loads(ARQUIVO_ESCALADOS.read_text(encoding="utf-8"))
        for t in reversed(tickets[-5:]):
            cor = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}.get(t["urgencia"], "⚪")
            st.markdown(f"{cor} **{t['cliente']}** — {t['resumo']}")
    else:
        st.caption("Nenhum ticket escalado ainda.")

# --- Área principal: entrada e resultado ------------------------------------

nome = st.text_input("Nome do cliente", value=exemplo["cliente"] if usar_exemplo else "")
mensagem = st.text_area(
    "Mensagem do cliente",
    value=exemplo["mensagem"] if usar_exemplo else "",
    height=120,
)

if st.button("Processar mensagem", type="primary") and mensagem.strip():
    with st.spinner("O agente está analisando..."):
        resultado = processar_mensagem(mensagem, nome)

    st.subheader("🧠 Raciocínio do agente")
    if not resultado["ferramentas"]:
        st.caption("O agente respondeu sem usar ferramentas.")
    for passo in resultado["ferramentas"]:
        with st.expander(f"🔧 {passo['ferramenta']}"):
            st.markdown("**Entrada:**")
            st.json(passo["entrada"])
            st.markdown("**Saída:**")
            st.code(passo["saida"], language=None)

    st.subheader("💬 Resposta ao cliente")
    st.success(resultado["resposta"])
