"""Mapa interativo do Piauí: indicadores por município, pesquisa, destaque de alertas e painel lateral."""
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from utils import charts
from utils.config import NIVEIS, PAGINA
from utils.contexto import abrir_analise, base, definir_municipio, municipio_atual, nomes_municipios
from utils.data_loader import carregar, carregar_geojson, carregar_json, exigir_dados
from utils.indicators import fmt_compacto, fmt_int, fmt_mes, fmt_num, fmt_pct, indicadores_periodo
from utils.maps import SEQUENCIAL, colorir_categorias, colorir_niveis, colorir_quantis, colorir_variacao, construir_mapa
from utils.ui import aviso_interpretacao, cabecalho, selo_nivel

cabecalho("Mapa Interativo do Piauí",
          "Passe o mouse sobre um município para ver o resumo; clique para abrir o painel com os detalhes")
prod, cat, W = exigir_dados(base)
geo = exigir_dados(carregar_geojson)
ind = exigir_dados(carregar, "indicadores_alerta")
ev = exigir_dados(carregar, "anomalias")
agr = exigir_dados(carregar, "agrupamentos")
prev = exigir_dados(carregar, "previsoes")
info_agr = exigir_dados(carregar_json, "agrupamento_info")
nomes = nomes_municipios(cat)
meses = list(W.columns)

INDICADORES = {
    "Produção ambulatorial total": "Soma da produção registrada no período selecionado.",
    "Variação percentual da produção": ("Total do período comparado ao período imediatamente anterior de mesma duração. "
                                        "Fica indisponível quando esse período anterior não existe na base."),
    "Média mensal de produção": "Média mensal da produção registrada no período selecionado.",
    "Volatilidade da produção (CV)": "Coeficiente de variação (desvio padrão ÷ média) dos meses do período.",
    "Desvio em relação à previsão": ("Classificação do desvio entre a produção registrada e a prevista pelo modelo "
                                     "escolhido no notebook, no último mês do período. Há previsões apenas de jan/2025 a ago/2026."),
    "Grupo territorial (agrupamento)": "Grupo do K-Means, calculado com as características de 2021–2024.",
    "Quantidade de anomalias identificadas": ("Número de meses do período em que o Isolation Forest classificou a "
                                              "produção como Atenção ou Alerta."),
}


def ao_buscar():
    escolha = st.session_state["busca_mapa"]
    if escolha:
        definir_municipio(escolha)
        st.session_state["zoom_mapa"] = True


# Controles ---------------------------------------------------------------------------
with st.container(border=True):
    c1, c2 = st.columns([1.3, 2])
    indicador = c1.selectbox("Indicador do mapa", list(INDICADORES))
    ini, fim = c2.select_slider("Período", options=meses, value=(meses[0], meses[-1]), format_func=fmt_mes)
    c3, c4 = st.columns([2, 1.3])
    c3.selectbox("Pesquisar município", cat["codigo_ibge"], index=None, format_func=nomes.get,
                 placeholder="Digite o nome do município", key="busca_mapa", on_change=ao_buscar)
    destacar = c4.toggle("Destacar municípios em alerta", value=True,
                         help=f"Contorno vermelho nos municípios com classificação geral Alerta em {fmt_mes(fim)}.")

# Valores do indicador ----------------------------------------------------------------
tab = indicadores_periodo(W, ini, fim)
no_fim = ind[ind["competencia"] == fim].set_index("codigo_ibge")
aviso = None
if indicador == "Produção ambulatorial total":
    valor = tab["total"]
    cores, legenda = colorir_quantis(valor, fmt_compacto)
    texto = valor.map(lambda v: f"{fmt_int(v)} procedimentos")
elif indicador == "Variação percentual da produção":
    valor = tab["variacao"]
    cores, legenda = colorir_variacao(valor, lambda v: fmt_pct(v, 0))
    texto = valor.map(lambda v: fmt_pct(v))
    if valor.isna().all():
        aviso = ("A variação não pode ser calculada para este período, porque não há na base um período anterior "
                 "de mesma duração. Encurte o período ou mova o início para depois de jan/2021.")
elif indicador == "Média mensal de produção":
    valor = tab["media"]
    cores, legenda = colorir_quantis(valor, fmt_compacto)
    texto = valor.map(lambda v: f"{fmt_int(v)} procedimentos/mês")
elif indicador == "Volatilidade da produção (CV)":
    valor = tab["cv"]
    cores, legenda = colorir_quantis(valor, lambda v: fmt_num(v))
    texto = valor.map(lambda v: f"CV de {fmt_num(v)}")
elif indicador == "Desvio em relação à previsão":
    nivel = no_fim["nivel_desvio"].reindex(tab.index)
    desvio = no_fim["desvio_log"].reindex(tab.index)
    cores, legenda = colorir_niveis(nivel)
    texto = pd.Series([f"{n} ({fmt_pct(np.expm1(d), 0)} em relação ao previsto)" if pd.notna(n) else "sem previsão"
                       for n, d in zip(nivel, desvio)], index=tab.index)
    if nivel.isna().all():
        aviso = (f"Não há previsões para {fmt_mes(fim)}. As previsões fora da amostra cobrem jan/2025 a ago/2026; "
                 "ajuste o fim do período.")
elif indicador == "Grupo territorial (agrupamento)":
    grupo = agr.set_index("codigo_ibge")["nome_grupo"].reindex(tab.index)
    cores, legenda = colorir_categorias(grupo, info_agr["ordem_grupos"])
    texto = grupo.fillna("sem grupo")
else:
    periodo = ind[ind["competencia"].between(ini, fim)]
    contagem = periodo[periodo["nivel_anomalia"].isin(["Atenção", "Alerta"])].groupby("codigo_ibge").size()
    contagem = contagem.reindex(tab.index, fill_value=0)
    classes = pd.cut(contagem, [-1, 0, 1, 2, 4, np.inf], labels=["0", "1", "2", "3 a 4", "5 ou mais"]).astype(str)
    ordem = ["0", "1", "2", "3 a 4", "5 ou mais"]
    cores, legenda = colorir_categorias(classes, ordem, dict(zip(ordem, SEQUENCIAL[:5])))
    legenda = [(c, f"{t} mês(es)") for c, t in legenda]
    texto = contagem.map(lambda v: f"{v} mês(es) com anomalia")

tabela = pd.DataFrame({"codigo_ibge": tab.index, "cor": cores.reindex(tab.index).values,
                       "valor_fmt": texto.reindex(tab.index).values})
em_alerta = set(no_fim.index[no_fim["nivel_geral"] == "Alerta"]) if destacar else set()
selecionado = municipio_atual()
zoom = st.session_state.pop("zoom_mapa", False)

# Mapa e painel -----------------------------------------------------------------------
if aviso:
    st.info(aviso)
col_mapa, col_painel = st.columns([2.1, 1])
with col_mapa:
    mapa = construir_mapa(geo, tabela, indicador, legenda, destaque=em_alerta,
                          selecionado=selecionado, enquadrar=zoom)   # aproxima só quando vem da pesquisa
    saida = st_folium(mapa, key="mapa_pi", height=620, use_container_width=True,
                      returned_objects=["last_active_drawing"])
    st.caption(f"**{indicador}:** {INDICADORES[indicador]} Período: {fmt_mes(ini)} a {fmt_mes(fim)}.")

clique = (saida or {}).get("last_active_drawing")
if clique and clique.get("properties", {}).get("codigo_ibge"):
    cod = clique["properties"]["codigo_ibge"]
    if cod != st.session_state.get("ultimo_clique"):
        st.session_state["ultimo_clique"] = cod
        definir_municipio(cod)
        st.rerun()

with col_painel:
    cod = municipio_atual()
    if not cod:
        st.info("Clique em um município no mapa ou use a pesquisa para ver os detalhes.")
    else:
        serie = W.loc[cod]
        t = tab.loc[cod]
        g = agr.set_index("codigo_ibge")["nome_grupo"].get(cod, "—")
        situacao = no_fim["nivel_geral"].get(cod)
        with st.container(border=True):
            st.markdown(f"### {nomes[cod]}")
            st.markdown(f"Grupo territorial: **{g}**")
            if isinstance(situacao, str):
                st.markdown(f"Situação em {fmt_mes(fim)}: {selo_nivel(situacao)}", unsafe_allow_html=True)
            m1, m2 = st.columns(2)
            m1.metric("Produção no período", fmt_compacto(t["total"]))
            m2.metric("Média mensal", fmt_compacto(t["media"]))
            m3, m4 = st.columns(2)
            m3.metric("Variação", fmt_pct(t["variacao"]), help=INDICADORES["Variação percentual da produção"])
            m4.metric("Volatilidade (CV)", fmt_num(t["cv"]))
            fig = charts.linha_mensal(serie, "Evolução histórica", media_movel=False)
            fig.update_layout(height=230, margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
            st.plotly_chart(fig, width="stretch")

            p = prev[(prev["codigo_ibge"] == cod) & prev["escolhido"].astype(bool) & (prev["periodo"] == "próximo mês")]
            if not p.empty:
                st.markdown(f"**Previsão para {fmt_mes(p['competencia'].iloc[0])}** ({p['modelo'].iloc[0]}): "
                            f"{fmt_int(p['previsto'].iloc[0])} procedimentos")

            evm = ev[(ev["codigo_ibge"] == cod) & ev["competencia"].between(ini, fim)]
            st.markdown(f"**Alertas no período:** {len(evm)} ocorrência(s)")
            for _, r in evm.head(3).iterrows():
                st.markdown(f"{selo_nivel(r['classificacao'])} {fmt_mes(r['competencia'])} — {r['indicador']} "
                            f"({r['intensidade']})", unsafe_allow_html=True)
            st.caption("Principais grupos de procedimentos: não disponíveis na base utilizada.")
            if st.button("Abrir análise detalhada", type="primary", width="stretch"):
                abrir_analise(cod, PAGINA["municipal"])

with st.expander("Como ler o mapa"):
    st.markdown(
        "- As cores seguem a legenda no canto inferior esquerdo do mapa; municípios em cinza não têm valor para o indicador.\n"
        "- Para produção, média e volatilidade, as cores dividem os municípios em faixas de tamanho parecido (quantis), "
        "porque a produção varia de poucas unidades a milhões de procedimentos.\n"
        "- O contorno vermelho marca municípios com classificação geral **Alerta** no último mês do período, segundo os "
        "critérios descritos na página Alertas Analíticos.\n"
        "- A associação entre dados e polígonos é feita pelo código IBGE do município, não pelo nome.")
aviso_interpretacao()
