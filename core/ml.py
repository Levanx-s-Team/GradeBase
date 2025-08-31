# core/ml.py
from typing import List, Dict, Any, Tuple
import numpy as np

from django.db.models import QuerySet
from core.models import Nota

# scikit-learn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import r2_score, mean_squared_error, accuracy_score
from sklearn.model_selection import train_test_split

FEATURES = ["avance1", "avance2", "avance3", "participacion", "proyecto_final"]
PASSING_GRADE = 11.0
_MIN_TRAIN_ROWS = 10  # mínimo para entrenar


def _fetch_training_qs() -> QuerySet:
    # Entrenamos con cualquier registro que tenga nota_final y al menos 1 feature
    qs = Nota.objects.filter(nota_final__isnull=False)
    return qs


def _qs_to_xy_regression(qs: QuerySet) -> Tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for n in qs.select_related("estudiante", "seccion", "seccion__curso"):
        row = [getattr(n, f) for f in FEATURES]
        # Mantenemos NaN; el Imputer los resolverá
        X.append(row)
        y.append(n.nota_final)
    return np.array(X, dtype=float), np.array(y, dtype=float)


def _qs_to_xy_logistic(qs: QuerySet) -> Tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for n in qs.select_related("estudiante", "seccion", "seccion__curso"):
        row = [getattr(n, f) for f in FEATURES]
        X.append(row)
        y.append(1 if (n.nota_final is not None and n.nota_final < PASSING_GRADE) else 0)
    return np.array(X, dtype=float), np.array(y, dtype=int)


def train_linear_regression() -> Dict[str, Any]:
    qs = _fetch_training_qs()
    X, y = _qs_to_xy_regression(qs)
    if X.shape[0] < _MIN_TRAIN_ROWS:
        raise ValueError(f"Datos insuficientes para entrenar regresión (mínimo {_MIN_TRAIN_ROWS}).")

    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("lr", LinearRegression())
    ])
    # eval simple: si hay suficientes filas, hold-out 30%
    if X.shape[0] >= 20:
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=42)
        pipe.fit(Xtr, ytr)
        yhat = pipe.predict(Xte)
        r2 = r2_score(yte, yhat)
        rmse = mean_squared_error(yte, yhat, squared=False)
        n_train = Xtr.shape[0]
    else:
        pipe.fit(X, y)
        yhat = pipe.predict(X)
        r2 = r2_score(y, yhat)
        rmse = mean_squared_error(y, yhat, squared=False)
        n_train = X.shape[0]

    return {"model": pipe, "r2": float(r2), "rmse": float(rmse), "n_train": int(n_train)}


def train_logistic_regression() -> Dict[str, Any]:
    qs = _fetch_training_qs()
    X, y = _qs_to_xy_logistic(qs)
    # Necesitamos positivo/negativo
    if X.shape[0] < _MIN_TRAIN_ROWS or len(set(y.tolist())) < 2:
        raise ValueError("Datos insuficientes o sin clases para entrenar logística.")

    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler(with_mean=False)),  # robusto a columnas con var baja
        ("lg", LogisticRegression(max_iter=200, random_state=42))
    ])
    if X.shape[0] >= 20:
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
        pipe.fit(Xtr, ytr)
        ypred = pipe.predict(Xte)
        acc = accuracy_score(yte, ypred)
        n_train = Xtr.shape[0]
    else:
        pipe.fit(X, y)
        ypred = pipe.predict(X)
        acc = accuracy_score(y, ypred)
        n_train = X.shape[0]

    return {"model": pipe, "accuracy": float(acc), "n_train": int(n_train)}


def _pred_input_from_seccion(seccion) -> List[Dict[str, Any]]:
    """
    Regresa filas con features para todos los Nota de la sección dada.
    """
    notas = Nota.objects.filter(seccion=seccion).select_related("estudiante", "seccion", "seccion__curso")
    rows = []
    for n in notas:
        rows.append({
            "pk": n.pk,
            "codigo": n.estudiante.codigo,
            "nombre": f"{n.estudiante.nombre} {n.estudiante.apellido}",
            "curso": n.seccion.curso.codigo,
            "seccion": n.seccion.nombre,
            "features": [getattr(n, f) for f in FEATURES],
        })
    return rows


def predict_final_for_seccion(seccion) -> Dict[str, Any]:
    bundle = train_linear_regression()
    model = bundle["model"]

    rows = _pred_input_from_seccion(seccion)
    if not rows:
        raise ValueError("No hay notas en la sección seleccionada.")

    X = np.array([r["features"] for r in rows], dtype=float)
    yhat = model.predict(X)
    # limitar a 0..20
    yhat = np.clip(yhat, 0.0, 20.0)

    preds = []
    for r, p in zip(rows, yhat):
        preds.append({
            "codigo": r["codigo"],
            "estudiante": r["nombre"],
            "curso": r["curso"],
            "seccion": r["seccion"],
            "pred_nota_final": round(float(p), 2),
        })

    return {
        "metrics": {"r2": bundle["r2"], "rmse": bundle["rmse"], "n_train": bundle["n_train"]},
        "predictions": preds
    }


def predict_risk_for_seccion(seccion) -> Dict[str, Any]:
    bundle = train_logistic_regression()
    model = bundle["model"]

    rows = _pred_input_from_seccion(seccion)
    if not rows:
        raise ValueError("No hay notas en la sección seleccionada.")

    X = np.array([r["features"] for r in rows], dtype=float)
    proba = model.predict_proba(X)[:, 1]  # prob de desaprobar (<11)
    preds = []
    for r, p in zip(rows, proba):
        riesgo_txt = "ALTO" if p >= 0.6 else ("MEDIO" if p >= 0.3 else "BAJO")
        preds.append({
            "codigo": r["codigo"],
            "estudiante": r["nombre"],
            "curso": r["curso"],
            "seccion": r["seccion"],
            "prob_desaprobacion": round(float(p), 3),
            "riesgo": riesgo_txt
        })

    return {
        "metrics": {"accuracy": bundle["accuracy"], "n_train": bundle["n_train"]},
        "predictions": preds
    }
