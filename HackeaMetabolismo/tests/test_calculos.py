"""
test_calculos.py — Tests unitarios para el core de HackeaMetabolismo
py -m pytest tests/ -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.core.calculos import calcular_tmb, calcular_tdee, calcular_macros, calcular_tef, calcular_plan
from src.core.calculos_40plus import calcular_whtr, clasificar_whtr, evaluar_40plus
from src.core.plateau import detectar_plateau, calcular_dias_para_meta
import pandas as pd
from datetime import datetime, timedelta


class TestTMB:
    def test_masculino(self):
        # 10*80 + 6.25*175 - 5*35 + 5 = 800 + 1093.75 - 175 + 5 = 1723.75
        assert calcular_tmb(80, 175, 35, "M") == pytest.approx(1723.75, abs=0.1)

    def test_femenino(self):
        # 10*65 + 6.25*165 - 5*30 - 161 = 650 + 1031.25 - 150 - 161 = 1370.25
        assert calcular_tmb(65, 165, 30, "F") == pytest.approx(1370.25, abs=0.1)


class TestTDEE:
    def test_factor_actividad(self):
        tmb  = 1700.0
        tdee = calcular_tdee(tmb, "moderado", 35)
        assert tdee == pytest.approx(1700 * 1.55, abs=1)

    def test_factor_corrector_40(self):
        tmb  = 1700.0
        tdee = calcular_tdee(tmb, "moderado", 45)
        assert tdee == pytest.approx(1700 * 1.55 * 0.97, abs=1)

    def test_factor_corrector_60(self):
        tdee = calcular_tdee(1700, "moderado", 62)
        assert tdee == pytest.approx(1700 * 1.55 * 0.92, abs=1)


class TestMacros:
    def test_proteina_mayor_40(self):
        macros = calcular_macros(80, 2000, 45)
        assert macros["proteina_g"] == pytest.approx(80 * 2.0, abs=0.1)

    def test_proteina_menor_40(self):
        macros = calcular_macros(80, 2000, 35)
        assert macros["proteina_g"] == pytest.approx(80 * 1.6, abs=0.1)

    def test_cho_positivo(self):
        macros = calcular_macros(70, 2000, 30)
        assert macros["cho_g"] >= 0


class TestTEF:
    def test_tef_positivo(self):
        tef = calcular_tef(150, 200, 70)
        assert tef > 0

    def test_proteina_mayor_tef(self):
        tef_prot  = calcular_tef(200, 0, 0)
        tef_grasa = calcular_tef(0, 0, 100)
        assert tef_prot > tef_grasa


class TestPlan:
    def test_deficit_limitado(self):
        plan = calcular_plan(80, 175, 35, "M", "moderado", "perder_grasa", deficit_deseado=900)
        assert plan.deficit_real <= 750
        assert len(plan.advertencias) > 0

    def test_kcal_minimo_respetado(self):
        plan = calcular_plan(50, 155, 30, "F", "sedentario", "perder_grasa", deficit_deseado=750)
        assert plan.kcal_objetivo >= 1200

    def test_mantenimiento(self):
        plan = calcular_plan(80, 175, 35, "M", "moderado", "mantenimiento")
        assert plan.deficit_real == 0
        assert plan.kcal_objetivo == plan.tdee


class TestWHtR:
    def test_calculo(self):
        assert calcular_whtr(88, 175) == pytest.approx(0.503, abs=0.001)

    def test_meta_bajo_riesgo(self):
        clasif, sev = clasificar_whtr(0.48)
        assert clasif == "Bajo riesgo"
        assert sev == "success"

    def test_riesgo_alto(self):
        clasif, sev = clasificar_whtr(0.65)
        assert "alto" in clasif.lower()


class TestPlateau:
    def test_sin_plateau_pocos_datos(self):
        df = pd.DataFrame({"fecha": ["2026-01-01"], "peso_kg": [80.0]})
        r  = detectar_plateau(df)
        assert not r.detectado

    def test_plateau_detectado(self):
        fechas = [(datetime(2026,1,1) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(25)]
        pesos  = [80.0] * 25
        df     = pd.DataFrame({"fecha": fechas, "peso_kg": pesos})
        r      = detectar_plateau(df)
        assert r.detectado

    def test_sin_plateau_bajando(self):
        fechas = [(datetime(2026,1,1) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(25)]
        pesos  = [80.0 - i * 0.1 for i in range(25)]
        df     = pd.DataFrame({"fecha": fechas, "peso_kg": pesos})
        r      = detectar_plateau(df)
        assert not r.detectado

    def test_dias_para_meta(self):
        dias = calcular_dias_para_meta(85, 80, 500)
        assert dias == pytest.approx(77, abs=2)
