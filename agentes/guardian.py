import hashlib
import hmac


class AgenteGuardian:
    """Agente transversal: privacidad, consentimiento y cumplimiento legal.

    - Guarda el consentimiento granular de cada usuario.
    - Seudonimiza: el resto del sistema solo ve un ID anónimo (pid).
    - Guarda la relación pid -> usuario en una "bóveda" y audita quién la consulta.
    - Ejecuta el derecho al olvido (borrar todos los datos de un usuario).
    """

    def __init__(self, clave_secreta=b"cambiar-en-produccion"):
        # En producción la clave vive en un gestor de secretos (AWS KMS, Vault...).
        self._clave = clave_secreta
        self.consentimientos = {}
        self._boveda = {}
        self.auditoria = []

    def registrar_consentimiento(self, usuario, analitica, personalizacion):
        # Sin permiso de analítica no puede haber personalización.
        self.consentimientos[usuario] = {
            "analitica": analitica,
            "personalizacion": analitica and personalizacion,
        }

    def puede(self, usuario, finalidad):
        return self.consentimientos.get(usuario, {}).get(finalidad, False)

    def seudonimizar(self, usuario):
        firma = hmac.new(self._clave, usuario.encode(), hashlib.sha256).hexdigest()
        pid = "P" + firma[:10]
        self._boveda[pid] = usuario
        return pid

    def identificar(self, pid, motivo):
        """Recupera el usuario real de un pid. Cada consulta queda auditada."""
        self.auditoria.append({"pid": pid, "motivo": motivo})
        return self._boveda[pid]

    def derecho_al_olvido(self, usuario, custodio):
        pid = self.seudonimizar(usuario)
        borrados = custodio.borrar_usuario(pid)
        self.consentimientos.pop(usuario, None)
        self._boveda.pop(pid, None)
        self.auditoria.append({"pid": pid, "motivo": "derecho al olvido"})
        return borrados
