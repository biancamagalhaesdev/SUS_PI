"""Análise detalhada de um município: indicadores, evolução, comparações e resumo analítico."""
import pandas as pd
import streamlit as st

from utils import charts
from utils.config import PAGINA
from utils.contexto import base, nomes_municipios, seletor_municipio
from utils.data_loader import carregar, exigir_dados
from utils.indicators import (fmt_compacto, fmt_int, fmt_mes, fmt_num, fmt_pct, indicadores_municipio,
                              indicadores_periodo, posicao_no_grupo, resumo_analitico, serie_indice)
from utils.ui import aviso_interpretacao, cabecalho, linha_de_cards, selo_nivel

cabecalho("Análise Municipal", "Situação detalhada da produção ambulatorial registrada em um município")
prod, cat, W = exigir_dados(base)
agr = exigir_dados(carregar, "agrupamentos")
ev = exigir_dados(carregar, "anomalias")
ind_alerta = exigir_dados(carregar, "indicadores_alerta")
prev = exigir_dados(carregar, "previsoes")
nomes = nomes_municipios(cat)

c1, c2 = st.columns([2, 1])
with c1:
    cod = seletor_municipio(cat, "sel_analise")
serie = W.loc[cod]
ind = indicadores_municipio(serie)
linha_agr = agr.set_index("codigo_ibge").loc[cod]
grupo = linha_agr["nome_grupo"]
c2.markdown(f"<br>Grupo territorial: **{grupo}**", unsafe_allow_html=True)

# Indicadores -------------------------------------------------------------------------
linha_de_cards([
    ("Produção total no período", fmt_compacto(ind["total"]), f"{fmt_int(ind['total'])} procedimentos, jan/2021 a ago/2026"),
    ("Média mensal", fmt_compacto(ind["media"]), "procedimentos por mês"),
    ("Tendência", ind["tendencia_texto"].capitalize(),
     f"mediana dos últimos 12 meses: {fmt_pct(ind['tendencia'])} vs. 12 anteriores"),
    ("Maior produção mensal", fmt_compacto(ind["maximo"]), fmt_mes(ind["mes_maximo"])),
    ("Menor produção mensal", fmt_compacto(ind["minimo"]), fmt_mes(ind["mes_minimo"])),
    ("Variabilidade", f"CV {fmt_num(ind['cv'])}", f"desvio padrão de {fmt_int(ind['desvio'])} procedimentos"),
], por_linha=3)

# Resumo analítico --------------------------------------------------------------------
cv_estado = indicadores_periodo(W, W.columns[0], W.columns[-1])["cv"]
frases = resumo_analitico(serie, ind, cv_estado, cv_estado.get(cod), posicao_no_grupo(agr, cod),
                          ev[ev["codigo_ibge"] == cod])
with st.container(border=True):
    st.markdown("#### Resumo analítico")
    st.markdown("\n".join(f"- {f}" for f in frases))
    st.caption("Frases geradas automaticamente por regras fixas a partir dos indicadores. Tendência: medianas dos últimos 12 "
               "meses e dos 12 anteriores, limiar de ±10%; "
               "variabilidade: quartis do CV dos municípios do estado; grupo: faixa interquartil das características de "
               "2021–2024; reduções e variações atípicas: critérios da página Alertas Analíticos.")

# Gráficos ----------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(charts.linha_mensal(serie, f"Evolução mensal — {nomes[cod]}",
                                        destaque=(pd.Timestamp("2026-05-16"), pd.Timestamp("2026-08-16"), "jun–ago/2026")),
                    width="stretch")
with col2:
    anual = serie.groupby(serie.index.year).agg(["sum", "count"]).reset_index()
    anual.columns = ["ano", "total", "meses"]
    anual["rotulo"] = [f"{a} ({m} meses)" if m < 12 else str(a) for a, m in zip(anual["ano"], anual["meses"])]
    st.plotly_chart(charts.barras_anos(anual, "Comparação entre anos"), width="stretch")

membros = agr.loc[agr["nome_grupo"] == grupo, "codigo_ibge"]
indice_grupo = W.loc[membros].apply(serie_indice, axis=1).median()
st.plotly_chart(charts.linhas_indice({nomes[cod]: serie_indice(serie), "Piauí (total do estado)": serie_indice(W.sum()),
                                      f"Mediana do grupo “{grupo}”": indice_grupo},
                                     "Comparação com o estado e com o grupo (índice: média do período = 100)"),
                width="stretch")
st.caption("O índice permite comparar trajetórias de escalas diferentes: cada série é dividida pela própria média.")

col3, col4 = st.columns(2)
with col3:
    st.markdown("#### Comparação das características (2021–2024)")
    variaveis = {"media_mensal": "Produção média mensal", "cv": "Coeficiente de variação",
                 "crescimento": "Crescimento 2021→2024", "amplitude_sazonal": "Amplitude sazonal"}
    comp = pd.DataFrame({"Município": linha_agr[list(variaveis)],
                         "Mediana do grupo": agr[agr["nome_grupo"] == grupo][list(variaveis)].median(),
                         "Mediana do estado": agr[list(variaveis)].median()}).rename(index=variaveis)
    st.dataframe(comp.style.format(lambda v: fmt_num(v, 2)), width="stretch")
with col4:
    st.markdown("#### Distribuição por grupo de procedimentos")
    st.info("Não disponível: a base utilizada contém apenas o total de procedimentos aprovados por município e mês.")
    p = prev[(prev["codigo_ibge"] == cod) & prev["escolhido"].astype(bool) & (prev["periodo"] == "próximo mês")]
    if not p.empty:
        st.markdown(f"**Previsão para {fmt_mes(p['competencia'].iloc[0])}** ({p['modelo'].iloc[0]}): "
                    f"{fmt_int(p['previsto'].iloc[0])} procedimentos")
        if st.button("Ver previsões deste município"):
            st.switch_page(PAGINA["previsoes"])

# Alertas -----------------------------------------------------------------------------
st.markdown("#### Alertas analíticos do município")
ultimo = ind_alerta[ind_alerta["codigo_ibge"] == cod].sort_values("competencia").iloc[-1]
st.markdown(f"Situação em {fmt_mes(ultimo['competencia'])}: {selo_nivel(ultimo['nivel_geral'])}",
            unsafe_allow_html=True)
evm = ev[ev["codigo_ibge"] == cod]
if evm.empty:
    st.success("Nenhum alerta ou ponto de atenção identificado no período.")
else:
    tabela = evm.assign(Mês=evm["competencia"].map(fmt_mes))[["Mês", "indicador", "classificacao", "intensidade", "justificativa"]]
    st.dataframe(tabela.rename(columns={"indicador": "Indicador", "classificacao": "Classificação",
                                        "intensidade": "Intensidade", "justificativa": "Justificativa"}),
                 hide_index=True, width="stretch", height=min(400, 38 * len(tabela) + 40))
aviso_interpretacao()
