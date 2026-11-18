"""SUS Inteligente — Piauí: ponto de entrada da aplicação (navegação e identidade visual).

Execução:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="SUS Inteligente — Piauí", page_icon="🩺", layout="wide",
                   initial_sidebar_state="expanded")

from utils.config import PAGINA  # noqa: E402
from utils.data_loader import ErroDados, carregar_json  # noqa: E402
from utils.ui import barra_lateral, configurar_estilo  # noqa: E402

configurar_estilo()

paginas = [
    st.Page(PAGINA["visao_geral"], title="Visão Geral", icon=":material/dashboard:", default=True),
    st.Page(PAGINA["mapa"], title="Mapa Interativo", icon=":material/map:"),
    st.Page(PAGINA["municipal"], title="Análise Municipal", icon=":material/location_city:"),
    st.Page(PAGINA["previsoes"], title="Previsões", icon=":material/trending_up:"),
    st.Page(PAGINA["agrupamentos"], title="Agrupamentos Territoriais", icon=":material/hub:"),
    st.Page(PAGINA["alertas"], title="Alertas Analíticos", icon=":material/notifications:"),
    st.Page(PAGINA["sobre"], title="Sobre o Projeto", icon=":material/info:"),
]
navegacao = st.navigation(paginas)

try:
    metadados = carregar_json("metadados")
except ErroDados:
    metadados = None            # cada página mostra o erro correspondente ao carregar seus dados
barra_lateral(metadados)
navegacao.run()
