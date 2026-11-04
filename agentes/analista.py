from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

VARIABLES_CHURN = ["visitas_total", "visitas_14d", "visitas_14d_previas", "tendencia",
                   "dias_sin_venir", "reservas", "tasa_cancelacion", "series", "aperturas_app"]
VARIABLES_SEGMENTO = ["visitas_total", "series", "reservas", "aperturas_app"]


class AgenteAnalista:
    """Fase 4 - Análisis y machine learning.

    - patron_aforo: aforo promedio por día de la semana y hora (base para "mejor hora").
    - entrenar_churn: Random Forest que predice quién no vendrá en los próximos 14 días.
    - segmentar: K-Means para agrupar socios por comportamiento.
    - recomendar_clases: filtrado colaborativo usuario-usuario.
    """

    def __init__(self, custodio):
        self.custodio = custodio
        self.patron = None
        self.modelo_churn = None

    def patron_aforo(self):
        chk = self.custodio.eventos().query("tipo == 'checkin'").copy()
        chk["dia_semana"] = chk.ts.dt.dayofweek
        n_fechas = chk.groupby("dia_semana").fecha.nunique()
        self.patron = (chk.groupby(["dia_semana", "hora"]).size().unstack(fill_value=0)
                       .reindex(columns=range(6, 22), fill_value=0).div(n_fechas, axis=0))
        return self.patron

    def mejor_hora(self, dia_semana, cerca_de=None):
        fila = self.patron.loc[dia_semana]
        if cerca_de is not None:
            fila = fila[abs(fila.index - cerca_de) <= 2]
        return int(fila.idxmin())

    def entrenar_churn(self):
        ev = self.custodio.eventos()
        corte = ev.ts.max() - timedelta(days=14)
        X = self.custodio.construir_features(hasta=corte)[VARIABLES_CHURN]
        volvieron = set(ev[(ev.tipo == "checkin") & (ev.ts >= corte)].pid)
        y = (~X.index.isin(volvieron)).astype(int)

        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
        self.modelo_churn = RandomForestClassifier(
            n_estimators=200, max_depth=6, class_weight="balanced", random_state=0).fit(X_tr, y_tr)
        prob = self.modelo_churn.predict_proba(X_te)[:, 1]
        pred = prob >= 0.5
        return {
            "auc": roc_auc_score(y_te, prob),
            "precision": precision_score(y_te, pred),
            "recall": recall_score(y_te, pred),
            "tasa_abandono_real": y.mean(),
            "importancias": pd.Series(self.modelo_churn.feature_importances_, index=VARIABLES_CHURN)
                              .sort_values(ascending=False),
        }

    def predecir_churn(self, features):
        return pd.Series(self.modelo_churn.predict_proba(features[VARIABLES_CHURN])[:, 1],
                         index=features.index, name="riesgo_abandono")

    def segmentar(self, features, k=4):
        X = StandardScaler().fit_transform(features[VARIABLES_SEGMENTO])
        clusters = pd.Series(KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X),
                             index=features.index)
        centros = features[VARIABLES_SEGMENTO].groupby(clusters).mean()

        # Ponerle nombre a cada cluster según su rasgo más marcado.
        nombres, libres = {}, set(centros.index)
        for nombre, columna, menor in [("Ocasional", "visitas_total", True),
                                       ("Fuerza", "series", False),
                                       ("Amante de clases", "reservas", False)]:
            c = centros.loc[sorted(libres), columna].sort_values(ascending=menor).index[0]
            nombres[c] = nombre
            libres.remove(c)
        for c in libres:
            nombres[c] = "Constante"
        return clusters.map(nombres).rename("segmento")

    def recomendar_clases(self):
        ev = self.custodio.eventos()
        matriz = ev[ev.tipo == "clase_reservada"].groupby(["pid", "clase"]).size().unstack(fill_value=0)
        similitud = cosine_similarity(matriz.values)
        np.fill_diagonal(similitud, 0)
        puntajes = pd.DataFrame(similitud @ matriz.values, index=matriz.index, columns=matriz.columns)
        puntajes = puntajes.mask(matriz > 0)  # recomendar solo clases que aún no ha probado
        return puntajes.idxmax(axis=1, skipna=True).where(puntajes.notna().any(axis=1)).rename("clase_recomendada")
