# FitFlow: MVP de un sistema multiagente de Big Data para un gimnasio

Un equipo de agentes; cada uno se encarga de una fase del ciclo de Big Data para personalizar la experiencia del socio.

| Fase | Agente | Archivo | Qué hace en el MVP |
|---|---|---|---|
| Transversal | 🛡️ Guardián | `agentes/guardian.py` | consentimiento granular, seudonimización (HMAC-SHA256), bóveda de identidades auditada, derecho al olvido |
| 1. Captura | 📡 Capturador | `agentes/capturador.py` | simula 300 socios durante 90 días: check-ins, reservas, series, app, calificaciones (con ruido realista) |
| 2. Ingesta | ⚡ Ingestor | `agentes/ingestor.py` | procesa cada evento en vivo: deduplica, valida, seudonimiza, calcula el aforo y emite alertas |
| 3. Almacenamiento | 🗄️ Custodio | `agentes/custodio.py` | SQLite con capas cuarentena / plata / oro y checksum SHA-256 por fila para verificar la integridad |
| 4. Análisis | 🧠 Analista | `agentes/analista.py` | mapa de aforo, Random Forest de abandono, segmentación K-Means, recomendador colaborativo de clases |
| 5. Explotación | 🎯 Coach | `agentes/coach.py` | una notificación personalizada por socio (retención, rendimiento, descubrimiento, hábito) |
| 5. Evaluación | 📊 Evaluador | `agentes/evaluador.py` | KPIs de experiencia y prueba A/B con test z de proporciones |
| Coordinación | 🧭 Orquestador | `agentes/orquestador.py` | conecta los agentes por el bus de eventos y ejecuta el ciclo |

Los agentes se comunican por un **bus de eventos** (`agentes/bus.py`) con temas como
`eventos.crudos`, `eventos.limpios`, `eventos.rechazados` y `alertas.aforo`.

## Cómo ejecutarlo

```bash
python -m venv venv
venv\Scripts\activate          # en Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python main.py                 # reporte en consola
streamlit run dashboard.py     # panel visual en http://localhost:8501
```

> En Windows, si `pip` falla con un error de "Long Path", crea el entorno virtual en una ruta corta (por ejemplo `C:\venvs\fitflow`).

## Limitaciones honestas del MVP

- Los datos son **sintéticos** (simulados). Por eso el modelo de abandono da un AUC muy alto: con datos reales será menor.
- El resultado de la **prueba A/B es simulado** (supone un efecto de +8 puntos). La lógica estadística sí es real y sirve tal cual con datos reales.
- Todo corre en un solo proceso. El bus en memoria imita a Kafka y SQLite imita al lakehouse.

## Camino a producción (qué reemplaza a qué)

| MVP | Producción |
|---|---|
| Simulador del Capturador | SDK de eventos en la app (Firebase Analytics / Segment), torniquete QR, Apple Health / Google Fit |
| `BusEventos` en memoria | Apache Kafka o AWS Kinesis |
| Ingestor en Python | Apache Flink o Spark Structured Streaming |
| SQLite (plata/oro) | S3 + Delta Lake (bronce/plata/oro), PostgreSQL para transacciones, Redis para el aforo en vivo |
| Features en pandas | Feature Store (Feast) |
| Modelos scikit-learn | los mismos modelos versionados con MLflow y reentrenados semanalmente con Airflow |
| Mensajes del Coach | Firebase Cloud Messaging, más un LLM para el coach conversacional |
| Clave HMAC en el código | AWS KMS / HashiCorp Vault |
| Dashboard Streamlit | Power BI / Looker para gerencia, y la propia app para el socio |
