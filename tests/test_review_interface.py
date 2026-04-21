"""Tests para la interfaz de revisión humana (review_interface.py) — HU-02."""

import os
import tempfile

import pandas as pd
import pytest

from src.review_interface import (
    apply_override,
    export_to_csv,
    finalize_review,
    flag_significant_deviations,
    prepare_review_table,
    print_review_table,
)


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _base_requirements():
    """DataFrame de requerimientos de insumos de muestra."""
    return pd.DataFrame([
        {"insumo": "Pan", "unidad_medida": "unidad", "cantidad_requerida": 100.0},
        {"insumo": "Carne", "unidad_medida": "gramos", "cantidad_requerida": 1500.0},
        {"insumo": "Papa", "unidad_medida": "gramos", "cantidad_requerida": 800.0},
    ])


# ---------------------------------------------------------------------------
# prepare_review_table
# ---------------------------------------------------------------------------


class TestPrepareReviewTable:
    def test_returns_expected_columns(self):
        df = prepare_review_table(_base_requirements())
        expected = {
            "insumo", "unidad_medida", "cantidad_sugerida_ia",
            "cantidad_final", "desviacion_significativa", "finalizada",
        }
        assert set(df.columns) == expected

    def test_cantidad_final_equals_sugerida_initially(self):
        df = prepare_review_table(_base_requirements())
        pd.testing.assert_series_equal(
            df["cantidad_sugerida_ia"].reset_index(drop=True),
            df["cantidad_final"].reset_index(drop=True),
            check_names=False,
        )

    def test_desviation_flag_false_initially(self):
        df = prepare_review_table(_base_requirements())
        assert not df["desviacion_significativa"].any()

    def test_finalizada_false_initially(self):
        df = prepare_review_table(_base_requirements())
        assert not df["finalizada"].any()

    def test_row_count_preserved(self):
        req = _base_requirements()
        df = prepare_review_table(req)
        assert len(df) == len(req)

    def test_raises_on_missing_columns(self):
        bad = pd.DataFrame([{"insumo": "Pan", "unidad_medida": "unidad"}])
        with pytest.raises(ValueError, match="Columnas faltantes"):
            prepare_review_table(bad)


# ---------------------------------------------------------------------------
# apply_override
# ---------------------------------------------------------------------------


class TestApplyOverride:
    def _review(self):
        return prepare_review_table(_base_requirements())

    def test_updates_cantidad_final(self):
        df = apply_override(self._review(), "Pan", 200.0)
        assert df.loc[df["insumo"] == "Pan", "cantidad_final"].values[0] == 200.0

    def test_does_not_mutate_sugerida(self):
        original = self._review()
        updated = apply_override(original, "Pan", 200.0)
        assert updated.loc[updated["insumo"] == "Pan", "cantidad_sugerida_ia"].values[0] == 100.0

    def test_does_not_change_other_rows(self):
        df = apply_override(self._review(), "Pan", 200.0)
        assert df.loc[df["insumo"] == "Carne", "cantidad_final"].values[0] == 1500.0

    def test_raises_on_negative_quantity(self):
        with pytest.raises(ValueError, match="negativa"):
            apply_override(self._review(), "Pan", -10.0)

    def test_raises_on_unknown_insumo(self):
        with pytest.raises(ValueError, match="no encontrado"):
            apply_override(self._review(), "Insumo Inexistente", 10.0)

    def test_raises_if_already_finalized(self):
        df = finalize_review(self._review())
        with pytest.raises(RuntimeError, match="finalizada"):
            apply_override(df, "Pan", 50.0)

    def test_zero_override_is_valid(self):
        df = apply_override(self._review(), "Pan", 0.0)
        assert df.loc[df["insumo"] == "Pan", "cantidad_final"].values[0] == 0.0

    def test_does_not_mutate_input_dataframe(self):
        original = self._review()
        _ = apply_override(original, "Pan", 999.0)
        assert original.loc[original["insumo"] == "Pan", "cantidad_final"].values[0] == 100.0


# ---------------------------------------------------------------------------
# flag_significant_deviations
# ---------------------------------------------------------------------------


class TestFlagSignificantDeviations:
    def _review_with_override(self, insumo, nueva_cantidad):
        return apply_override(prepare_review_table(_base_requirements()), insumo, nueva_cantidad)

    def test_flags_deviation_above_threshold(self):
        # Pan sugerido = 100, final = 125 → 25 % desviación → debe marcar
        df = self._review_with_override("Pan", 125.0)
        assert df.loc[df["insumo"] == "Pan", "desviacion_significativa"].values[0]

    def test_does_not_flag_exact_match(self):
        df = self._review_with_override("Pan", 100.0)
        assert not df.loc[df["insumo"] == "Pan", "desviacion_significativa"].values[0]

    def test_does_not_flag_deviation_below_threshold(self):
        # Pan sugerido = 100, final = 115 → 15 % desviación → no debe marcar
        df = self._review_with_override("Pan", 115.0)
        assert not df.loc[df["insumo"] == "Pan", "desviacion_significativa"].values[0]

    def test_flags_exactly_at_threshold_plus_one(self):
        # 21 % de desviación → debe marcar
        df = self._review_with_override("Pan", 121.0)
        assert df.loc[df["insumo"] == "Pan", "desviacion_significativa"].values[0]

    def test_does_not_flag_at_exact_threshold(self):
        # Exactly 20 % desviación → no debe marcar (se usa >)
        df = self._review_with_override("Pan", 120.0)
        assert not df.loc[df["insumo"] == "Pan", "desviacion_significativa"].values[0]

    def test_flags_decrease_above_threshold(self):
        # Pan sugerido = 100, final = 75 → -25 % desviación → debe marcar
        df = self._review_with_override("Pan", 75.0)
        assert df.loc[df["insumo"] == "Pan", "desviacion_significativa"].values[0]

    def test_zero_suggestion_nonzero_final_is_flagged(self):
        req = pd.DataFrame([
            {"insumo": "Sal", "unidad_medida": "gramos", "cantidad_requerida": 0.0},
        ])
        df = prepare_review_table(req)
        df = apply_override(df, "Sal", 5.0)
        assert df.loc[df["insumo"] == "Sal", "desviacion_significativa"].values[0]

    def test_zero_suggestion_zero_final_not_flagged(self):
        req = pd.DataFrame([
            {"insumo": "Sal", "unidad_medida": "gramos", "cantidad_requerida": 0.0},
        ])
        df = prepare_review_table(req)
        assert not df.loc[df["insumo"] == "Sal", "desviacion_significativa"].values[0]

    def test_custom_threshold(self):
        req = _base_requirements()
        df = prepare_review_table(req)
        df = df.copy()
        df.loc[df["insumo"] == "Pan", "cantidad_final"] = 108.0
        # 8 % desviación: no marca con umbral 20 %, pero sí con umbral 5 %
        result_20 = flag_significant_deviations(df, threshold=0.20)
        result_5 = flag_significant_deviations(df, threshold=0.05)
        assert not result_20.loc[result_20["insumo"] == "Pan", "desviacion_significativa"].values[0]
        assert result_5.loc[result_5["insumo"] == "Pan", "desviacion_significativa"].values[0]


# ---------------------------------------------------------------------------
# finalize_review
# ---------------------------------------------------------------------------


class TestFinalizeReview:
    def test_sets_finalizada_to_true(self):
        df = finalize_review(prepare_review_table(_base_requirements()))
        assert df["finalizada"].all()

    def test_does_not_mutate_input(self):
        original = prepare_review_table(_base_requirements())
        _ = finalize_review(original)
        assert not original["finalizada"].any()

    def test_preserves_other_columns(self):
        original = prepare_review_table(_base_requirements())
        result = finalize_review(original)
        assert set(result.columns) == set(original.columns)


# ---------------------------------------------------------------------------
# export_to_csv
# ---------------------------------------------------------------------------


class TestExportToCsv:
    def test_creates_csv_file(self):
        df = finalize_review(prepare_review_table(_base_requirements()))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "lista_validada.csv")
            result = export_to_csv(df, path)
            assert os.path.exists(result)

    def test_csv_contains_expected_columns(self):
        df = finalize_review(prepare_review_table(_base_requirements()))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "lista_validada.csv")
            export_to_csv(df, path)
            loaded = pd.read_csv(path)
            expected_cols = {
                "insumo", "unidad_medida", "cantidad_sugerida_ia",
                "cantidad_final", "desviacion_significativa",
            }
            assert expected_cols.issubset(set(loaded.columns))

    def test_csv_row_count_matches(self):
        df = finalize_review(prepare_review_table(_base_requirements()))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "lista_validada.csv")
            export_to_csv(df, path)
            loaded = pd.read_csv(path)
            assert len(loaded) == len(df)

    def test_csv_values_are_correct(self):
        df = prepare_review_table(_base_requirements())
        df = apply_override(df, "Pan", 120.0)
        df = finalize_review(df)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.csv")
            export_to_csv(df, path)
            loaded = pd.read_csv(path)
            pan = loaded[loaded["insumo"] == "Pan"]
            assert pan["cantidad_sugerida_ia"].values[0] == pytest.approx(100.0)
            assert pan["cantidad_final"].values[0] == pytest.approx(120.0)

    def test_creates_parent_directories(self):
        df = finalize_review(prepare_review_table(_base_requirements()))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nested", "dir", "out.csv")
            result = export_to_csv(df, path)
            assert os.path.exists(result)


# ---------------------------------------------------------------------------
# print_review_table (smoke test)
# ---------------------------------------------------------------------------


class TestPrintReviewTable:
    def test_runs_without_error(self, capsys):
        df = prepare_review_table(_base_requirements())
        print_review_table(df)
        captured = capsys.readouterr()
        assert "TABLA COMPARATIVA" in captured.out
        assert "Pan" in captured.out

    def test_shows_alert_for_deviation(self, capsys):
        df = apply_override(prepare_review_table(_base_requirements()), "Pan", 200.0)
        print_review_table(df)
        captured = capsys.readouterr()
        assert ">20%" in captured.out
