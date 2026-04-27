def solve(input_str: str) -> str:
    tokens = input_str.split()
    it = iter(tokens)
    x = int(next(it))
    q = int(next(it))
    teams = []
    next_id = 1
    out_lines = []
    for _ in range(q):
        typ = int(next(it))
        val = int(next(it))
        if typ == 1:
            teams.append((next_id, val))
            next_id += 1
        else:
            K = val
            m = len(teams)
            adj = [[] for _ in range(m)]
            for i, (tid, a) in enumerate(teams):
                a_mod = a % x
                a_next = (a_mod + 1) % x
                for s in range(K):
                    if s % x == a_mod or s % x == a_next:
                        adj[i].append(s)
            match_slot = [-1] * K
            def dfs(u, visited):
                for v in adj[u]:
                    if visited[v]:
                        continue
                    visited[v] = True
                    if match_slot[v] == -1 or dfs(match_slot[v], visited):
                        match_slot[v] = u
                        return True
                return False
            match_count = 0
            for i in range(m):
                visited = [False] * K
                if dfs(i, visited):
                    match_count += 1
            if match_count == K:
                out_lines.append("YES")
                for s in range(K):
                    t_idx = match_slot[s]
                    out_lines.append(f"{teams[t_idx][0]} {s}")
            else:
                found = False
                for L in range(K):
                    for R in range(L, K):
                        cnt = 0
                        for _, a in teams:
                            a_mod = a % x
                            a_next = (a_mod + 1) % x
                            covers = False
                            for s in range(L, R + 1):
                                if s % x == a_mod or s % x == a_next:
                                    covers = True
                                    break
                            if covers:
                                cnt += 1
                        if cnt < R - L + 1:
                            out_lines.append("NO")
                            out_lines.append(f"{L} {R}")
                            found = True
                            break
                    if found:
                        break
    return "\n".join(out_lines)