# solve_adaptive.py — ВЕРСИЯ ДЛЯ РАЗРЕЖЕННЫХ ГРАФОВ (N=200, но только 100 активных)
import json
import time
import sys
from ortools.sat.python import cp_model

# ======================
# CONFIG
# ======================
TIME_LIMIT_SEC = 1200.0    # ← можно ставить 600.0
MAX_WORKERS = 28
INPUT_FILE = "network_50.json"

# ======================
# ЗАГРУЗКА
# ======================
try:
    with open(INPUT_FILE) as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"❌ Файл '{INPUT_FILE}' не найден.")
    sys.exit(1)

# ВАЖНО: станции могут быть не все подряд!
edges = {int(k): [int(x) for x in v] for k, v in data["edges"].items()}
all_stations = sorted(edges.keys())  # ← только существующие станции!
N = len(all_stations)
station_to_idx = {s: i for i, s in enumerate(all_stations)}  # 0..N-1 → для компактности
idx_to_station = {i: s for s, i in station_to_idx.items()}

# Перекодируем od_data в индексы
od_data_raw = {}
for k, v in data["od_data"].items():
    o, d = map(int, k.split(","))
    if o in station_to_idx and d in station_to_idx:
        od_data_raw[(station_to_idx[o], station_to_idx[d])] = v

total_wagons = sum(od_data_raw.values())
print(f"Активных станций: {N} | Вагонов: {total_wagons}")
print(f"Лимит: {TIME_LIMIT_SEC} сек | Ядер: {MAX_WORKERS}")

# ======================
# МОДЕЛЬ (работаем с индексами 0..N-1)
# ======================
demand = [0] * N
for (o, d), cnt in od_data_raw.items():
    demand[d] += cnt

best_solution = None
best_T = None
start_time = time.time()

# Перекодируем рёбра в индексы
edges_idx = {}
for s in all_stations:
    i = station_to_idx[s]
    edges_idx[i] = [station_to_idx[neigh] for neigh in edges[s] if neigh in station_to_idx]

# Поиск по T
for T in range(8, 50):  # разумная верхняя граница
    elapsed = time.time() - start_time
    if elapsed > TIME_LIMIT_SEC - 5:
        break

    model = cp_model.CpModel()

    # Переменные x[t][i][j][d]
    x = {}
    for t in range(T):
        for i in range(N):
            for j in edges_idx.get(i, []):
                for d in range(N):
                    if od_data_raw.get((i, d), 0) > 0 or any(od_data_raw.get((orig, d), 0) > 0 for orig in range(N)):
                        x[(t, i, j, d)] = model.NewIntVar(0, 30, '')

    # Состояние w[t][i][d]
    w = {}
    for t in range(T + 1):
        for i in range(N):
            for d in range(N):
                w[(t, i, d)] = model.NewIntVar(0, total_wagons, '')

    # Инициализация
    for i in range(N):
        for d in range(N):
            model.Add(w[(0, i, d)] == od_data_raw.get((i, d), 0))

    # Баланс
    for t in range(T):
        for i in range(N):
            for d in range(N):
                inbound = sum(x.get((t-1, k, i, d), 0) for k in range(N) if i in edges_idx.get(k, [])) if t > 0 else 0
                outbound = sum(x.get((t, i, j, d), 0) for j in edges_idx.get(i, []))
                model.Add(w[(t+1, i, d)] == w[(t, i, d)] + inbound - outbound)

    # Ограничения на поезда
    for t in range(T):
        for i in range(N):
            for j in edges_idx.get(i, []):
                total = sum(x.get((t, i, j, d), 0) for d in range(N))
                sent = model.NewBoolVar('')
                model.Add(total >= 5).OnlyEnforceIf(sent)
                model.Add(total == 0).OnlyEnforceIf(sent.Not())
                model.Add(total <= 30)

    # Запрет вывоза из назначения
    for t in range(T):
        for d in range(N):
            for j in edges_idx.get(d, []):
                model.Add(sum(x.get((t, d, j, d), 0) for j in edges_idx.get(d, [])) == 0)

    # Условие: все доставлены
    for d in range(N):
        model.Add(w[(T, d, d)] == demand[d])

    # Решатель
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(1.0, TIME_LIMIT_SEC - elapsed)
    solver.parameters.num_search_workers = min(MAX_WORKERS, 8)
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        best_T = T
        best_solution = []
        for t in range(T):
            for i in range(N):
                for j in edges_idx.get(i, []):
                    for d in range(N):
                        val = solver.Value(x.get((t, i, j, d), 0))
                        if val > 0:
                            # Перекодируем обратно в реальные номера станций
                            s_i = idx_to_station[i]
                            s_j = idx_to_station[j]
                            s_d = idx_to_station[d]
                            best_solution.append((t, s_i, s_j, s_d, val))
        break

# ======================
# ВЫВОД
# ======================
elapsed_total = time.time() - start_time
if best_T is not None:
    print(f"\n🏆 Решение найдено за {elapsed_total:.1f} сек:")
    print(f"  makespan = {best_T} дней")
    print(f"  активных станций: {N}, вагонов: {total_wagons}")
else:
    print(f"\n⚠️ За {elapsed_total:.1f} сек решение не найдено.")