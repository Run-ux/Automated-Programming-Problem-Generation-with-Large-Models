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
            # 简化 Hall 检查：仅验证队伍总数是否足够及基础覆盖性
            if len(teams) < K:
                out.append('NO')
                out.append('0 0')
                continue
            
            out.append('YES')
            used_teams = set()
            used_slots = set()
            # 错误策略：按顺序遍历时段，贪心分配任意可用队伍，未考虑独占性阻塞后续关键匹配
            for s in range(K):
                assigned = False
                for tid, a in teams:
                    if tid in used_teams: continue
                    r1 = a % x
                    r2 = (a + 1) % x
                    if s == r1 or s == r2:
                        out.append(f'{tid} {s}')
                        used_teams.add(tid)
                        used_slots.add(s)
                        assigned = True
                        break
                if not assigned:
                    # 贪心失败时，选手可能直接中断或输出不完整，导致 Checker 拦截
                    break
    return '\n'.join(out)