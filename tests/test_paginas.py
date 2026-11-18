"""Todas as páginas executam sem erro e as interações principais funcionam (AppTest do Streamlit)."""
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils.config import PAGINA, RAIZ

TERESINA, PICOS = "221100", "220800"


def iniciar():
    return AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120).run()


@pytest.mark.parametrize("pagina", list(PAGINA.values()))
def test_pagina_executa_sem_erro(pagina):
    at = iniciar()
    at.switch_page(pagina).run()
    assert not at.exception, [e.value for e in at.exception]


def test_filtros_da_visao_geral():
    at = iniciar()
    at.multiselect[0].set_value([2025]).run()
    at.multiselect[2].set_value([TERESINA]).run()
    assert not at.exception
    cards = " ".join(m.value for m in at.markdown if 'class="card"' in m.value)
    assert "de 224 municípios" in cards


def test_mapa_todos_os_indicadores():
    at = iniciar()
    at.switch_page(PAGINA["mapa"]).run()
    for opcao in at.selectbox[0].options:
        at.selectbox[0].set_value(opcao).run()
        assert not at.exception, opcao


def test_mapa_pesquisa_e_navegacao_para_analise():
    at = iniciar()
    at.switch_page(PAGINA["mapa"]).run()
    at.selectbox(key="busca_mapa").set_value(TERESINA).run()
    assert any("### Teresina" in m.value for m in at.markdown)
    at.button[0].click().run()
    assert at.selectbox(key="sel_analise").value == TERESINA


def test_previsoes_por_grupo_e_modelo():
    at = iniciar()
    at.switch_page(PAGINA["previsoes"]).run()
    at.radio[0].set_value("Agrupamento territorial").run()
    for modelo in ["Naive sazonal", "Regressão Linear", "Random Forest"]:
        at.selectbox[-1].set_value(modelo).run()
        assert not at.exception, modelo


def test_alertas_filtros():
    at = iniciar()
    at.switch_page(PAGINA["alertas"]).run()
    at.select_slider[0].set_value(pd.Timestamp("2026-06-01")).run()
    at.multiselect[0].set_value([TERESINA, PICOS]).run()
    at.multiselect[2].set_value(["Alerta"]).run()
    assert not at.exception
