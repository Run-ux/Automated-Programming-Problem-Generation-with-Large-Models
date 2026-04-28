def solve(input_str):
    import sys, collections
    data = input_str.strip().split()
    if not data:
        return ''
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []
    class Dinic:
        def __init__(self, n):
            self.n = n
            self.graph = [[] for _ in range(n)]
        def add_edge(self, fr, to, cap):
            fwd = [to, cap, None]
            rev = [fr, 0, fwd]
            fwd[2] = rev
            self.graph[fr].append(fwd)
            self.graph[to].append(rev)
        def bfs(self, s, t):
            level = [-1] * self.n
            q = collections.deque([s])
            level[s] = 0
            while q:
                v = q.popleft()
                for to, cap, rev in self.graph[v]:
                    if cap > 0 and level[to] < 0:
                        level[to] = level[v] + 1
                        q.append(to)
            self.level = level
            return level[t] >= 0
        def dfs(self, v, t, f):
            if v == t:
                return f
            for i in range(self.it[v], len(self.graph[v])):
                self.it[v] = i
                to, cap, rev = self.graph[v][i]
                if cap > 0 and self.level[v] < self.level[to]:
                    ret = self.dfs(to, t, min(f, cap))
                    if ret > 0:
                        self.graph[v][i][1] -= ret
                        rev[1] += ret
                        return ret
            return 0
        def max_flow(self, s, t):
            flow = 0
            INF = 10**18
            while self.bfs(s, t):
                self.it = [0] * self.n
                while True:
                    f = self.dfs(s, t, INF)
                    if f == 0:
                        break
                    flow += f
            return flow
    for _ in range(q):
        typ = int(next(it))
        if typ == 1:
            a = int(next(it))
            teams.append((len(teams) + 1, a))
        else:
            K = int(next(it))
            if K >= x:
                if len(teams) < K:
                    out.append('NO')
                    out.append(f'0 {K - 1}')
                else:
                    out.append('YES')
                    for s in range(K):
                        out.append(f'{teams[s % len(teams)][0]} {s}')
            else:
                def count_cover(L, R):
                    cnt = 0
                    for tid, a_i in teams:
                        rems = {a_i % x, (a_i + 1) % x}
                        ok = False
                        for r in rems:
                            s0 = L + ((r - L) % x + x) % x
                            if s0 <= R:
                                ok = True
                                break
                        if ok:
                            cnt += 1
                    return cnt
                conflict = None
                for L in range(K):
                    for R in range(L, K):
                        cnt = count_cover(L, R)
                        if cnt < R - L + 1:
                            if conflict is None or (L < conflict[0]) or (L == conflict[0] and R < conflict[1]):
                                conflict = (L, R)
                if conflict is not None:
                    out.append('NO')
                    out.append(f'{conflict[0]} {conflict[1]}')
                else:
                    n = len(teams)
                    N = 1 + n + K + 1
                    S, T = 0, N - 1
                    dinic = Dinic(N)
                    for i, (tid, a_i) in enumerate(teams, start=1):
                        dinic.add_edge(S, i, 1)
                    for j in range(K):
                        dinic.add_edge(n + 1 + j, T, 1)
                    for i, (tid, a_i) in enumerate(teams, start=1):
                        rems = {a_i % x, (a_i + 1) % x}
                        for j in range(K):
                            if j % x in rems:
                                dinic.add_edge(i, n + 1 + j, 1)
                    flow = dinic.max_flow(S, T)
                    if flow != K:
                        out.append('NO')
                        out.append(f'0 {K - 1}')
                    else:
                        out.append('YES')
                        for s in range(K):
                            out.append(f'{teams[s % len(teams)][0]} {s}')
    return '\n'.join(out)