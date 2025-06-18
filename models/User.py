class Usuario:
    def __init__(self, uid, nombre, email, rol="usuario", foto_url=None, proyectos_creados=None):
        self.uid = uid
        self.nombre = nombre
        self.email = email
        self.rol = rol
        self.foto_url = foto_url
        self.proyectos_creados = proyectos_creados or []  # lista de IDs

        
    def to_json(self):
        return self.__dict__
    
