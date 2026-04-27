def solve(input_str: str) -> str:
    data = input_str.split()
    if not data:
        return ""
    it = iter(data)
    x = int(next(it))
    q = int(next(it))

    teams = []
    out_lines = []

    for _ in range(q):
        typ = int(next(it))
        val = int(next(it))
        if typ == 1:
            teams.append((len(teams) + 1, val))
        else:
            K = val
            adj = [[] for _ in range(len(teams))]
            for i, (tid, a) in enumerate(teams):
                m1 = a % x
                m2 = (a + 1) % x
                for s in range(K):
                    if s % x == m1 or s % x == m2:
                        adj[i].append(s)

            match_r = [-1] * K
            def dfs(u, vis):
                for v in adj[u]:
                    if not vis[v]:
                        vis[v] = True
                        if match_r[v] == -1 or dfs(match_r[v], vis):
                            match_r[v] = u
                            return True
                return False

            match_count = 0
            for i in range(len(teams)):
                vis = [False] * K
                if dfs(i, vis):
                    match_count += 1

            if match_count == K:
                out_lines.append("YES")
                for s in range(K):
                    tid = teams[match_r[s]][0]
                    out_lines.append(f"{tid} {s}")
            else:
                found = False
                for L in range(K):
                    for R in range(L, K):
                        cnt = 0
                        for _, a in teams:
                            m1 = a % x
                            m2 = (a + 1) % x
                            covers = False
                            for s in range(L, R + 1):
                                if s % x == m1 or s % x == m2:
                                    covers = True
                                    break
                            if covers:
                                cnt += 1
                        if cnt < (R - L + 1):
                            out_lines.append("NO")
                            out_lines.append(f"{L} {R}")
                            found = True
                            break
                    if found:
                        break
    return "\n".join(out_lines)