from collections import Counter, defaultdict


class BusEventos:
    """Bus publicar/suscribir en memoria por donde se comunican los agentes.

    En producción se reemplaza por Apache Kafka: cada tema ("eventos.crudos",
    "eventos.limpios", ...) se convierte en un topic de Kafka.
    """

    def __init__(self):
        self._suscriptores = defaultdict(list)
        self.contador = Counter()

    def suscribir(self, tema, funcion):
        self._suscriptores[tema].append(funcion)

    def publicar(self, tema, evento):
        self.contador[tema] += 1
        for funcion in self._suscriptores[tema]:
            funcion(evento)
