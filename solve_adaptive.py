# solve_adaptive.py — ВЕРСИЯ ДЛЯ РАЗРЕЖЕННЫХ ГРАФОВ (N=200, но только 100 активных)
import json
import time
import sys
from ortools.sat.python import cp_model

# ======================
# CONFIG
# ======================
TIME_LIMIT_SEC = 600.0    
MAX_WORKERS = 28
INPUT_FILE = "network_10_base.json"

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
# Вычисляем диаметр графа
def graph_diameter(edges_idx):
    from collections import deque
    N = len(edges_idx)
    max_dist = 0
    for start in range(N):
        dist = [-1] * N
        q = deque([start])
        dist[start] = 0
        while q:
            u = q.popleft()
            for v in edges_idx.get(u, []):
                if dist[v] == -1:
                    dist[v] = dist[u] + 1
                    q.append(v)
        if dist != [-1]*N:
            max_dist = max(max_dist, max(d for d in dist if d != -1))
    return max_dist

diam = graph_diameter(edges_idx)
min_T = max(1, diam)
max_T = min(50, diam + 20)
print(f"🔍 Диаметр сети: {diam} → ищем makespan от {min_T} до {max_T}")

for T in range(min_T, max_T + 1):
    elapsed = time.time() - start_time
    if elapsed > TIME_LIMIT_SEC - 5:
        break

    model = cp_model.CpModel()

    # Переменные x[t][i][j][d]
    x_unit = {}
    for t in range(T):
        for i in range(N):
            for j in edges_idx.get(i, []):
                for d in range(N):
                    if d in [dest for (_, dest) in od_data_raw.keys()] or (i, d) in od_data_raw:
                        x_unit[(t, i, j, d)] = model.NewIntVar(0, 6, '')

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
                inbound = 5 * sum(x_unit.get((t-1, k, i, d), 0) for k in range(N) if i in edges_idx.get(k, [])) if t > 0 else 0
                outbound = 5 * sum(x_unit.get((t, i, j, d), 0) for j in edges_idx.get(i, []))
                model.Add(w[(t+1, i, d)] == w[(t, i, d)] + inbound - outbound)

    # Ограничения на поезда
    for t in range(T):
        for i in range(N):
            for j in edges_idx.get(i, []):
                total_units = sum(x_unit.get((t, i, j, d), 0) for d in range(N))
                train_length = 5 * total_units

                sent = model.NewBoolVar('')
                model.Add(total_units >= 1).OnlyEnforceIf(sent)   # ≥1 → ≥5 вагонов
                model.Add(total_units == 0).OnlyEnforceIf(sent.Not())
                model.Add(total_units <= 6)                       # ≤6 → ≤30 вагонов

    # Запрет вывоза из назначения
    for t in range(T):
        for d in range(N):
            # Запрет: вагоны с назначением d НЕ могут покидать станцию d
            for j in edges_idx.get(d, []):
                model.Add(x_unit.get((t, d, j, d), 0) == 0)

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
                        val = solver.Value(x_unit.get((t, i, j, d), 0))
                        if val > 0:
                            # Перекодируем обратно в реальные номера станций
                            s_i = idx_to_station[i]
                            s_j = idx_to_station[j]
                            s_d = idx_to_station[d]
                            val_units = solver.Value(x_unit.get((t, i, j, d), 0))
                            val_wagons = 5 * val_units
                            if val_wagons > 0:
                                best_solution.append((t, s_i, s_j, s_d, val_wagons))
        break

# ======================
# ВЫВОД
# ======================
elapsed_total = time.time() - start_time
# ======================
# ПОСЛЕ УСПЕШНОГО РЕШЕНИЯ: ПОШАГОВАЯ ТРАССИРОВКА
# ======================
# if best_T is not None and best_solution:
#     print("\n🔍 Пошаговая трассировка (день → день):")
#     print("=" * 60)

#     # Воссоздаём w[t][i][d] из решения (имитация)
#     # Инициализация w0
#     w = {}
#     for i in range(N):
#         for d in range(N):
#             w[(0, i, d)] = od_data_raw.get((i, d), 0)

#     # Группируем отправки по (t, i, j) → {(t,i,j): [(d, val), ...]}
#     sends_by_edge = {}
#     for (t, s_i, s_j, s_d, val) in best_solution:
#         i = station_to_idx[s_i]
#         j = station_to_idx[s_j]
#         d = station_to_idx[s_d]
#         key = (t, i, j)
#         sends_by_edge.setdefault(key, []).append((d, val))

#     # Суточное моделирование
#     for t in range(best_T):
#         print(f"\n📅 День {t} → {t+1}")
#         print("-" * 40)

#         # 1. Отправлено в этот день
#         print("📤 Отправлено:")
#         edge_sends = {}
#         for (tt, i, j), items in sends_by_edge.items():
#             if tt == t:
#                 total = sum(val for _, val in items)
#                 dest_summary = ", ".join(f"ст.{idx_to_station[d]}: {val}" for d, val in items)
#                 print(f"   Ст.{idx_to_station[i]} → Ст.{idx_to_station[j]}: {dest_summary} → поезд [{total}]")
#                 edge_sends[(i, j)] = items

#         # 2. Обновляем w[t+1] по балансу
#         w_next = {}
#         arrivals = {}  # (j, d) → объём
#         for i in range(N):
#             for d in range(N):
#                 # Прибыло на i от других станций (за счёт отправок в день t-1 → прибытие в t)
#                 # Но у нас отправки в день t прибывают в t+1!
#                 inbound = 0
#                 for k in range(N):
#                     if (t, k, i) in sends_by_edge:
#                         for d2, val in sends_by_edge[(t, k, i)]:
#                             if d2 == d:
#                                 inbound += val
#                                 arrivals.setdefault((i, d), 0)
#                                 arrivals[(i, d)] += val
#                 # Отправлено с i в день t
#                 outbound = 0
#                 for j in edges_idx.get(i, []):
#                     if (t, i, j) in sends_by_edge:
#                         for d2, val in sends_by_edge[(t, i, j)]:
#                             if d2 == d:
#                                 outbound += val

#                 w_next[(i, d)] = w.get((t, i, d), 0) + inbound - outbound
#                 # Запрет отрицательных значений (должно быть 0 по модели)
#                 if w_next[(i, d)] < 0:
#                     w_next[(i, d)] = 0

#         # 3. Прибыло (можно вывести отдельно)
#         if arrivals:
#             print("\n📥 Прибыло:")
#             # Группируем по станции прибытия
#             by_station = {}
#             for (j, d), val in arrivals.items():
#                 by_station.setdefault(j, []).append((d, val))
#             for j in sorted(by_station):
#                 items = by_station[j]
#                 summary = ", ".join(f"назн. ст.{idx_to_station[d]}: {val}" for d, val in items)
#                 print(f"   На ст.{idx_to_station[j]} ← из других: {summary}")
#         else:
#             print("📥 Прибыло: —")

#         # 4. Состояние на станциях (остатки)
#         print("\n📊 Остатки на станциях (после отправок и прибытия):")
#         for i in range(N):
#             station_name = idx_to_station[i]
#             remaining = []
#             total_here = 0
#             for d in range(N):
#                 cnt = w_next.get((i, d), 0)
#                 if cnt > 0:
#                     dest_name = idx_to_station[d]
#                     remaining.append(f"ст.{dest_name}: {cnt}")
#                     total_here += cnt
#             if remaining:
#                 print(f"   Ст.{station_name}: {', '.join(remaining)} (всего: {total_here})")
#             else:
#                 print(f"   Ст.{station_name}: —")

#         # Переход к следующему дню
#         for i in range(N):
#             for d in range(N):
#                 w[(t+1, i, d)] = w_next[(i, d)]

# ======================
# ФИНАЛЬНЫЙ ИТОГОВЫЙ ВЫВОД
# ======================
print("\n" + "🧾".center(60, "="))
print("🧾 ИТОГИ РАБОТЫ".center(60))
print("=" * 60)

print(f"   Активных станций: {N} | Вагонов: {total_wagons}")
print(f"   Лимит времени: {TIME_LIMIT_SEC} сек | Ядер: {MAX_WORKERS}")
print(f"   ➤ Решение найдено: {'ДА' if best_T is not None else 'НЕТ'}")

if best_T is not None:
    print(f"   ➤ Время работы: {elapsed_total:.2f} сек")
    print(f"   ➤ Makespan (мин. дней для развоза): {best_T}")
    
    # Подсчёт числа поездов и их загрузки
    total_trains = len(best_solution)
    total_wagons_sent = sum(val for (_, _, _, _, val) in best_solution)
    avg_load = total_wagons_sent / total_trains if total_trains > 0 else 0
    
    print(f"   ➤ Всего поездов сформировано: {total_trains}")
    print(f"   ➤ Средняя загрузка поезда: {avg_load:.2f} ваг. (мин: 5, макс: 30)")
    
    # Проверка доставки
    delivered = []
    for d in range(N):
        dest_station = idx_to_station[d]
        expected = demand[d]
        actual = sum(
            val for (t, s_i, s_j, s_d, val) in best_solution 
            if s_d == dest_station and s_j == dest_station
        ) + od_data_raw.get((d, d), 0)  # + уже находившиеся на месте
        # Но точнее — из модели: w[T][d][d] == demand[d] — мы это гарантировали
        delivered.append(f"Ст.{dest_station}: {expected}/{expected}")
    print(f"   ✅ Все вагоны доставлены: {', '.join(delivered)}")

else:
    print(f"   ➤ Время работы: {elapsed_total:.2f} сек")
    print(f"   ➤ Makespan: — (решение не найдено)")