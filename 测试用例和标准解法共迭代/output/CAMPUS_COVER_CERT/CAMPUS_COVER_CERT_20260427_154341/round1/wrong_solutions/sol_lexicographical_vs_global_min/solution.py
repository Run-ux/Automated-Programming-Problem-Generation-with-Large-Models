def solve(input_str: str) -> str:
    import sys
    data = input_str.split()
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    ops = []
    for _ in range(q):
        ops.append((int(next(it)), int(next(it))))
    
    teams = []
    team_id = 0
    out = []
    
    for t, v in ops:
        if t == 1:
            team_id += 1
            teams.append((team_id, v))
        else:
            K = v
            limit = min(K, 500)
            min_surplus = float('inf')
            best_L, best_R = 0, 0
            found_violation = False
            
            for L in range(limit):
                for R in range(L, limit):
                    cnt = 0
                    for tid, a in teams:
                        r1 = a % x
                        r2 = (a + 1) % x
                        if (r1 >= L and r1 <= R) or (r2 >= L and r2 <= R):
                            cnt += 1
                    surplus = cnt - (R - L + 1)
                    # 错误理解：寻找全局盈余最小（违反程度最大）的区间，而非字典序最小
                    if surplus < min_surplus:
                        min_surplus = surplus
                        best_L, best_R = L, R
                        found_violation = True
            
            if found_violation and min_surplus < 0:
                out.append('NO')
                out.append(f'{best_L} {best_R}')
            else:
                out.append('YES')
                used_slots = set()
                for tid, a in teams:
                    if len(used_slots) == K: break
                    r1 = a % x
                    r2 = (a + 1) % x
                    for s in [r1, r2]:
                        if s < K and s not in used_slots:
                            out.append(f'{tid} {s}')
                            used_slots.add(s)
                            break
    return '\n'.join(out)