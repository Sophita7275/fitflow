from collections import Counter
from datetime import datetime

TIPOS_VALIDOS = {"app_abierta", "checkin", "clase_reservada", "clase_cancelada",
                 "serie_completada", "calificacion"}


class AgenteIngestor:
    """Fase 2 - Ingesta y procesamiento en tiempo real.

    Escucha "eventos.crudos" y, evento por evento:
    deduplica, valida, seudonimiza, publica en "eventos.limpios"
    y calcula el aforo en vivo, emitiendo alertas cuando se supera el umbral.
    En producción: Kafka + Apache Flink / Spark Structured Streaming.
    """

    def __init__(self, bus, guardian, umbral_aforo=16):
        self.bus = bus
        self.guardian = guardian
        self.umbral_aforo = umbral_aforo
        self.vistos = set()
        self.stats = Counter()
        self.aforo = Counter()
        self.alertas = []
        bus.suscribir("eventos.crudos", self.procesar)

    def _validar(self, evento):
        if evento.get("tipo") not in TIPOS_VALIDOS:
            return "tipo inválido"
        if not evento.get("usuario"):
            return "sin usuario"
        try:
            datetime.fromisoformat(evento["ts"])
        except (TypeError, ValueError):
            return "fecha inválida"
        return None

    def procesar(self, evento):
        self.stats["recibidos"] += 1
        if evento["id"] in self.vistos:
            self.stats["duplicados"] += 1
            return
        self.vistos.add(evento["id"])

        pid = self.guardian.seudonimizar(evento["usuario"])
        motivo = self._validar(evento)
        if motivo:
            self.stats["invalidos"] += 1
            self.bus.publicar("eventos.rechazados", {**evento, "usuario": pid, "motivo": motivo})
            return

        ts = datetime.fromisoformat(evento["ts"])
        self.stats["validos"] += 1
        self.bus.publicar("eventos.limpios", {
            "id": evento["id"], "pid": pid, "tipo": evento["tipo"], "ts": ts, "datos": evento["datos"],
        })

        if evento["tipo"] == "checkin":
            franja = (ts.date(), ts.hour)
            self.aforo[franja] += 1
            if self.aforo[franja] == self.umbral_aforo:
                alerta = {"fecha": ts.date(), "hora": ts.hour, "personas": self.umbral_aforo}
                self.alertas.append(alerta)
                self.bus.publicar("alertas.aforo", alerta)
