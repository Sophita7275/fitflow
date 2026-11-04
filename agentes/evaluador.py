import hashlib
import math
import random
from datetime import timedelta


class AgenteEvaluador:
    """Fase 5b - Mejora continua y evaluación del impacto.

    - kpis: indicadores de experiencia calculados con los datos reales almacenados.
    - asignar_grupo: reparte socios en A/B de forma estable (hash del pid).
    - experimento_ab: compara dos grupos con una prueba z de proporciones.
    """

    def kpis(self, eventos, perfiles, umbral_riesgo=0.6):
        fin, inicio = eventos.ts.max(), eventos.ts.min()
        semanas = (fin - inicio).days / 7
        chk = eventos[eventos.tipo == "checkin"]
        activos = chk[chk.ts >= fin - timedelta(days=14)].pid.nunique()
        reservas = (eventos.tipo == "clase_reservada").sum()
        return {
            "socios": len(perfiles),
            "retencion_14d": activos / len(perfiles),
            "visitas_por_semana": len(chk) / len(perfiles) / semanas,
            "tasa_cancelacion_clases": (eventos.tipo == "clase_cancelada").sum() / max(reservas, 1),
            "calificacion_media_clases": eventos.estrellas.mean(),
            "socios_en_riesgo": int((perfiles.riesgo_abandono >= umbral_riesgo).sum()),
        }

    @staticmethod
    def asignar_grupo(pid):
        return "A" if int(hashlib.sha256(pid.encode()).hexdigest(), 16) % 2 == 0 else "B"

    @staticmethod
    def prueba_z(exitos_a, n_a, exitos_b, n_b):
        p_a, p_b = exitos_a / n_a, exitos_b / n_b
        p = (exitos_a + exitos_b) / (n_a + n_b)
        error = math.sqrt(p * (1 - p) * (1 / n_a + 1 / n_b))
        z = (p_a - p_b) / error if error else 0.0
        return p_a, p_b, math.erfc(abs(z) / math.sqrt(2))

    def experimento_ab(self, notificaciones, tasa_base=0.30, efecto_supuesto=0.08, semilla=7):
        """SIMULACIÓN del experimento: A recibe mensaje personalizado, B el genérico.

        Como el MVP no tiene usuarios reales, la respuesta ("volvió en 7 días")
        se simula suponiendo un efecto. En producción se mide con los check-ins reales
        y esta misma función calcula si la diferencia es significativa.
        """
        rng = random.Random(semilla)
        candidatos = notificaciones[notificaciones.tipo != "generico"]
        resultados = {"A": [0, 0], "B": [0, 0]}
        for pid in candidatos.pid:
            grupo = self.asignar_grupo(pid)
            prob = tasa_base + (efecto_supuesto if grupo == "A" else 0)
            resultados[grupo][0] += rng.random() < prob
            resultados[grupo][1] += 1
        p_a, p_b, p_valor = self.prueba_z(*resultados["A"], *resultados["B"])
        return {"n_A": resultados["A"][1], "n_B": resultados["B"][1],
                "retorno_A": p_a, "retorno_B": p_b, "p_valor": p_valor,
                "significativo": p_valor < 0.05, "simulado": True}
