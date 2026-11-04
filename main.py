"""Ejecuta el sistema multiagente FitFlow de punta a punta y muestra un reporte en consola."""
import sys

from agentes.orquestador import AgenteOrquestador

sys.stdout.reconfigure(encoding="utf-8")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def titulo(texto):
    print(f"\n{'=' * 64}\n{texto}\n{'=' * 64}")


def main():
    orq = AgenteOrquestador()
    r = orq.ejecutar()

    titulo("INGESTA (Agente Ingestor)")
    s = r["ingesta"]
    print(f"Recibidos: {s['recibidos']:,} | válidos: {s['validos']:,} | "
          f"inválidos (a cuarentena): {s['invalidos']} | duplicados descartados: {s['duplicados']}")
    print(f"Alertas de aforo lleno emitidas en tiempo real: {len(r['alertas_aforo'])}")

    titulo("ALMACENAMIENTO (Agente Custodio + Guardián)")
    print(f"Filas con checksum alterado: {r['filas_alteradas']}")
    print(f"Consultas a la bóveda de identidades auditadas: {r['consultas_auditadas']}")

    titulo("ANÁLISIS (Agente Analista)")
    c = r["churn"]
    print(f"Modelo de abandono -> AUC: {c['auc']:.2f} | precisión: {c['precision']:.2f} | "
          f"recall: {c['recall']:.2f}")
    print("Variables más importantes:", ", ".join(c["importancias"].index[:3]))
    print("\nSocios por segmento:")
    print(r["perfiles"].segmento.value_counts().to_string())
    picos = r["patron_aforo"].mean().sort_values(ascending=False)
    print(f"\nHoras pico: {', '.join(f'{h}:00' for h in picos.index[:3])} | "
          f"horas más tranquilas: {', '.join(f'{h}:00' for h in picos.index[-3:])}")

    titulo("EXPLOTACIÓN (Agente Coach)")
    n = r["notificaciones"]
    print(n.tipo.value_counts().to_string())
    print("\nEjemplos:")
    for _, fila in n.groupby("tipo").head(1).iterrows():
        print(f"  [{fila.tipo}] {fila.usuario}: {fila.mensaje}")

    titulo("EVALUACIÓN (Agente Evaluador)")
    for k, v in r["kpis"].items():
        print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")
    ab = r["ab"]
    print(f"\nPrueba A/B (SIMULADA): personalizado {ab['retorno_A']:.0%} vs genérico {ab['retorno_B']:.0%} "
          f"| p-valor {ab['p_valor']:.3f} -> {'significativo' if ab['significativo'] else 'no significativo'}")

    print(f"\nListo en {r['segundos']:.1f} s. Base de datos en datos/fitflow.db")


if __name__ == "__main__":
    main()
