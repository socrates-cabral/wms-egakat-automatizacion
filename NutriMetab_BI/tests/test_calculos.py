"""
test_calculos.py — Tests unitarios para calculos_nutri.py
Ejecutar con: py -m pytest tests/ -v
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

import pytest
from src.procesamiento.calculos_nutri import (
    calcular_imc,
    clasificar_imc,
    calcular_tmb,
    calcular_get,
    calcular_macros,
    evaluar_paciente,
    Sexo,
    NivelActividad,
)


# ── IMC ────────────────────────────────────────────────────────

class TestIMC:
    def test_imc_normal(self):
        assert calcular_imc(70, 1.75) == pytest.approx(22.86, abs=0.01)

    def test_imc_sobrepeso(self):
        assert calcular_imc(85, 1.75) == pytest.approx(27.76, abs=0.01)

    def test_imc_talla_cero_lanza_error(self):
        with pytest.raises(ValueError):
            calcular_imc(70, 0)

    def test_imc_talla_negativa_lanza_error(self):
        with pytest.raises(ValueError):
            calcular_imc(70, -1.75)


# ── Clasificación IMC ──────────────────────────────────────────

class TestClasificacionIMC:
    @pytest.mark.parametrize("imc,esperado", [
        (17.0, "Bajo peso"),
        (22.0, "Normal"),
        (27.5, "Sobrepeso"),
        (32.0, "Obesidad I"),
        (37.0, "Obesidad II"),
        (42.0, "Obesidad III"),
    ])
    def test_clasificaciones(self, imc, esperado):
        assert clasificar_imc(imc) == esperado


# ── TMB (Mifflin-St Jeor) ─────────────────────────────────────

class TestTMB:
    def test_tmb_masculino(self):
        # 10*78 + 6.25*175 - 5*35 + 5 = 780 + 1093.75 - 175 + 5 = 1703.75
        assert calcular_tmb(78, 175, 35, Sexo.MASCULINO) == pytest.approx(1703.75, abs=0.1)

    def test_tmb_femenino(self):
        # 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
        assert calcular_tmb(60, 165, 30, Sexo.FEMENINO) == pytest.approx(1320.25, abs=0.1)


# ── GET ────────────────────────────────────────────────────────

class TestGET:
    def test_get_sedentario(self):
        assert calcular_get(1700, NivelActividad.SEDENTARIO) == pytest.approx(2040.0, abs=0.1)

    def test_get_muy_activo(self):
        assert calcular_get(1700, NivelActividad.MUY_ACTIVO) == pytest.approx(3230.0, abs=0.1)


# ── Macros ─────────────────────────────────────────────────────

class TestMacros:
    def test_macros_valores_positivos(self):
        macros = calcular_macros(70, 2000)
        assert macros["proteina_g"]     > 0
        assert macros["carbohidrato_g"] > 0
        assert macros["grasa_g"]        > 0

    def test_proteina_es_16g_por_kg(self):
        macros = calcular_macros(80, 2500)
        assert macros["proteina_g"] == pytest.approx(128.0, abs=0.1)


# ── Pipeline completo ──────────────────────────────────────────

class TestEvaluarPaciente:
    def test_pipeline_retorna_resultado(self):
        r = evaluar_paciente(
            peso_kg=78,
            talla_m=1.75,
            edad=35,
            sexo=Sexo.MASCULINO,
            nivel_actividad=NivelActividad.MODERADO,
        )
        assert r.imc > 0
        assert r.tmb_kcal > 0
        assert r.get_kcal > r.tmb_kcal
        assert r.categoria_imc in [
            "Bajo peso", "Normal", "Sobrepeso",
            "Obesidad I", "Obesidad II", "Obesidad III",
        ]

    def test_get_mayor_a_tmb(self):
        r = evaluar_paciente(65, 1.60, 28, Sexo.FEMENINO, NivelActividad.ACTIVO)
        assert r.get_kcal > r.tmb_kcal
