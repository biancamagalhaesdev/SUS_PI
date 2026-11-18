"""Alertas analíticos: alterações relevantes no comportamento histórico da produção registrada."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import charts
from utils.config import COR_NIVEL, PAGINA
from utils.contexto import abrir_analise, base, nomes_municipios
from utils.data_loader import carregar, carregar_json, exigir_dados
from utils.indicators import fmt_int, fmt_mes, fmt_num, fmt_pct
from utils.ui import cabecalho, linha_de_cards

cabecalho("Alertas Analíticos",
          "Municípios com alterações estatísticas relevantes na produção registrada, que merecem investigação complementar")
prod, cat, W = exigir_dados(base)
ev = exigir_dados(carregar, "anomalias")
ind = exigir_dados(carregar, "indicadores_alerta")
lim = exigir_dados(carregar_json, "limites_alerta")
nomes = nomes_municipios(cat)
meses = [pd.Timestamp(m) for m in sorted(ind["competencia"].unique())]
INDICADORES = ["Queda expressiva", "Instabilidade mensal", "Desvio em relação à previsão", "Anomalia (Isolation Forest)"]

# Situação em um mês ------------------------------------------------------------------
ref = st.select_slider("Mês de referência para a situação dos municípios", options=meses, value=meses[-1],
                       format_func=fmt_mes)
situacao = ind[ind["competencia"] == ref]["nivel_geral"].value_counts()
linha_de_cards([
    ("Em alerta", fmt_int(situacao.get("Alerta", 0)), f"municípios em {fmt_mes(ref)}"),
    ("Em atenção", fmt_int(situacao.get("Atenção", 0)), f"municípios em {fmt_mes(ref)}"),
    ("Estáveis", fmt_int(situacao.get("Estável", 0)), "dentro dos parâmetros históricos"),
], por_linha=3)

por_mes = ev.groupby([ev["competencia"], "classificacao"]).size().unstack(fill_value=0)
fig = go.Figure()
for nivel in ["Atenção", "Alerta"]:
    if nivel in por_mes:
        fig.add_trace(go.Bar(x=por_mes.index, y=por_mes[nivel], name=nivel, marker_color=COR_NIVEL[nivel],
                             hovertemplate="%{x|%m/%Y}: %{y} ocorrências<extra></extra>"))
fig.update_layout(barmode="stack")
st.plotly_chart(charts._finalizar(fig, "Ocorrências de atenção e alerta por mês", "Mês de processamento",
                                  "Ocorrências", 300), width="stretch")
st.caption("Um mesmo município pode ter mais de uma ocorrência no mesmo mês, uma por indicador.")

# Tabela filtrável --------------------------------------------------------------------
st.markdown("### Ocorrências")
with st.container(border=True):
    c1, c2 = st.columns([1.5, 2])
    municipios = c1.multiselect("Município", cat["codigo_ibge"], format_func=nomes.get, placeholder="Todos")
    ini, fim = c2.select_slider("Período", options=meses, value=(meses[-12], meses[-1]), format_func=fmt_mes)
    c3, c4 = st.columns(2)
    tipos = c3.multiselect("Tipo de alerta", INDICADORES, placeholder="Todos")
    classes = c4.multiselect("Classificação", ["Alerta", "Atenção"], placeholder="Alerta e Atenção")

f = ev[ev["competencia"].between(ini, fim)]
if municipios:
    f = f[f["codigo_ibge"].isin(municipios)]
if tipos:
    f = f[f["indicador"].isin(tipos)]
if classes:
    f = f[f["classificacao"].isin(classes)]

st.caption(f"{fmt_int(len(f))} ocorrência(s) em {f['codigo_ibge'].nunique()} município(s). "
           "Selecione uma linha para abrir a análise do município.")
tabela = pd.DataFrame({"Município": f["municipio"], "Mês": f["competencia"].map(fmt_mes),
                       "Indicador": f["indicador"], "Intensidade": f["intensidade"],
                       "Classificação": f["classificacao"], "Justificativa analítica": f["justificativa"]})
selecao = st.dataframe(tabela, hide_index=True, width="stretch", height=430, on_select="rerun",
                       selection_mode="single-row", key="tabela_alertas",
                       column_config={"Justificativa analítica": st.column_config.TextColumn(width="large")})
linhas = selecao.selection.rows if selecao is not None else []
if linhas:
    cod = f.iloc[linhas[0]]["codigo_ibge"]
    if st.button(f"Abrir análise de {nomes[cod]}", type="primary"):
        abrir_analise(cod, PAGINA["municipal"])

# Critérios ---------------------------------------------------------------------------
with st.expander("Critérios de classificação", expanded=False):
    q, i, d, a = lim["queda"], lim["instabilidade"], lim["desvio"], lim["anomalia"]
    st.markdown(f"""
Todos os indicadores seguem a mesma regra: o valor de cada município em cada mês é comparado com a distribuição do
mesmo indicador em um **período de referência**. **Atenção**: {lim['regra']['atencao']}; **Alerta**: {lim['regra']['alerta']};
**Estável**: demais casos. A classificação geral do município no mês é a mais grave entre os indicadores.

| Indicador | Como é medido | Atenção | Alerta | Referência |
|---|---|---|---|---|
| Queda expressiva | Média dos últimos 3 meses ÷ mediana dos 12 meses anteriores | ≤ {fmt_pct(q['atencao'], 1, False)} | ≤ {fmt_pct(q['alerta'], 1, False)} | 2021–2024 ({fmt_int(q['n_referencia'])} casos) |
| Instabilidade mensal | Coeficiente de variação dos últimos 12 meses | ≥ {fmt_num(i['atencao'])} | ≥ {fmt_num(i['alerta'])} | 2021–2024 ({fmt_int(i['n_referencia'])} casos) |
| Desvio em relação à previsão | \\|log(1 + real) − log(1 + previsto)\\|, modelo {d['modelo']} | ≥ {fmt_num(d['atencao'])} | ≥ {fmt_num(d['alerta'])} | validação 2025 ({fmt_int(d['n_referencia'])} casos) |
| Anomalia (Isolation Forest) | Escore de anomalia a partir das variações em relação ao mês anterior, ao mesmo mês do ano anterior e à mediana dos 12 meses anteriores | ≥ {fmt_num(a['atencao'], 3)} | ≥ {fmt_num(a['alerta'], 3)} | {a['referencia_inicio'].replace('-', '/')} a 2024/12 ({fmt_int(a['n_referencia'])} casos) |

**Limitações dos critérios**
- Os limites são calculados com todos os municípios juntos. Como variações grandes são comuns nos municípios
  pequenos, uma mudança relativa moderada em um município grande e estável (por exemplo, a queda de cerca de 40% de
  Teresina em jun/2026) pode não ser classificada como atípica.
- A instabilidade usa os últimos 12 meses: um pico isolado mantém o município em atenção ou alerta por até um ano.
- O desvio em relação à previsão só existe de jan/2025 a ago/2026. Seus limites são altos porque os erros relativos do
  modelo já eram grandes nos municípios pequenos em 2025.
- Os percentis (95 e 99) e as janelas (3 e 12 meses) são decisões de projeto, documentadas e fixadas antes da análise.
""")

st.info("Os alertas indicam **alterações estatísticas na produção registrada**, como redução expressiva, variação "
        "atípica ou desvio em relação ao comportamento histórico. Eles não permitem afirmar que um município tem "
        "deficiência de atendimento, falta de profissionais ou qualquer situação assistencial; indicam apenas que o "
        "registro merece investigação complementar.")
