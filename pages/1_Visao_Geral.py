"""Página inicial: indicadores gerais e gráficos da produção, com filtros."""
import pandas as pd
import streamlit as st

from utils import charts
from utils.config import MESES_NOME, NIVEIS
from utils.contexto import base, nomes_municipios
from utils.data_loader import carregar, exigir_dados
from utils.indicators import fmt_compacto, fmt_int, fmt_mes, fmt_pct, filtrar, variacao_ano_anterior
from utils.ui import aviso_interpretacao, cabecalho, linha_de_cards

cabecalho("Visão Geral", "Panorama da produção ambulatorial registrada nos municípios do Piauí")
prod, cat, W = exigir_dados(base)
ind = exigir_dados(carregar, "indicadores_alerta")
nomes = nomes_municipios(cat)

# Filtros -----------------------------------------------------------------------------
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([1, 1, 2.2, 1.3])
    anos = c1.multiselect("Ano", sorted(prod["competencia"].dt.year.unique()), placeholder="Todos")
    meses = c2.multiselect("Mês", list(MESES_NOME), format_func=MESES_NOME.get, placeholder="Todos")
    municipios = c3.multiselect("Município", cat["codigo_ibge"], format_func=nomes.get,
                                placeholder=f"Todos os {len(cat)} municípios")
    c4.selectbox("Grupo de procedimento", ["Não disponível na base"], disabled=True,
                 help="A consulta do DATASUS utilizada traz apenas o total de procedimentos por município e mês.")

f = filtrar(prod, anos, meses, municipios)
if f.empty:
    st.warning("Nenhum dado para a combinação de filtros selecionada.")
    st.stop()

# Cards -------------------------------------------------------------------------------
total = f["producao"].sum()
n_meses = f["competencia"].nunique()
var, n_comp = variacao_ano_anterior(prod, f)
ref = f["competencia"].max()
situacao = ind[(ind["competencia"] == ref) & ind["codigo_ibge"].isin(f["codigo_ibge"].unique())]["nivel_geral"]
n_alerta, n_atencao = int((situacao == "Alerta").sum()), int((situacao == "Atenção").sum())

linha_de_cards([
    ("Produção registrada", fmt_compacto(total), f"{fmt_int(total)} procedimentos aprovados"),
    ("Municípios analisados", fmt_int(f["codigo_ibge"].nunique()), f"de {len(cat)} municípios do Piauí"),
    ("Média mensal de produção", fmt_compacto(total / n_meses), f"média de {n_meses} meses selecionados"),
    ("Variação vs. ano anterior", fmt_pct(var),
     f"mesmos meses do ano anterior ({n_comp} meses comparados)" if n_comp else "sem ano anterior na base"),
    ("Municípios com alerta analítico", fmt_int(n_alerta), f"{n_atencao} em atenção · situação em {fmt_mes(ref)}"),
    ("Período de cobertura", f"{fmt_mes(f['competencia'].min())} a {fmt_mes(ref)}", "base completa: jan/2021 a ago/2026"),
])

# Gráficos ----------------------------------------------------------------------------
serie = f.groupby("competencia")["producao"].sum()
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(charts.linha_mensal(serie, "Evolução mensal da produção registrada",
                                        media_movel=not meses), width="stretch")
with col2:
    anual = f.groupby(f["competencia"].dt.year).agg(total=("producao", "sum"), meses=("competencia", "nunique"))
    anual = anual.reset_index().rename(columns={"competencia": "ano"})
    anual["rotulo"] = [f"{a} ({m} meses)" if m < 12 else str(a) for a, m in zip(anual["ano"], anual["meses"])]
    st.plotly_chart(charts.barras_anos(anual, "Produção registrada por ano"), width="stretch")
    if (anual["meses"] < 12).any():
        st.caption("Anos com menos de 12 meses selecionados aparecem com o número de meses entre parênteses; "
                   "compare-os com cautela.")

por_mun = f.groupby("codigo_ibge")["producao"].sum()
col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.histograma_log(por_mun, "Distribuição da produção entre os municípios",
                                          "Produção no período (escala logarítmica)"), width="stretch")
with col4:
    top = por_mun.sort_values(ascending=False).head(15)
    participacao = [f"{v / total:.1%}".replace(".", ",") for v in top.values]
    st.plotly_chart(charts.barras_horizontais([nomes[c] for c in top.index], top.values,
                                              "Municípios com maior produção no período", "Procedimentos",
                                              texto=participacao), width="stretch")

colunas_nivel = {"Queda expressiva": "nivel_queda", "Instabilidade mensal": "nivel_instabilidade",
                 "Desvio em relação à previsão": "nivel_desvio", "Anomalia (Isolation Forest)": "nivel_anomalia",
                 "Classificação geral": "nivel_geral"}
sel = ind[(ind["competencia"] == ref) & ind["codigo_ibge"].isin(f["codigo_ibge"].unique())]
contagem = pd.DataFrame({rot: sel[col].value_counts() for rot, col in colunas_nivel.items()}).T.reindex(columns=NIVEIS).fillna(0)
st.plotly_chart(charts.barras_niveis(contagem, f"Distribuição dos indicadores de atenção territorial — {fmt_mes(ref)}"),
                width="stretch")
st.caption("Municípios sem valor em um indicador (por exemplo, sem previsão fora de 2025–2026) não entram na contagem "
           "desse indicador. Critérios na página Alertas Analíticos.")
aviso_interpretacao()
