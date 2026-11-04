import hashlib
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd


def _checksum(fila):
    return hashlib.sha256("|".join(str(v) for v in fila).encode()).hexdigest()


class AgenteCustodio:
    """Fase 3 - Almacenamiento seguro e íntegro.

    MVP con SQLite siguiendo la arquitectura medallion:
      - cuarentena : eventos rechazados por el Ingestor (para auditar)
      - plata      : eventos limpios y seudonimizados, cada fila con checksum SHA-256
      - oro        : variables (features) por socio, listas para los modelos
    En producción: S3/ADLS + Delta Lake, PostgreSQL y Redis (ver README).
    """

    def __init__(self, bus, ruta="datos/fitflow.db", tam_lote=5000):
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        Path(ruta).unlink(missing_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.tam_lote = tam_lote
        self._lote = []
        self._cache = None
        self.con.executescript("""
            CREATE TABLE plata (id TEXT PRIMARY KEY, pid TEXT, tipo TEXT, ts TEXT,
                                datos TEXT, checksum TEXT);
            CREATE INDEX idx_plata_pid ON plata(pid);
            CREATE TABLE cuarentena (id TEXT, pid TEXT, motivo TEXT, crudo TEXT);
        """)
        bus.suscribir("eventos.limpios", self.guardar)
        bus.suscribir("eventos.rechazados", self.poner_en_cuarentena)

    def guardar(self, evento):
        fila = (evento["id"], evento["pid"], evento["tipo"], evento["ts"].isoformat(),
                json.dumps(evento["datos"], sort_keys=True))
        self._lote.append(fila + (_checksum(fila),))
        if len(self._lote) >= self.tam_lote:
            self.flush()

    def poner_en_cuarentena(self, evento):
        self.con.execute("INSERT INTO cuarentena VALUES (?, ?, ?, ?)",
                         (evento["id"], evento["usuario"], evento["motivo"], json.dumps(evento, default=str)))

    def flush(self):
        self.con.executemany("INSERT OR IGNORE INTO plata VALUES (?, ?, ?, ?, ?, ?)", self._lote)
        self.con.commit()
        self._lote = []
        self._cache = None

    def verificar_integridad(self):
        """Recalcula el checksum de cada fila. Devuelve cuántas filas fueron alteradas."""
        alteradas = 0
        for *fila, checksum in self.con.execute("SELECT id, pid, tipo, ts, datos, checksum FROM plata"):
            if _checksum(fila) != checksum:
                alteradas += 1
        return alteradas

    def borrar_usuario(self, pid):
        borrados = self.con.execute("DELETE FROM plata WHERE pid = ?", (pid,)).rowcount
        self.con.commit()
        self._cache = None
        return borrados

    def eventos(self):
        if self._cache is None:
            df = pd.read_sql("SELECT id, pid, tipo, ts, datos FROM plata", self.con, parse_dates=["ts"])
            datos = df.pop("datos").map(json.loads)
            df["clase"] = datos.map(lambda d: d.get("clase"))
            df["estrellas"] = datos.map(lambda d: d.get("estrellas"))
            df["fecha"] = df.ts.dt.normalize()
            df["hora"] = df.ts.dt.hour
            self._cache = df
        return self._cache

    def construir_features(self, hasta=None):
        """Capa oro: una fila por socio con su comportamiento hasta la fecha `hasta`."""
        df = self.eventos()
        if hasta is not None:
            df = df[df.ts < hasta]
        ref = hasta if hasta is not None else df.ts.max()

        def contar(filtro):
            return df[filtro].groupby("pid").size()

        chk = df[df.tipo == "checkin"]
        f = pd.DataFrame(index=pd.Index(df.pid.unique(), name="pid"))
        f["visitas_total"] = chk.groupby("pid").size()
        f["visitas_14d"] = contar((df.tipo == "checkin") & (df.ts >= ref - timedelta(days=14)))
        f["visitas_14d_previas"] = contar((df.tipo == "checkin") & (df.ts >= ref - timedelta(days=28))
                                          & (df.ts < ref - timedelta(days=14)))
        f["reservas"] = contar(df.tipo == "clase_reservada")
        f["cancelaciones"] = contar(df.tipo == "clase_cancelada")
        f["series"] = contar(df.tipo == "serie_completada")
        f["aperturas_app"] = contar(df.tipo == "app_abierta")
        f = f.fillna(0).astype(int)

        primera_vez = df.groupby("pid").ts.min()
        ultima_visita = chk.groupby("pid").ts.max().reindex(f.index).fillna(primera_vez)
        f["dias_sin_venir"] = (ref - ultima_visita).dt.days
        f["tasa_cancelacion"] = f.cancelaciones / f.reservas.clip(lower=1)
        f["tendencia"] = f.visitas_14d - f.visitas_14d_previas
        f["calificacion_media"] = df.groupby("pid").estrellas.mean().reindex(f.index)
        f["hora_preferida"] = (chk.groupby("pid").hora.agg(lambda s: s.mode().iloc[0])
                               .reindex(f.index).fillna(18).astype(int))
        reservas = df[df.tipo == "clase_reservada"]
        f["clase_favorita"] = reservas.groupby("pid").clase.agg(lambda s: s.mode().iloc[0]).reindex(f.index)

        if hasta is None:
            f.to_sql("oro_features", self.con, if_exists="replace")
        return f
