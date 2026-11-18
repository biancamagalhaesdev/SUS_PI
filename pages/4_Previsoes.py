"""Resultados dos modelos supervisionados de previsão exportados pelo notebook."""
import numpy as np
import pandas as pd
import streamlit as st

from utils import charts
from utils.contexto import base, nomes_municipios, seletor_municipio
from utils.data_loader import carregar, carregar_json, exigir_dados
from utils.indicators import fmt_compacto, fmt_int, fmt_mes, fmt_num
from utils.ui import aviso_interpretacao, cabecalho, linha_de_cards

cabecalho("Previsões", "Produção registrada e previsões dos modelos supervisionados do projeto")
prod, cat, W = exigir_dados(base)
prev = exigir_dados(carregar, "previsoes")
met = exigir_dados(carregar, "metricas")
agr = exigir_dados(carregar, "agrupamentos")
meta = exigir_dados(carregar_json, "metadados")
info_agr = exigir_dados(carregar_json, "agrupamento_info")
nomes = nomes_municipios(cat)

modelos = list(dict.fromkeys(met["modelo"]))
escolhido = meta["modelo_escolhido"]

with st.container(border=True):
    c1, c2, c3 = st.columns([1, 1.6, 1.4])
    escopo = c1.radio("Analisar", ["Município", "Agrupamento territorial"], horizontal=False)
    with c2:
        if escopo == "Município":
            cod = seletor_municipio(cat, "sel_previsoes")
            membros, rotulo = [cod], nomes[cod]
        else:
            grupo = st.selectbox("Agrupamento", info_agr["ordem_grupos"])
            membros = agr.loc[agr["nome_grupo"] == grupo, "codigo_ibge"].tolist()
            rotulo = f"Grupo “{grupo}” ({len(membros)} municípios, soma)"
    modelo = c3.selectbox("Modelo", modelos, index=modelos.index(escolhido),
                          format_func=lambda m: f"{m} (escolhido na validação)" if m == escolhido else m)

p = prev[(prev["modelo"] == modelo) & prev["codigo_ibge"].isin(membros)]
p = p.groupby(["competencia", "periodo"], as_index=False)[["real", "previsto"]].sum(min_count=1)
historico = W.loc[membros].sum()
fora = p[p["periodo"].isin(["validação", "teste"])]
proximo = p[p["periodo"] == "próximo mês"]

erro = (fora["real"] - fora["previsto"]).abs()
positivos = fora["real"] > 0
mae = erro.mean()
mape = 100 * (erro[positivos] / fora.loc[positivos, "real"]).mean() if positivos.any() else np.nan
ultimo_mes = historico.index[-1]

linha_de_cards([
    ("Analisado", rotulo if len(rotulo) < 40 else rotulo[:38] + "…", escopo.lower()),
    ("Modelo utilizado", modelo, f"conjunto de atributos: {met.loc[met['modelo'] == modelo, 'conjunto_atributos'].iloc[0]}"),
    ("Último período observado", fmt_mes(ultimo_mes), f"{fmt_int(historico.iloc[-1])} procedimentos registrados"),
    ("Valor previsto", fmt_compacto(proximo["previsto"].iloc[0]) if not proximo.empty else "—",
     f"para {fmt_mes(meta['mes_previsto'] + '-01')}, um mês à frente"),
    ("Intervalo de previsão", "Não disponível", "os modelos usados não fornecem um intervalo confiável"),
    ("Erro histórico (fora da amostra)", f"MAE {fmt_compacto(mae)}",
     f"MAPE {fmt_num(mape, 1)}% · jan/2025 a ago/2026 ({int((~positivos).sum())} meses com zero fora do MAPE)"),
], por_linha=3)

mostrar_tudo = st.toggle("Mostrar histórico completo desde jan/2021", value=False)
hist = historico if mostrar_tudo else historico.loc["2024-01-01":]
st.plotly_chart(charts.real_previsto(hist, fora, proximo, f"Real × previsto — {rotulo}", modelo), width="stretch")
st.caption("Previsões de um mês à frente: cada valor previsto usa apenas a produção observada até o mês anterior. "
           "Validação (2025) com reajuste semestral; teste (jan–ago/2026) e mês seguinte com o modelo final treinado "
           "até dez/2025. Os meses de jun–ago/2026 foram atípicos, o que afeta o teste e a previsão do mês seguinte.")

# Comparação entre modelos ------------------------------------------------------------
st.markdown("### Comparação entre os modelos")
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(charts.barras_metricas(met, "MAE", "MAE por modelo — todos os municípios"), width="stretch")
with col2:
    st.plotly_chart(charts.barras_metricas(met, "MAPE", "MAPE (%) por modelo — todos os municípios"), width="stretch")

local = prev[prev["codigo_ibge"].isin(membros) & prev["periodo"].isin(["validação", "teste"])]
local = local.groupby(["modelo", "periodo", "competencia"], as_index=False)[["real", "previsto"]].sum()
local["erro"] = (local["real"] - local["previsto"]).abs()
mae_local = local.groupby(["modelo", "periodo"], as_index=False)["erro"].mean().rename(columns={"erro": "MAE"})
st.plotly_chart(charts.barras_metricas(mae_local, "MAE", f"MAE por modelo — {rotulo}"), width="stretch")

tabela = met[["modelo", "periodo", "conjunto_atributos", "hiperparametros", "MAE", "RMSE", "MAPE", "R2", "n"]].copy()
tabela["modelo"] = [f"{m} ★" if m == escolhido else m for m in tabela["modelo"]]
st.dataframe(tabela.rename(columns={"modelo": "Modelo", "periodo": "Período", "conjunto_atributos": "Atributos",
                                    "hiperparametros": "Hiperparâmetros", "R2": "R²", "MAPE": "MAPE (%)"})
             .style.format({"MAE": lambda v: fmt_num(v, 1), "RMSE": lambda v: fmt_num(v, 1),
                            "MAPE (%)": lambda v: fmt_num(v, 1), "R²": lambda v: fmt_num(v, 3)}),
             hide_index=True, width="stretch")
st.caption("★ modelo escolhido pelo menor MAE na validação. MAE e RMSE em procedimentos; o MAPE exclui meses com "
           "produção zero; o R² é alto para todos os modelos porque a escala varia muito entre municípios e deve ser "
           "lido com cautela. O naive sazonal repete a produção do mesmo mês do ano anterior.")
aviso_interpretacao()
