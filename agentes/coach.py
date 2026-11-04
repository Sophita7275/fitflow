import pandas as pd


class AgenteCoach:
    """Fase 5a - Explotación: convierte los insights en acciones para cada socio.

    Genera como máximo UNA notificación por socio (para no hacer spam) y solo
    personaliza si el socio dio consentimiento. En producción se enviaría
    con Firebase Cloud Messaging.
    """

    def __init__(self, guardian, analista, umbral_riesgo=0.6):
        self.guardian = guardian
        self.analista = analista
        self.umbral_riesgo = umbral_riesgo

    def _mensaje(self, p, dia_semana):
        hora = self.analista.mejor_hora(dia_semana, cerca_de=p.hora_preferida)
        clase = p.clase_favorita if isinstance(p.clase_favorita, str) else "funcional"
        if p.riesgo_abandono >= self.umbral_riesgo:
            return "retencion", (f"¡Te extrañamos! Mañana a las {hora}:00 hay poca gente. "
                                 f"¿Te reservamos un cupo en {clase}?")
        if p.segmento == "Fuerza":
            return "rendimiento", (f"Llevas {p.series} series registradas. Mañana a las {hora}:00 "
                                   f"la zona de pesas estará más tranquila.")
        if isinstance(p.clase_recomendada, str):
            return "descubrimiento", (f"A socios con gustos como los tuyos les encanta {p.clase_recomendada}. "
                                      f"¡Pruébala esta semana!")
        return "habito", (f"Tu mejor hora mañana: {hora}:00 (aforo bajo). "
                          f"¡Sigue así, llevas {p.visitas_14d} visitas en 2 semanas!")

    def generar(self, perfiles, dia_semana):
        filas = []
        for pid, p in perfiles.iterrows():
            usuario = self.guardian.identificar(pid, motivo="enviar notificación")
            if self.guardian.puede(usuario, "personalizacion"):
                tipo, mensaje = self._mensaje(p, dia_semana)
            else:
                tipo, mensaje = "generico", "¡Te esperamos esta semana! Revisa el horario de clases en la app."
            filas.append({"usuario": usuario, "pid": pid, "segmento": p.segmento,
                          "riesgo_abandono": round(p.riesgo_abandono, 2), "tipo": tipo, "mensaje": mensaje})
        return pd.DataFrame(filas)
