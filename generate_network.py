# generate_random_connected_network.py
import random
import json
import sys
from collections import defaultdict, deque

def generate_connected_graph(n_stations, extra_edges_ratio=0.5, seed=42):
    """
    Генерирует связный неориентированный граф из n_stations станций.
    
    Параметры:
      n_stations: int — число станций (нумеруются 0..n_stations-1)
      extra_edges_ratio: float — сколько ДОП. рёбер добавить: 
          total_edges = (n_stations - 1) + round(extra_edges_ratio * (n_stations - 1))
      seed: int — для воспроизводимости
    
    Возвращает:
      edges: dict {int: [int]} — список соседей для каждой станции
    """
    random.seed(seed)
    
    if n_stations < 1:
        raise ValueError("n_stations >= 1")
    if n_stations == 1:
        return {0: []}
    
    edges = defaultdict(list)
    stations = list(range(n_stations))
    
    # Шаг 1: строим остовное дерево методом "random attachment"
    # (начинаем с 0, поочерёдно подключаем каждую новую станцию к случайной существующей)
    available = [0]  # станции, уже в дереве
    
    for new_station in range(1, n_stations):
        # выбираем случайную станцию из уже подключенных
        parent = random.choice(available)
        # добавляем двустороннее ребро
        edges[parent].append(new_station)
        edges[new_station].append(parent)
        available.append(new_station)
    
    # Шаг 2: добавляем extra_edges
    max_possible_extra = n_stations * (n_stations - 1) // 2 - (n_stations - 1)
    n_extra = min(
        round(extra_edges_ratio * (n_stations - 1)),
        max_possible_extra
    )
    
    # Все возможные рёбра (без дублей и петель)
    all_possible = []
    for i in range(n_stations):
        for j in range(i + 1, n_stations):
            if j not in edges[i]:  # ещё нет такого ребра
                all_possible.append((i, j))
    
    if all_possible and n_extra > 0:
        extra_edges = random.sample(all_possible, min(n_extra, len(all_possible)))
        for u, v in extra_edges:
            edges[u].append(v)
            edges[v].append(u)
    
    # Приводим к обычному dict и сортируем соседей
    return {i: sorted(edges[i]) for i in range(n_stations)}


def generate_od_data(edges, avg_wagons_per_station=30, max_dest_per_station=5, seed=42):
    """
    Генерирует OD-матрицу (origin-destination):
      - каждая станция отправляет вагоны на 1..max_dest_per_station других станций
      - объём — случайный от 5 до 50 (с центром ~avg_wagons_per_station)
    """
    random.seed(seed)
    n = len(edges)
    od = {}
    
    for o in range(n):
        # Все возможные назначения (кроме себя)
        candidates = [d for d in range(n) if d != o and d in edges]  # защита
        if not candidates:
            continue
        # Сколько направлений?
        k = random.randint(1, min(max_dest_per_station, len(candidates)))
        dests = random.sample(candidates, k)
        for d in dests:
            # Объём: от 5 до 50, среднее ~avg
            cnt = 5 * random.randint(1, max(1, avg_wagons_per_station // 5 // k + 1))
            # Ограничиваем сверху:
            cnt = min(cnt, 20)  # например, максимум 50 вагонов на одно направление
            od[(o, d)] = cnt
    return od


def is_connected(edges):
    """Проверка связности графа (DFS/BFS) — для валидации"""
    if not edges:
        return True
    n = len(edges)
    visited = set()
    queue = deque([0])
    visited.add(0)
    
    while queue:
        u = queue.popleft()
        for v in edges.get(u, []):
            if v not in visited:
                visited.add(v)
                queue.append(v)
    return len(visited) == n


# ======================
# ОСНОВНОЙ СКРИПТ
# ======================
if __name__ == "__main__":
    # Параметры — можно передавать через CLI или редактировать здесь
    N_STATIONS = 50
    EXTRA_RATIO = 0.6  # +60% рёбер к остову → плотность ~1.6 * (N-1)
    SEED = 42
    
    print(f"🧱 Генерируем СЛУЧАЙНУЮ СВЯЗНУЮ сеть из {N_STATIONS} станций...")
    
    # 1. Граф
    edges = generate_connected_graph(N_STATIONS, extra_edges_ratio=EXTRA_RATIO, seed=SEED)
    
    # Проверка
    assert is_connected(edges), "❌ Граф несвязный!"
    n_edges = sum(len(v) for v in edges.values()) // 2
    print(f"✅ Граф связный: {N_STATIONS} станций, {n_edges} рёбер (плотность = {n_edges / N_STATIONS:.2f})")
    
    # 2. OD-матрица
    od_data = generate_od_data(edges, avg_wagons_per_station=40, max_dest_per_station=4, seed=SEED + 1)
    total_wagons = sum(od_data.values())
    print(f"📦 Сгенерировано {len(od_data)} OD-пар, {total_wagons} вагонов")
    
    # 3. Сохранение
    data = {
        "stations": N_STATIONS,
        "edges": edges,
        "od_data": {f"{o},{d}": v for (o, d), v in od_data.items()}
    }
    
    filename = f"network_random_{N_STATIONS}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Сохранено в '{filename}'")
    
    # Пример структуры
    print("\n🔍 Пример топологии:")
    for i in range(min(5, N_STATIONS)):
        print(f"   Станция {i}: → {edges[i]}")
    if N_STATIONS > 5:
        print("   ...")