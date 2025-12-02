# generate_network_200.py — ИСПРАВЛЕНА ОШИБКА
import random
import json

# Базовый граф (10 станций)
base_edges = {
    0: [1],
    1: [0, 2],
    2: [1, 3, 4, 7],
    3: [2],
    4: [2, 5],
    5: [4, 6],
    6: [5, 7],
    7: [2, 6, 8],
    8: [7, 9],
    9: [8],
}

base_od = {
    (0, 6): 10, (0, 9): 20, (0, 1): 5, (0, 5): 10,
    (1, 4): 20, (1, 6): 10, (1, 3): 5, (1, 8): 10,
    (2, 3): 10, (2, 5): 20, (2, 9): 10, (2, 8): 5,
    (3, 1): 5, (3, 2): 10, (3, 7): 20, (3, 9): 5,
    (4, 1): 20, (4, 5): 10, (4, 8): 10, (4, 0): 10,
    (5, 0): 10, (5, 2): 20, (5, 7): 10,
    (6, 0): 10, (6, 1): 10, (6, 4): 10,
    (7, 3): 20, (7, 5): 10, (7, 9): 10,
    (8, 1): 10, (8, 2): 5, (8, 4): 10,
    (9, 0): 20, (9, 2): 10, (9, 3): 5, (9, 7): 10,
}
base_od = {k: v for k, v in base_od.items() if k[0] != k[1]}

# Параметры
N_BLOCKS = 5
BLOCK_SIZE = 10  # ← теперь это просто размер блока (но базовый граф — 10 станций)
BASE_GRAPH_SIZE = 10  # ← явно выносим

TOTAL_STATIONS = N_BLOCKS * BLOCK_SIZE
print(f"🧱 Генерируем сеть из {TOTAL_STATIONS} станций ({N_BLOCKS} блоков по {BLOCK_SIZE})")

# 1. Собираем полный граф (только первые BASE_GRAPH_SIZE станций в каждом блоке)
edges = {}
for b in range(N_BLOCKS):
    offset = b * BLOCK_SIZE
    for u in range(BASE_GRAPH_SIZE):  # только 0..9
        edges[offset + u] = []
        for v in base_edges.get(u, []):
            if v < BASE_GRAPH_SIZE:  # защита
                edges[offset + u].append(offset + v)

# 2. Добавляем межблоковые связи
random.seed(42)
inter_connections = []

# Гарантируем, что все узлы существуют перед использованием
all_nodes = list(edges.keys())

for b1 in range(N_BLOCKS):
    for b2 in range(b1 + 1, N_BLOCKS):
        for _ in range(3):
            # Берём случайные узлы ИЗ СУЩЕСТВУЮЩИХ в блоке
            u_candidates = [i for i in range(BASE_GRAPH_SIZE)]
            v_candidates = [i for i in range(BASE_GRAPH_SIZE)]
            if not u_candidates or not v_candidates:
                continue
            u = random.choice(u_candidates)
            v = random.choice(v_candidates)
            
            u_full = b1 * BLOCK_SIZE + u
            v_full = b2 * BLOCK_SIZE + v
            
            # Проверяем, что узлы существуют (защита от KeyError)
            if u_full not in edges:
                edges[u_full] = []
            if v_full not in edges:
                edges[v_full] = []
            
            edges[u_full].append(v_full)
            edges[v_full].append(u_full)
            inter_connections.append((u_full, v_full))

print(f"🔗 Добавлено {len(inter_connections)} межблоковых связей")

# 3. Генерируем OD-матрицу
od_data = {}
demand_shift = [0, 2, 1, 3, 4, 0, 1, 2, 3, 4][:N_BLOCKS]  # расширяем до N_BLOCKS

for b in range(N_BLOCKS):
    offset_src = b * BLOCK_SIZE
    shift = demand_shift[b]
    offset_dst = ((b + shift) % N_BLOCKS) * BLOCK_SIZE
    for (orig, dest), cnt in base_od.items():
        # Убеждаемся, что orig, dest < BASE_GRAPH_SIZE
        if orig >= BASE_GRAPH_SIZE or dest >= BASE_GRAPH_SIZE:
            continue
        new_orig = offset_src + orig
        new_dest = offset_dst + dest
        # Защита: если станция не создана — пропускаем
        if new_orig not in edges or new_dest not in edges:
            continue
        od_data[(new_orig, new_dest)] = cnt

total_wagons = sum(od_data.values())
print(f"📦 Сгенерировано {total_wagons} вагонов")

# 4. Сохраняем
data = {
    "stations": TOTAL_STATIONS,
    "edges": edges,
    "od_data": {f"{o},{d}": v for (o, d), v in od_data.items()}
}

with open("network_50.json", "w") as f:
    json.dump(data, f, indent=2)

print("✅ Сеть сохранена в 'network_200.json'")
print(f"Пример: Ст.0 соединена с {edges.get(0, [])[:5]}")