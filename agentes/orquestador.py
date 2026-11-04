import time
from datetime import timedelta
from pathlib import Path

from .analista import AgenteAnalista
from .bus import BusEventos
from .capturador import AgenteCapturador
from .coach import AgenteCoach
from .custodio import AgenteCustodio
from .evaluador import AgenteEvaluador
from .guardian import AgenteGuardian
from .ingestor import AgenteIngestor

RUTA_DB = Path(__file__).resolve().parent.parent / "datos" / "fitflow.db"


class AgenteOrquestador:
    """Coordina al equipo de agentes y ejecuta el ciclo completo de Big Data."""

    def __init__(self, n_usuarios=300, dias=90, log=print):
        self.log = log
        self.bus = BusEventos()
        self.guardian = AgenteGuardian()
        self.capturador = AgenteCapturador(self.bus, self.guardian, n_usuarios, dias)
        self.ingestor = AgenteIngestor(self.bus, self.guardian)
        self.custodio = AgenteCustodio(self.bus, RUTA_DB)
        self.analista = AgenteAnalista(self.custodio)
        self.coach = AgenteCoach(self.guardian, self.analista)
        self.evaluador = AgenteEvaluador()

    def ejecutar(self):
        t0 = time.time()
        self.log("[1] Capturador: simulando socios e interacciones...")
        self.capturador.registrar_usuarios()
        self.capturador.simular()   # cada evento fluye en vivo: Capturador -> Ingestor -> Custodio
        self.custodio.flush()

        self.log("[2] Ingestor: eventos validados, deduplicados y seudonimizados en tiempo real")
        self.log("[3] Custodio: verificando integridad de los datos almacenados...")
        alteradas = self.custodio.verificar_integridad()
        eventos = self.custodio.eventos()
        features = self.custodio.construir_features()

        self.log("[4] Analista: aforo, modelo de abandono, segmentos y recomendaciones...")
        self.analista.patron_aforo()
        metricas_churn = self.analista.entrenar_churn()
        perfiles = features.join([
            self.analista.segmentar(features),
            self.analista.predecir_churn(features),
            self.analista.recomendar_clases(),
        ])

        self.log("[5] Coach y Evaluador: notificaciones personalizadas y medición de impacto...")
        manana = (eventos.ts.max() + timedelta(days=1)).dayofweek
        notificaciones = self.coach.generar(perfiles, manana)
        kpis = self.evaluador.kpis(eventos, perfiles)
        ab = self.evaluador.experimento_ab(notificaciones)

        self.resultados = {
            "ingesta": dict(self.ingestor.stats),
            "alertas_aforo": self.ingestor.alertas,
            "filas_alteradas": alteradas,
            "eventos": eventos,
            "perfiles": perfiles,
            "patron_aforo": self.analista.patron,
            "churn": metricas_churn,
            "notificaciones": notificaciones,
            "kpis": kpis,
            "ab": ab,
            "consultas_auditadas": len(self.guardian.auditoria),
            "segundos": time.time() - t0,
        }
        return self.resultados
