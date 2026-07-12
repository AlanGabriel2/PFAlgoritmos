from data import SUBJECTS

# Colores de los 8 caminos críticos (aristas del mapa). El tutorial también los
# usa para mostrar la leyenda de colores.
PATH_PALETTE = [
    (180, 20, 40),   # Crimson
    (20, 160, 60),   # Emerald
    (30, 80, 180),   # Sapphire
    (180, 140, 20),  # Gold
    (20, 140, 140),  # Teal
    (140, 40, 140),  # Plum
    (180, 80, 20),   # Rust
    (80, 40, 160)    # Indigo
]

class NodeState:
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"
    CLEANED = "CLEANED"

class DagEngine:
    def __init__(self):
        self.subjects = SUBJECTS
        self.nodes = list(self.subjects.keys())
        self.state = {node: NodeState.LOCKED for node in self.nodes}
        self.dp = {node: 1 for node in self.nodes}
        self.par_score = 0
        self.critical_nodes = []
        self.critical_paths = []
        self.node_colors = {}
        self.edge_colors = {}
        self.calculate_dp()
        self.calculate_critical_path()
        self.update_unlocks()

    def calculate_dp(self):
        """Calcula el Camino Crítico (Tiempo Récord) usando Programación Dinámica."""
        # Calcular los grados de entrada (in-degrees)
        in_degree = {node: 0 for node in self.nodes}
        adj = {node: [] for node in self.nodes}
        
        for u in self.nodes:
            for req in self.subjects[u]['reqs']:
                # La arista es req -> u
                if req in self.nodes:
                    adj[req].append(u)
                    in_degree[u] += 1

        # Ordenamiento Topológico para DP
        queue = [node for node in self.nodes if in_degree[node] == 0]
        topo_order = []
        
        while queue:
            u = queue.pop(0)
            topo_order.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        
        # Calcular DP
        for u in topo_order:
            for req in self.subjects[u]['reqs']:
                if req in self.nodes:
                    self.dp[u] = max(self.dp[u], self.dp[req] + 1)
                    
        self.par_score = max(self.dp.values())

    def calculate_critical_path(self):
        """Identifica los nodos que forman parte del camino crítico y sus rutas."""
        target_dp = self.par_score
        end_nodes = [node for node in self.nodes if self.dp[node] == target_dp]
        
        paths = []
        def dfs(node, current_path):
            if self.dp[node] == 1:
                paths.append(current_path[::-1])
                return
            for req in self.subjects[node]['reqs']:
                if req in self.nodes and self.dp[req] == self.dp[node] - 1:
                    dfs(req, current_path + [req])
                    
        for node in end_nodes:
            dfs(node, [node])
            
        self.critical_paths = paths
        
        # Asignar colores únicos a las rutas (paleta compartida a nivel de módulo
        # para que el tutorial pueda mostrar los mismos colores).
        palette = PATH_PALETTE
        
        visited_nodes = set()
        for i, path in enumerate(self.critical_paths):
            color = palette[i % len(palette)]
            for j in range(len(path)):
                node = path[j]
                visited_nodes.add(node)
                # Asignar color al nodo si no tiene uno (la primera ruta que lo reclame dicta su color)
                if node not in self.node_colors:
                    self.node_colors[node] = color
                
                # Asignar color a la arista (req -> node)
                if j > 0:
                    req = path[j-1]
                    edge = (req, node)
                    if edge not in self.edge_colors:
                        self.edge_colors[edge] = []
                    if color not in self.edge_colors[edge]:
                        self.edge_colors[edge].append(color)
                        
        self.critical_nodes = list(visited_nodes)

    def update_unlocks(self):
        """Desbloquea las habitaciones cuyos prerrequisitos ya fueron limpiados."""
        # Comprobar la condición del Mega-Candado
        cleaned_count = sum(1 for s in self.state.values() if s == NodeState.CLEANED)
        total_required = len(self.nodes) - 1 # Excluir el Mega-Candado

        for node in self.nodes:
            if self.state[node] == NodeState.CLEANED:
                continue
                
            if node == "TIP10TEMTT1": # Mega-Candado (Habitación de Titulación)
                if cleaned_count >= total_required:
                    self.state[node] = NodeState.UNLOCKED
            else:
                # Nodos normales
                can_unlock = True
                for req in self.subjects[node]['reqs']:
                    if req in self.state and self.state[req] != NodeState.CLEANED:
                        can_unlock = False
                        break
                
                if can_unlock:
                    self.state[node] = NodeState.UNLOCKED

        # --- MODO PRUEBA: Desbloquear todos los nodos temporalmente ---
        for node in self.nodes:
            if self.state[node] == NodeState.LOCKED:
                self.state[node] = NodeState.UNLOCKED
        # --------------------------------------------------------------

    def clean_room(self, node):
        if self.state[node] == NodeState.UNLOCKED:
            self.state[node] = NodeState.CLEANED
            return True
        return False
        
    def get_par_score(self):
        return self.par_score
