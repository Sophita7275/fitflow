import random
import uuid
from datetime import datetime, timedelta

PERFILES = {
    "principiante": dict(p_visita=0.30, series=(3, 8), p_clase=0.4, clases=["yoga", "pilates", "funcional"]),
    "fuerza": dict(p_visita=0.55, series=(12, 25), p_clase=0.1, clases=["crossfit", "funcional"]),
    "cardio": dict(p_visita=0.50, series=(2, 6), p_clase=0.5, clases=["spinning", "funcional"]),
    "clases": dict(p_visita=0.45, series=(0, 3), p_clase=0.9, clases=["spinning", "yoga", "pilates", "crossfit"]),
}
EJERCICIOS = ["sentadilla", "press banca", "peso muerto", "remo", "press militar"]
PANTALLAS = ["inicio", "aforo", "reservas", "rutina", "progreso", "retos"]


class AgenteCapturador:
    """Fase 1 - Captura de datos de interacción.

    En el MVP un simulador genera socios y su comportamiento durante N días.
    En producción los eventos llegarían del SDK de la app (Firebase/Segment),
    del torniquete con QR y de los wearables, con el mismo formato.
    """

    def __init__(self, bus, guardian, n_usuarios=300, dias=90, semilla=42):
        self.bus = bus
        self.guardian = guardian
        self.n_usuarios = n_usuarios
        self.dias = dias
        self.rng = random.Random(semilla)
        self.inicio = datetime(2026, 8, 1)
        self.usuarios = {}

    def registrar_usuarios(self):
        rng = self.rng
        for i in range(self.n_usuarios):
            usuario = f"U{i:04d}"
            abandona = rng.random() < 0.25
            self.usuarios[usuario] = {
                "perfil": rng.choice(list(PERFILES)),
                "hora": rng.choice([6, 7, 8, 12, 13, 17, 18, 19, 20]),
                "dia_abandono": rng.randint(self.dias // 3, self.dias - 20) if abandona else None,
            }
            self.guardian.registrar_consentimiento(
                usuario,
                analitica=rng.random() < 0.92,
                personalizacion=rng.random() < 0.85,
            )

    def _emitir(self, usuario, tipo, ts, **datos):
        # Sin consentimiento solo se registra el acceso, necesario para prestar el servicio.
        if tipo != "checkin" and not self.guardian.puede(usuario, "analitica"):
            return
        evento = {
            "id": str(uuid.UUID(int=self.rng.getrandbits(128))),
            "usuario": usuario,
            "tipo": tipo,
            "ts": ts.isoformat(),
            "datos": datos,
        }
        # Ruido realista para que el Ingestor tenga trabajo: eventos corruptos y duplicados.
        r = self.rng.random()
        if r < 0.01:
            evento["tipo"] = None
        elif r < 0.02:
            evento["ts"] = "fecha-invalida"
        self.bus.publicar("eventos.crudos", evento)
        if self.rng.random() < 0.01:
            self.bus.publicar("eventos.crudos", dict(evento))

    def simular(self):
        rng = self.rng
        for d in range(self.dias):
            fecha = self.inicio + timedelta(days=d)
            for usuario, u in self.usuarios.items():
                perfil = PERFILES[u["perfil"]]
                p = perfil["p_visita"] * (0.6 if fecha.weekday() >= 5 else 1)
                if u["dia_abandono"] is not None and d >= u["dia_abandono"]:
                    p *= max(0.03, 1 - (d - u["dia_abandono"]) / 7)

                if rng.random() < 0.15:
                    ts = fecha.replace(hour=rng.randint(6, 22), minute=rng.randint(0, 59))
                    self._emitir(usuario, "app_abierta", ts, pantalla=rng.choice(PANTALLAS))
                if rng.random() >= p:
                    continue

                hora = min(21, max(5, round(rng.gauss(u["hora"], 1))))
                ts = fecha.replace(hour=hora, minute=rng.randint(0, 59))
                self._emitir(usuario, "app_abierta", ts - timedelta(minutes=20), pantalla="aforo")

                clase = None
                if rng.random() < perfil["p_clase"]:
                    clase = rng.choice(perfil["clases"])
                    self._emitir(usuario, "clase_reservada", ts - timedelta(hours=3), clase=clase)
                    if rng.random() < 0.12:
                        self._emitir(usuario, "clase_cancelada", ts - timedelta(hours=1), clase=clase)
                        continue

                self._emitir(usuario, "checkin", ts)
                for _ in range(rng.randint(*perfil["series"])):
                    self._emitir(
                        usuario, "serie_completada", ts + timedelta(minutes=rng.randint(5, 60)),
                        ejercicio=rng.choice(EJERCICIOS), peso=rng.randint(10, 120),
                    )
                if clase and rng.random() < 0.15:
                    self._emitir(usuario, "calificacion", ts + timedelta(hours=1),
                                 clase=clase, estrellas=rng.choice([3, 4, 4, 5, 5]))
