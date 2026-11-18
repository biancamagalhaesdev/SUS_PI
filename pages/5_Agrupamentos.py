"""Resultados do aprendizado não supervisionado: grupos de municípios com padrões semelhantes."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from utils import charts
from utils.config import COR, PALETA_GRUPOS
from utils.contexto import base, nomes_municipios
from utils.data_loader import carregar, carregar_geojson, carregar_json, exigir_dados
from utils.indicators import fmt_compacto, fmt_num, serie_indice
from utils.maps import colorir_categorias, construir_mapa
from utils.ui import cabecalho, linha_de_cards

cabecalho("Agrupamentos Territoriais", "Municípios com padrões semelhantes de produção ambulatorial (K-Means e hierárquico)")
prod, cat, W = exigir_dados(base)
agr = exigir_dados(carregar, "agrupamentos")
info = exigir_dados(carregar_json, "agrupamento_info")
geo = exigir_dados(carregar_geojson)
nomes = nomes_municipios(cat)
agr = agr.assign(nome=agr["codigo_ibge"].map(nomes))
ordem = info["ordem_grupos"]
k = info["k_final"]
selecao = pd.DataFrame(info["selecao_k"]).set_index("k")
col_sil = [c for c in selecao.columns if "K-Means" in c and "silhueta" in c][0]

linha_de_cards([
    ("Grupos identificados", str(k), "K-Means, comparado ao agrupamento hierárquico (Ward)"),
    ("Silhueta do K-Means", fmt_num(selecao.loc[k, col_sil], 2), "de −1 a 1; maior = grupos mais separados"),
    ("Variância explicada pela PCA", f"{sum(info['pca_variancia_explicada']):.0%}".replace(".", ","),
     "duas primeiras componentes, usadas só para visualização"),
], por_linha=3)

st.markdown(
    "**Atributos usados (calculados em jan/2021–dez/2024):** produção média mensal, desvio padrão, coeficiente de "
    "variação, crescimento, produção máxima, produção mínima e amplitude sazonal. Média, desvio, máximo e mínimo passam "
    "por log10 antes da padronização. Os nomes dos grupos foram atribuídos depois de examinar suas características.")

# Mapa e escolha de k -----------------------------------------------------------------
col1, col2 = st.columns([1.6, 1])
with col1:
    cores, legenda = colorir_categorias(agr.set_index("codigo_ibge")["nome_grupo"], ordem)
    tabela = pd.DataFrame({"codigo_ibge": cores.index, "cor": cores.values,
                           "valor_fmt": agr.set_index("codigo_ibge")["nome_grupo"].reindex(cores.index).values})
    st_folium(construir_mapa(geo, tabela, "Grupo territorial", legenda), key="mapa_grupos", height=520,
              use_container_width=True, returned_objects=[])
with col2:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=selecao.index, y=selecao[col_sil], mode="lines+markers", name="K-Means",
                             line=dict(color=COR["azul"])))
    col_hc = [c for c in selecao.columns if "silhueta" in c and "hier" in c]
    if col_hc:
        fig.add_trace(go.Scatter(x=selecao.index, y=selecao[col_hc[0]], mode="lines+markers", name="Hierárquico",
                                 line=dict(color=COR["amarelo"], dash="dot")))
    fig.add_vline(x=k, line_color=COR["vermelho"], line_dash="dash")
    st.plotly_chart(charts._finalizar(fig, "Coeficiente de silhueta por número de grupos", "k", "Silhueta", 250),
                    width="stretch")
    col_in = [c for c in selecao.columns if "in" in c.lower() and "rcia" in c.lower()]
    if col_in:
        fig2 = go.Figure(go.Scatter(x=selecao.index, y=selecao[col_in[0]], mode="lines+markers",
                                    line=dict(color=COR["azul"])))
        fig2.add_vline(x=k, line_color=COR["vermelho"], line_dash="dash")
        st.plotly_chart(charts._finalizar(fig2, "Método do cotovelo (inércia do K-Means)", "k", "Inércia", 250),
                        width="stretch")

# Características ---------------------------------------------------------------------
st.markdown("### Características de cada grupo")
resumo = agr.groupby("nome_grupo").agg(
    municipios=("codigo_ibge", "size"), producao_media=("media_mensal", "median"), cv=("cv", "median"),
    crescimento=("crescimento", "median"), amplitude=("amplitude_sazonal", "median"),
    minima=("producao_minima", "median")).reindex(ordem)
resumo_fmt = pd.DataFrame({
    "Municípios": resumo["municipios"],
    "Produção mensal (mediana)": resumo["producao_media"].map(fmt_compacto),
    "CV (mediana)": resumo["cv"].map(fmt_num),
    "Crescimento 2021→2024 (mediana)": resumo["crescimento"].map(fmt_num),
    "Amplitude sazonal (mediana)": resumo["amplitude"].map(fmt_num),
    "Produção mínima mensal (mediana)": resumo["minima"].map(fmt_compacto),
})
st.dataframe(resumo_fmt, width="stretch")
st.caption("Crescimento = (média de 2024 − média de 2021) ÷ média dos dois anos, entre −2 e 2. "
           "Amplitude sazonal = (maior − menor média por mês do ano) ÷ média geral.")

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.dispersao(agr, "media_mensal", "cv", "nome_grupo", ordem,
                                     "Produção média × variabilidade", "Produção média mensal (escala log)",
                                     "Coeficiente de variação", log_x=True), width="stretch")
with col4:
    cargas = info["pca_cargas"]
    v1, v2 = info["pca_variancia_explicada"]
    st.plotly_chart(charts.dispersao(agr, "pca1", "pca2", "nome_grupo", ordem, "Visualização PCA dos municípios",
                                     f"Componente 1 ({v1:.0%})", f"Componente 2 ({v2:.0%})"), width="stretch")
    principal = max(cargas, key=lambda v: abs(cargas[v][0]))
    secundario = max(cargas, key=lambda v: abs(cargas[v][1]))
    st.caption(f"Maior carga na componente 1: {principal}; na componente 2: {secundario}.")

st.markdown("### Comparação das características")
abas_var = st.tabs(["Produção média", "Coeficiente de variação", "Crescimento", "Amplitude sazonal"])
for aba, (var, rot, log_y) in zip(abas_var, [("media_mensal", "Produção média mensal", True), ("cv", "CV", False),
                                              ("crescimento", "Crescimento", False),
                                              ("amplitude_sazonal", "Amplitude sazonal", False)]):
    with aba:
        st.plotly_chart(charts.caixas_por_grupo(agr, var, ordem, f"{rot} por grupo", rot, log_y=log_y),
                        width="stretch")

st.markdown("### Tendência temporal de cada grupo")
indices = W.apply(serie_indice, axis=1)
linhas = []
for g in ordem:
    membros = agr.loc[agr["nome_grupo"] == g, "codigo_ibge"]
    linhas.append(indices.loc[membros].median().rename(g))
trend = pd.concat(linhas, axis=1).rolling(3).mean()
fig = px.line(trend, labels={"value": "Índice (média do período = 100)", "competencia": "Mês de processamento",
                             "variable": "Grupo"},
              color_discrete_map={g: PALETA_GRUPOS[i] for i, g in enumerate(ordem)})
st.plotly_chart(charts._finalizar(fig, "Mediana do índice de produção por grupo (média móvel de 3 meses)",
                                  "Mês de processamento", "Índice"), width="stretch")

# Municípios por grupo e comparação entre algoritmos ----------------------------------
st.markdown("### Municípios de cada grupo")
abas = st.tabs([f"{g} ({(agr['nome_grupo'] == g).sum()})" for g in ordem])
for aba, g in zip(abas, ordem):
    with aba:
        t = agr[agr["nome_grupo"] == g].sort_values("media_mensal", ascending=False)
        st.dataframe(pd.DataFrame({"Município": t["nome"], "Produção média mensal": t["media_mensal"].map(fmt_compacto),
                                   "CV": t["cv"].map(fmt_num), "Crescimento": t["crescimento"].map(fmt_num)}),
                     hide_index=True, width="stretch", height=320)

with st.expander("Comparação entre K-Means e agrupamento hierárquico"):
    cruz = pd.crosstab(agr["nome_grupo"], agr["grupo_hierarquico"].map(lambda g: f"Hierárquico {g + 1}")).reindex(ordem)
    st.dataframe(cruz, width="stretch")
    st.caption("Cada célula mostra quantos municípios de um grupo do K-Means caíram em cada grupo do hierárquico. "
               "Os dois métodos concordam nos extremos (maior porte, maior instabilidade) e divergem no meio.")

st.info("Os grupos descrevem padrões de **registro** da produção ambulatorial. Eles não são uma classificação da "
        "qualidade dos serviços de saúde dos municípios.")
